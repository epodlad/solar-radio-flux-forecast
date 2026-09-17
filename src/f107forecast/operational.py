"""Noon/late issue selection. Morning observations do not trigger daily forecasts."""
from datetime import datetime, time, timezone, timedelta
import hashlib,json
from .data import daily
from .forecast import forecast_daily
from .model import Config,DriftFilter

def make_issue(records,config=Config()):
    series=daily(records)
    result=forecast_daily(series,config)
    day=series[-1][0]
    noon=datetime.combine(day,time(20),timezone.utc)
    evening=[o for o in records if o.time.date()==day and o.time>noon]
    late=evening[-1] if evening else None
    stage='evening' if late else 'noon'
    inputs={'daily':[(str(d),v) for d,v in series],'evening':late.json() if late else None,
            'parameters':config.json(),'model_version':result['model_version']}
    result['forecast_id']=hashlib.sha256(json.dumps(inputs,sort_keys=True).encode()).hexdigest()
    result['issue_stage']=stage
    result['evening_observation']=late.json() if late else None
    result['evening_update_applied']=late is not None
    result['noon_input_cutoff_utc']=noon.isoformat()
    result['input_cutoff_utc']=(late.time if late else noon).isoformat()
    result['method_input_cutoffs']={name:noon.isoformat() for name in result['methods']}
    if late:
        m=DriftFilter(config);prev=None
        for d,y in series:
            if prev and d-prev!=timedelta(days=1):m=DriftFilter(config)
            m.update(y);prev=d
        dt=(late.time-noon).total_seconds()/86400
        pred=m.corrected(late.observed,dt).forecast(tuple(h-dt for h in (1,2,3)))
        result['methods']['adaptive_drift_late_experimental']=[{'target_date':str(day+timedelta(days=h)),'horizon_days':h,**p} for h,p in enumerate(pred,1)]
        result['method_input_cutoffs']['adaptive_drift_late_experimental']=late.time.isoformat()
    result['late_correction_status']='experimental; not validated for operational use'
    return result
