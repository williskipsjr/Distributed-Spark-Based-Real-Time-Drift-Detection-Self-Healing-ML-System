from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parent


def _build_path(project_root: Path, *parts: str) -> Path:
    path = project_root.joinpath(*parts).resolve()
    if path == project_root:
        raise ValueError("Refusing to operate on the project root directory")
    if project_root not in path.parents:
        raise ValueError(f"Refusing to operate outside project root: {path}")
    return path


def _remove_directory_contents(target_dir: Path, project_root: Path) -> tuple[int, list[str]]:
    if target_dir == project_root:
        raise ValueError("Refusing to delete the project root directory")
    if project_root not in target_dir.parents:
        raise ValueError(f"Refusing to delete contents outside project root: {target_dir}")

    removed_items: list[str] = []
    if target_dir.exists():
        for child in sorted(target_dir.iterdir(), key=lambda item: item.name.lower()):
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
            removed_items.append(child.name)
    else:
        print(f"Directory missing, creating: {target_dir.relative_to(project_root)}")

    target_dir.mkdir(parents=True, exist_ok=True)
    return len(removed_items), removed_items


def _log_reset_result(label: str, target_dir: Path, project_root: Path, removed_count: int, removed_items: list[str]) -> None:
    relative_path = target_dir.relative_to(project_root)
    if removed_count == 0:
        print(f"{label}: nothing to remove in {relative_path}")
        return

    print(f"Deleted {label} from {relative_path} ({removed_count} item(s))")
    for item_name in removed_items:
        print(f"  - {item_name}")


def reset_pipeline(clear_predictions: bool = True, hard_reset: bool = False) -> None:
    project_root = _project_root()
    targets = [
        ("hourly metrics", _build_path(project_root, "data", "metrics", "hourly_metrics")),
        ("Spark checkpoints", _build_path(project_root, "checkpoints", "spark_predictions")),
    ]

    if clear_predictions:
        targets.append(("prediction outputs", _build_path(project_root, "data", "predictions")))

    if hard_reset:
        targets.append(("drift reports", _build_path(project_root, "artifacts", "drift")))

    print("Resetting pipeline state...")
    for label, target_dir in targets:
        removed_count, removed_items = _remove_directory_contents(target_dir=target_dir, project_root=project_root)
        _log_reset_result(
            label=label,
            target_dir=target_dir,
            project_root=project_root,
            removed_count=removed_count,
            removed_items=removed_items,
        )

    if not clear_predictions:
        print("Prediction outputs preserved")

    if hard_reset:
        print("Hard reset enabled: drift reports cleared")

    print("Pipeline state reset complete.")


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Safely clear streaming pipeline state before restarting Kafka and Spark.",
    )
    parser.add_argument(
        "--keep-predictions",
        action="store_true",
        help="Preserve data/predictions instead of clearing it.",
    )
    parser.add_argument(
        "--hard-reset",
        action="store_true",
        help="Also clear drift reports in artifacts/drift.",
    )
    return parser


def main() -> None:
    args = _build_argument_parser().parse_args()
    reset_pipeline(
        clear_predictions=not args.keep_predictions,
        hard_reset=args.hard_reset,
    )


if __name__ == "__main__":
    main()