Prepared Blueprint: Python FastAPI, one Uvicorn worker, `$PORT`, `/health` process probe. Free preview selected to avoid a new paid resource. Source cache and forecast-vintage files are local; on Free instances they are **ephemeral**. Never describe this setup as durable operational archiving.

Free Render web instances sleep after inactivity. The app's timer runs only while awake. A request also checks the refresh TTL. This is safe update-on-request with caching, NOT a guarantee of two scheduled daily updates.

For a robust scientific deployment, choose durable storage plus an external scheduler (or Render cron if explicitly selected), then verify that a fetch and archival write run successfully twice daily. Candidate check times are 21:00 and 00:00 UTC (after 20:00 and 22:00/23:00 measurements), but actual publication lag must be observed; these are not promised source release times. Polling can retry delayed observations without duplicate assimilation.

Environment:
- F107_DATA_DIR: cache/snapshot/forecast directory.
- F107_REFRESH_SECONDS: >=60; default 300.
- F107_CONFIG: frozen model config path; default results/config.json.
- F107_VALIDATION: validation JSON path.
- F107_DURABLE_STORAGE: false by default; set true only with verified durable storage.
- RENDER_GIT_COMMIT: injected by deployment, used as provenance.

Before a public release: complete full archive hindcast, freeze configuration, verify live fetch, add durable issued-forecast retention, verify schedule, audit all publishable files, create separate public GitHub repository, deploy, then archive a stable tagged release to Zenodo. A running process without data is not an accepted live forecast service.

Live provider defaults to NOAA SWPC (F107_PROVIDER=noaa). The service polls every
300 seconds while awake, uses NOAA noon observations and issues once per new noon
input (plus source revisions). Twice-daily issuance is not enabled for NOAA until
its afternoon timestamps are reconciled with Canada. A free Render web service
sleeps without traffic; it cannot guarantee unattended five-minute polling.
No Render deployment has been created. An always-on plan and persistent storage
would require selecting and authorizing those resources before deployment.
