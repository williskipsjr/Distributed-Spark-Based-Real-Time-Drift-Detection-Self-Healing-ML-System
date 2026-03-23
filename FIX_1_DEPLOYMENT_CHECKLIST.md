# FIX #1 DEPLOYMENT CHECKLIST

Use this checklist to deploy zone aggregation fix to production.

---

## Pre-Deployment (Local Testing)

- [ ] Pull latest code with producer changes
- [ ] Run validation tests:
  ```bash
  python test_fix_zone_aggregation.py
  # Expected: 3/3 tests passed
  ```
- [ ] Verify no errors in test output
- [ ] Confirm all three test categories pass:
  - [ ] Zone Aggregation
  - [ ] Parquet Load
  - [ ] Feature Alignment

---

## Deployment to Staging

- [ ] Stop current Kafka producer:
  ```bash
  pkill -f "kafka_producer"
  ```

- [ ] Start new producer with aggregate data (test with safe 2018 data first):
  ```bash
  python -m src.streaming.kafka_producer \
    --dataset data/processed/pjm_supervised.parquet \
    --sleep-seconds 1.0 \
    --log-level INFO
  ```

- [ ] Verify producer starts without errors
- [ ] Consume one Kafka message and verify load_mw is ~180k:
  ```bash
  kafka-console-consumer --bootstrap-servers localhost:9092 \
    --topic pjm.load --max-messages 1 | \
    python3 -m json.tool | grep load_mw
  # Should output: "load_mw": 183040.34
  ```

- [ ] Start Spark streaming job in DEBUG mode:
  ```bash
  python -m src.streaming.spark_job --debug-mode True
  ```

- [ ] Check Spark console output for predictions:
  ```
  UDF PRED SAMPLE: [180000, 179000, 181000, ...]  ← GOOD (in training range)
  NOT: [120000, 140000, 150000, ...]               ← BAD (way too high)
  ```

- [ ] Monitor error values (should be reasonable, <5% typically):
  ```
  actual_load: ~180,000
  predicted_load: ~180,000
  error: <10,000
  ```

- [ ] Run for at least 10 batches (10 minutes with 0.1s sleep) without crashing

---

## Validation Checkpoints

### Producer Logs
- [ ] No warnings about `data-distribution-warning`
- [ ] See `aggregating-zones-to-pjm-wide` if using CSV
- [ ] `load_mw_mean` is ~183k (2018) or ~180k (2019 aggregated)
- [ ] NO `load_mw_mean` like `5994` (that's per-zone!)

### Spark Streaming Logs
- [ ] No warnings about distribution shift
- [ ] Predictions are 170k-200k range (not 120k-140k)
- [ ] Error values are 1k-10k (not 180k)

### Metrics Output
- [ ] Parquet metrics files created in `data/metrics/hourly_metrics/`
- [ ] Files have non-zero record counts
- [ ] `mean_prediction` is ~180k (not way off)

---

## Staging Validation (With 2019 Data)

Only proceed to this section after passing above with 2018 data:

- [ ] Stop producer and job
- [ ] Start producer with 2019 zone-level data:
  ```bash
  python -m src.streaming.kafka_producer \
    --dataset data/stream_dataset/hrl_load_metered-2019.csv \
    --sleep-seconds 0.5 \
    --log-level INFO
  ```

- [ ] Verify producer starts and shows aggregation:
  ```
  aggregating-zones-to-pjm-wide: unique_zones: 30
  zone-aggregation-complete: load_mw_mean: 179850.87
  ```

- [ ] Start Spark job:
  ```bash
  python -m src.streaming.spark_job --debug-mode True
  ```

- [ ] Verify predictions are still in range:
  ```
  actual_load: ~180,000 (aggregated 2019)
  predicted_load: ~180,000 (matches!)
  error: <5,000
  ```

---

## Rollback Plan (If Something Goes Wrong)

If predictions still look wrong after deployment:

1. Stop producer and Spark job
2. Check producer logs for distribution warnings (mean_load < 50k?)
3. If so, old code is running:
   - Verify `kafka_producer.py` has `_load_and_prepare_data()` function
   - Check git status - should include producer changes
4. Revert to previous working version:
   ```bash
   git checkout HEAD~1 src/streaming/kafka_producer.py
   ```
5. Restart producer and re-test
6. Open issue with debug logs if problem persists

---

## Production Deployment (Final)

After successful staging validation:

- [ ] Review all logs from staging run
- [ ] Confirm 100+ messages processed with no errors
- [ ] Get approval from ML team lead
- [ ] Deploy to production with gradual rollout:
  - [ ] Deploy producer first
  - [ ] Wait 5 minutes, verify logs show aggregation
  - [ ] Deploy Spark job
  - [ ] Monitor for 30 minutes
- [ ] Set up alerts for distribution shift warnings

---

## Post-Deployment Monitoring (1 Week)

- [ ] Check producer logs daily:
  - No `data-distribution-warning` messages
  - `load_mw_mean` consistently ~180k
- [ ] Check Spark job logs:
  - Error metrics consistently <5%
  - No drift detector alerts
- [ ] Verify metrics parquet files accumulating normally
- [ ] Test model predictions on fresh data samples

---

## Success Criteria

✓ Fix is deployed successfully when:
1. Kafka messages show load_mw ~ 180,000 (not 1-6k)
2. Model predictions ~ 180,000 (not 120-140k)
3. Prediction errors ~ 1-10k (not 120-180k)
4. No distribution shift warnings in logs
5. Spark job runs for >1 hour without errors
6. Metrics files created with valid data

✗ Fix needs rollback if:
1. Kafka messages show load_mw < 10,000
2. Model predictions > 200,000 or < 100,000
3. Errors > 50,000 (still 30x off)
4. Distribution shift warnings appear
5. Spark job crashes or hangs

---

## Questions?

See `FIX_1_IMPLEMENTATION.md` for detailed documentation.
