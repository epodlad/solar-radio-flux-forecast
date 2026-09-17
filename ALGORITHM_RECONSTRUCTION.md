# Mathematical specification: new implementation

Status: SOURCE_DESCRIPTION_DERIVED with explicitly new implementation choices. Legacy executable/source unavailable. This document is not a claim of reverse-engineering completed source code.

## Target and chronology

Observed F10.7, one exact 20:00 UTC measurement per UTC date, sfu. No interpolation. Missing dates restart the filter; require 30 consecutive observations before a forecast. Observations at other times are retained. Final archive data do not carry historic receipt times or vintages: retrospective runs are archive-vintage hindcasts, not exact operational replays.

## A. Adaptive scalar drift

Poster-supported structure: x[k+1] = x[k] + drift[k+1] dt + w[k+1] dt; z[k] = x[k] + epsilon[k]. Drift from exponentially smoothed increments. Identification of variance stated but exact equations unavailable.

Implemented new discrete daily convention:

- x_minus = x_previous + d_previous
- P_minus = P_previous + Q_previous
- e = z - x_minus; K = P_minus / (P_minus + R)
- x = x_minus + K e
- P = (1-K)^2 P_minus + K^2 R (Joseph scalar form)
- Q_next = max(Q_floor, (1-b) Q_previous + b max(Q_floor, e^2-P_previous-R))
- d_next = (1-a)d_previous + a(z-z_previous)

Initialization x=z_first, d=0, P=R, Q=Q_initial. Forecast mean x+h*d, variance P+h*Q+R. R includes future-observation noise. This is conditional on estimated drift/Q; their estimation uncertainty is not fully included. No nominal coverage claim is justified until evaluated.

New defaults: a=.45, b=.05, R=4 sfu^2, Q_initial=25 sfu^2, Q_floor=.01 sfu^2. These are configurable exploratory choices, not recovered SASFF parameters. The .45 weight is documented only for the regression poster; its use as a scalar candidate has no historical equivalence claim. Training grid compares scalar a in [.1,.25,.45,.82] using only the tuning interval.

## B. Adaptive regression

Poster: F[k+1]=a0+a1*F[k]+a2*D[k]+epsilon; D[k]=(1-alpha)D[k-1]+alpha(F[k]-F[k-1]); alpha=.45.

Coefficient state follows random walk. Implementation conditions features numerically as phi=[1,F/100,D/100], beta=[a0,100*a1,100*a2]. Initial beta=[0,100,0], P_beta=diag(100,100,100), coefficient diffusion Q_beta=q_beta I. Default q_beta=.01; new configurable choice.

When z[k] arrives, phi is built from k-1 data; predict P_beta_minus=P_beta+Q_beta. Set S=phi P_beta_minus phi^T + residual_variance + R, K=P_beta_minus phi^T/S. Update beta and Joseph covariance. Adapt NEXT residual variance by EWMA of max(floor,e^2-phi P_beta_minus phi^T-R). Only after the coefficient update, compute D[k] using current z[k]. This ordering avoids updating with the target and scoring that fitted value as an earlier forecast.

Multi-day mean recursively substitutes forecast F,D while holding coefficient means fixed. Joint uncertainty state u=(beta0,beta1,beta2,F,D). Before each transition add Q_beta to the coefficient covariance. Transition F'=beta0+beta1 F/100+beta2 D/100, D'=(1-alpha)D+alpha(F'-F). Propagate C'=J C J^T + residual_variance*g*g^T, g=(0,0,0,1,alpha); output variance C_FF+R. Initial joint C has only the beta posterior covariance; previous observed F,D are conditional features. Future measurement noise is added to each target interval, not recursively treated as process noise. This is a first-order approximation and NEW 2/3-day extension, not a recovered poster formula.

## C. Late Penticton correction experiment

Only model A for now. At evening timestamp t after same-day noon, dt=(t-noon)/86400. Hold noon-estimated drift and Q fixed. Propagate x_t=x_noon+dt*d, P_t=P_noon+dt*Q, then assimilate the evening observed flux with variance R. Forecast future noons using residual horizons h-dt. This assumes the same latent evolving flux/diffusion across a day; it is a hypothesis to validate, not proof that intraday scatter represents sustained activity. It does not feed the short increment into daily EWMA drift. Does not mutate the daily baseline. Compare on paired issue/target dates. Evening correction is shown separately and labeled experimental; it does not replace the noon forecasts. An equivalent regression extension is not yet implemented.

## Unknown historical details

Original R/Q adaptation, initialization, operational series, exact correction of flares/outliers, alert thresholds, interval definition, cron schedule and original output values remain UNKNOWN. No alert threshold invented.
