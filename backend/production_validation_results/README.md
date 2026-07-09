# Production Validation

## Status: VALIDATED

Last run: 2026-07-09T16:11:18.931411+00:00  Passed: 20/20 (100.0%)

## To Run Validation

```bash
cd backend
python run_production_validation.py
```

This will:
1. Test all 4 cities (Mumbai, Pune, Ahmedabad, Nashik)
2. Run 5 test cases per city (20 total)
3. Generate `production_validation_results/validation_summary.json`

## Generate Report

```bash
cd backend
python generate_validation_report.py
```

Only run this AFTER successful validation.

## Rules

- NO fake validation data
- NO hand-written production claims
- Reports generated ONLY from actual test runs
