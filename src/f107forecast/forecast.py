from datetime import timedelta
from .model import Config, DriftFilter, RegressionFilter


def forecast_daily(series, config=Config(), warmup=30):
    models=[DriftFilter(config),RegressionFilter(config)]
    n=0; last=None
    for date,y in sorted(series):
        if last is not None and date-last!=timedelta(days=1):
            models=[DriftFilter(config),RegressionFilter(config)]; n=0
        for m in models:m.update(y)
        n+=1; last=date
    if n<warmup: raise ValueError(f'Need {warmup} consecutive daily observations; have {n}')
    return {'origin_date':str(last),'units':'sfu','series':'observed','daily_definition':'20:00 UTC, exact',
            'warmup_observations':n,'model_version':'0.1.0.dev1','parameters':config.json(),
            'uncertainty':'conditional Gaussian approximation; drift and hyperparameter uncertainty not fully represented',
            'methods':{m.name:[{'target_date':str(last+timedelta(days=h)),'horizon_days':h,**p}
                               for h,p in enumerate(m.forecast(),1)] for m in models}}
