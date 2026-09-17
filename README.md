# Solar Radio Flux Forecast

Adaptive Kalman Forecasting of F10.7. **Research prototype, 0.1.0.dev1. Not a validated public release.**

An independent modern implementation of the short-term solar radio-flux forecasting research line developed by Olena Podladchikova during her work at the Royal Observatory of Belgium / SIDC-STCE. Two historical posters motivate a scalar random walk with adaptive drift and a Kalman regression. The original source has not been located: this repository does **not** claim to reproduce original numerical outputs.

Only official Canadian Penticton observations are used. This is not a forecast issued by ROB/STCE or the Government of Canada. Original source, private working notes and institutional assets are excluded.

## Run

Python 3.11 or later:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
python -m uvicorn f107forecast.api:app --host 0.0.0.0 --port 8080 --workers 1
```

On Windows activate with `.venv\Scripts\activate` instead. The website is at `http://localhost:8080`; OpenAPI documentation at `/docs`.

The filter uses earlier observations to initialize itself. Minimum warmup is 30 **consecutive** daily observations. That is not a claim that a month is scientifically sufficient for hyperparameter selection.

## Data and forecast meaning

Default target: `fluxobsflux` at exactly 20:00 UTC, for each of the following three calendar dates, in sfu. This observed-flux choice supports terrestrial space-weather applications and is a **new implementation decision**; the historical convention is unknown. Adjusted flux is parsed and available for future controlled comparisons. No daily averaging or nearest-time substitution is performed.

The live service defaults to Canadian measurements distributed by NOAA SWPC at https://services.swpc.noaa.gov/json/f107_cm_flux.json. It selects Noon records at 20:00 UTC and preserves provider precision. Unavailable adjusted flux fields are null. The rolling cache retains 90 days and forecast files 30 days. The optional Canadian adapter and the historical CLI use the official Canadian archive with hashed snapshots. Repeated identical snapshots do not re-assimilate data. Corrected source files produce a new forecast ID by replaying the chronology. A newer evening measurement is shown separately from the noon forecast origin; the evening correction is displayed separately as an unvalidated experimental result; noon forecasts are preserved.

## Validation status

18 numerical/pipeline/API tests pass. Tests include prefix invariance under changed future observations, an independently calculated scalar Kalman step, duplicate handling, missing-day warmup, covariance behavior and source-failure recovery. No legacy golden tests exist.

Multi-year independent validation is pending. Preliminary numerical results and offline calculation snapshots are not included in this public package. See VALIDATION.md.

## API

- `/api/latest`: latest selected measurement; sfu, UTC; unavailable flux series are null.
- `/api/forecast`: daily model forecasts, uncertainty, target dates and provenance.
- `/api/history?days=90`: recent measurements.
- `/api/validation`: full validation results if generated; otherwise HTTP 503.
- `/api/provenance`: hash, source, retrieval/calculation times, version and commit.
- `/api/status`: scientific data readiness, source errors and stale data status.
- `/health`: process liveness only.

The service returns explicit HTTP 503 when observations are absent or warmup is insufficient. Source failures keep the last successful result, labeled degraded. `/health` being alive is **not** proof of a current forecast.

## Deployment

`render.yaml` defines a single FastAPI web service. The current Free plan configuration is a preview, with checks every 5 minutes while the process is awake and refresh-on-request. It does **not** guarantee two daily jobs. Render free instances sleep and have ephemeral disk; durable forecast-vintage retention and reliable daily scheduling need an explicit storage/scheduler deployment decision. See docs/DEPLOYMENT.md. No paid service was created.

## Development

```bash
python -m pytest -q
```

See ALGORITHM_RECONSTRUCTION.md for exact implemented equations and omissions; HISTORY.md and REFERENCES.md distinguish the two historical author lists. The code is MIT licensed. Data/source publications retain their own terms.
