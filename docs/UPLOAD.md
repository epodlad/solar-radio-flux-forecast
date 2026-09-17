# Upload and release sequence

This is development version 0.1.0.dev1, not a stable release.

1. Create a separate GitHub repository named solar-radio-flux-forecast.
2. Extract the archive. Upload the CONTENTS of its solar-radio-flux-forecast folder to the repository root, including .gitignore. Do not upload the ZIP itself as the source tree. render.yaml and pyproject.toml must be at the root.
3. The website is served by Python from src/f107forecast/static/index.html. A saved HTML preview is not the live service.
4. Complete seasonal scheduling and reconcile the additional measurement before claiming twice-daily forecasting. Current code still uses a refresh interval while awake.
5. Deploy and verify the actual Render URL, health, observations, forecasts and provenance. The supplied free preview configuration does not guarantee unattended scheduled runs or durable storage.
6. After scientific validation and deployment acceptance, create a tagged GitHub release and archive that release in Zenodo. No DOI exists yet.

Primary software author: Olena Podladchikova. License: MIT for new software only. No legacy source or institutional assets are included.
