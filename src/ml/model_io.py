"""Model loading and inference utilities.

This module centralizes inference behavior so both offline evaluation and
future Spark streaming code paths use the same prediction logic.

Core flow:
1. Load a trained model artifact with ``load_model``.
2. Validate and align input features using shared ``FEATURE_COLUMNS``.
3. Run inference via ``predict``.
4. Use ``predict_batch`` when predictions must be appended to a DataFrame.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from src.common.logging import get_logger
from src.data.feature_builder import FEATURE_COLUMNS


model_version = "v1"
PREDICTION_COLUMN = "predicted_load"

_logger = get_logger(__name__)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _models_dir() -> Path:
    return _project_root() / "artifacts" / "models"


def _active_model_pointer_path() -> Path:
    return _models_dir() / "active_model.json"


def _resolve_active_model_path() -> Path | None:
    # Reads active pointer file so serving can follow promoted model.
    pointer_path = _active_model_pointer_path()
    if not pointer_path.exists():
        return None

    try:
        payload = json.loads(pointer_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    if not isinstance(payload, dict):
        return None

    active_path = payload.get("active_model_path")
    if not isinstance(active_path, str) or not active_path:
        return None

    resolved = Path(active_path)
    return resolved if resolved.exists() else None


def _find_latest_model(models_dir: Path) -> Path:
    if not models_dir.exists():
        raise FileNotFoundError(f"Model directory not found: {models_dir}")

    candidates = [
        path
        for path in models_dir.rglob("*.joblib")
        if path.is_file()
    ]
    if not candidates:
        raise FileNotFoundError(f"No model artifacts found under: {models_dir}")

    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return candidates[0]


def _is_bundle(obj: Any) -> bool:
    """Return True when *obj* is a model bundle dict containing model + features."""
    return isinstance(obj, dict) and "model" in obj and "features" in obj


def load_model(model_path: str | None = None):
    """Load a trained model artifact using joblib.

    Always returns a bundle dict ``{"model": <estimator>, "features": [...]}``.  
    Legacy artifacts that contain only the raw estimator are wrapped automatically
    using the shared ``FEATURE_COLUMNS`` list so old files remain usable.

    If ``model_path`` is ``None``, the most recently modified ``.joblib`` file
    from ``artifacts/models`` is loaded.
    """

    # ----------------------------------------------------
    # ----------------- Model Load Block -----------------
    # Resolves explicit path or active/latest model and normalizes format.
    # ----------------------------------------------------
    if model_path:
        resolved_path = Path(model_path)
    else:
        resolved_path = _resolve_active_model_path() or _find_latest_model(_models_dir())
    if not resolved_path.exists():
        raise FileNotFoundError(f"Model artifact not found: {resolved_path}")

    _logger.info("model-loading-start", extra={"model_path": str(resolved_path)})
    loaded = joblib.load(resolved_path)

    # Normalise to bundle format — handle both new bundles and legacy raw models.
    if _is_bundle(loaded):
        bundle = loaded
    else:
        bundle = {"model": loaded, "features": FEATURE_COLUMNS}

    inferred_version = _infer_model_version(resolved_path)
    _attach_metadata(bundle["model"], resolved_path=resolved_path, inferred_version=inferred_version)

    _logger.info(
        "model-loading-complete",
        extra={
            "model_path": str(resolved_path),
            "model_version": inferred_version,
        },
    )
    return bundle


def predict(model_or_bundle, features_df: pd.DataFrame) -> pd.Series:
    """Run model inference from a pandas DataFrame of feature columns.

    Accepts either a raw estimator or a bundle dict from ``load_model()``.
    Returns a pandas Series aligned to ``features_df`` index.
    """

    # ----------------------------------------------------
    # ---------------- Prediction Inference --------------
    # Validates feature contract and runs estimator prediction.
    # ----------------------------------------------------
    if not isinstance(features_df, pd.DataFrame):
        raise TypeError("features_df must be a pandas.DataFrame")

    if _is_bundle(model_or_bundle):
        raw_model = model_or_bundle["model"]
        feature_list = model_or_bundle["features"]
    else:
        raw_model = model_or_bundle
        feature_list = FEATURE_COLUMNS

    missing = [col for col in feature_list if col not in features_df.columns]
    if missing:
        raise KeyError(f"Missing required feature columns: {', '.join(missing)}")

    model_input = features_df[feature_list]

    _logger.info(
        "prediction-start",
        extra={
            "rows": int(len(model_input)),
            "feature_count": int(len(feature_list)),
            "model_version": get_model_version(model_or_bundle),
        },
    )

    predictions = raw_model.predict(model_input)
    result = pd.Series(predictions, index=features_df.index, name=PREDICTION_COLUMN)

    _logger.info(
        "prediction-complete",
        extra={
            "rows": int(len(result)),
            "model_version": get_model_version(model_or_bundle),
        },
    )
    return result


def predict_batch(model_or_bundle, df: pd.DataFrame) -> pd.DataFrame:
    """Append predictions to a DataFrame as ``predicted_load``.

    Accepts either a raw estimator or a bundle dict from ``load_model()``.
    """

    if not isinstance(df, pd.DataFrame):
        raise TypeError("df must be a pandas.DataFrame")

    output = df.copy()
    output[PREDICTION_COLUMN] = predict(model_or_bundle=model_or_bundle, features_df=output)
    return output


def get_model_version(model_or_bundle: Any, default: str = model_version) -> str:
    raw_model = model_or_bundle["model"] if _is_bundle(model_or_bundle) else model_or_bundle
    return str(getattr(raw_model, "model_version", default))


def _validate_feature_columns(df: pd.DataFrame) -> None:
    missing = [column for column in FEATURE_COLUMNS if column not in df.columns]
    if missing:
        raise KeyError(f"Missing required feature columns: {', '.join(missing)}")


def _infer_model_version(model_path: Path) -> str:
    stem = model_path.stem.lower()
    if "model_" in stem:
        return stem.replace("model_", "")
    if stem.startswith("v"):
        return stem
    return model_version


def _attach_metadata(model: Any, resolved_path: Path, inferred_version: str) -> None:
    # Backfills minimal metadata so downstream logs are informative.
    if not hasattr(model, "model_version"):
        try:
            setattr(model, "model_version", inferred_version)
        except Exception:
            pass

    if not hasattr(model, "model_path"):
        try:
            setattr(model, "model_path", str(resolved_path))
        except Exception:
            pass
