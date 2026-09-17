# Provenance

Only Canadian Penticton observations are used, distributed through NOAA SWPC by default or through the optional Canadian archive adapter. The snapshot description below applies to the Canadian adapter; NOAA cache policy is described separately below. In live operation each successful fetch records UTC retrieval time, source URL, SHA256, record count and rejected-line diagnostics. Snapshots are immutable and named by hash; the validated latest table is atomically replaced. Numerical corrections to a source snapshot cause a new model replay and forecast identity. Forecast identity includes snapshot hash, configuration and software version. Deployment commit is attached separately.

Measurement time is not publication time. The Canadian archive does not supply the history of publication delays and revisions required for a true as-issued replay. Historical accuracy metrics are explicitly archive-vintage hindcasts.

MEASURED: Canadian numeric flux fields, as represented by the selected data provider.
SOURCE_DERIVED: poster model structure, regression smoothing weight.
ASSUMED: new initialization/noise defaults, Gaussian approximations, fixed noon convention and gap policy.
MODEL_DERIVED: forecasts, intervals, retrospective metrics.

No legacy source, original posters, working drafts, institutional logos or private paths are included in the distributable. Citation metadata identifies new software author only and does not erase historical collaborators.

## NOAA live input (2026-09-17)
Default live provider is NOAA SWPC: https://services.swpc.noaa.gov/json/f107_cm_flux.json.
NOAA credits the Canadian Solar Radio Monitoring Program; this is a distribution source,
not another observatory. Only 2800 MHz records marked Noon at 20:00 UTC are used.
NOAA values are preserved at their reported precision. They are not numerically identical
to the Canadian archive excerpt; existing Canadian hindcasts do not validate this input variant.
Afternoon timestamps differ between feeds in the inspected sample, so NOAA evening correction
is disabled pending reconciliation. No adjusted flux, Julian date or Carrington value is invented.
Set F107_PROVIDER=canada to use the earlier Canadian adapter; caches are separate.
NOAA storage is one rolling 90-day cache and issued forecast files retained for 30 days.
This limits operational reproducibility to the retention window; future validation datasets should be archived separately with explicit provenance.

Afternoon update: NOAA time tags are preserved. The fractional-day correction assumes the NOAA-reported elapsed time; differences from the seasonal Penticton schedule remain unresolved. Applied status, noon cutoff, evening observation and per-method cutoffs are included in the forecast API.
