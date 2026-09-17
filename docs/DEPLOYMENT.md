# Deployment

Python 3.12; build `pip install .`; start `python -m uvicorn f107forecast.api:app --host 0.0.0.0 --port $PORT --workers 1`. Health path: `/health`.

Set `F107_PROVIDER=noaa`. `F107_DATA_DIR` optionally selects the data directory. One worker avoids duplicate schedulers. The existing Render service is paid and automatically deploys commits on main. The blueprint retains a free preview option; sleeping instances cannot reliably execute scheduled checks.

Checks: 20:45 and 23:45 UTC March–October; 20:45 and 22:45 November–February. One startup fetch initializes data after a restart. Requests before the next scheduled check do not download data. The old `F107_REFRESH_SECONDS` variable is unused.

These times allow 45 minutes after scheduled observations; they do not guarantee data publication. A failure keeps the last good forecast, marks the service degraded and waits until the next scheduled check. A restart initializes from cache when present and fetches once. No persistent disk is provisioned here; local caches and forecast history can be lost on deploy.

The API reports `next_check_utc`, input cutoffs and `evening_update_applied`. `/health` checks process liveness, not data freshness. NOAA afternoon timing is used as reported for the experimental correction; the discrepancy with seasonal measurement times remains documented in provenance.
