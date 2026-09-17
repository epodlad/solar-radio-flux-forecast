"""Chronological hindcasts. Never tune using the final test period."""
from datetime import timedelta, datetime, timezone
from dataclasses import replace
import math
import numpy as np
from .model import Config, DriftFilter, RegressionFilter

MODELS = (DriftFilter, RegressionFilter)


def hindcast(series, config=Config(), warmup=30, late=None):
    """Reinitialize after missing calendar days; do not turn row steps into days.

    late: optional date -> (UTC datetime, observed sfu), used only AFTER noon
    on that issue date. This experiment is supported for the drift model only.
    """
    if warmup < 2: raise ValueError('warmup must be >=2')
    series = sorted(series)
    if len({d for d,y in series}) != len(series): raise ValueError('duplicate dates')
    values = dict(series)
    models = [cls(config) for cls in MODELS]
    previous = None; n = 0; rows = []
    for date, y in series:
        if previous is not None and date-previous != timedelta(days=1):
            models = [cls(config) for cls in MODELS]; n=0
        change = abs(y-values[previous]) if previous is not None and date-previous==timedelta(days=1) else None
        for model in models: model.update(y)
        n += 1; previous=date
        if n < warmup: continue
        predictions = {m.name:m.forecast() for m in models}
        predictions['persistence'] = [{'mean_sfu':y} for _ in range(3)]
        predictions['recurrence27'] = [{'mean_sfu':values.get(date+timedelta(days=h-27))} for h in (1,2,3)]
        if late and date in late:
            stamp, v = late[date]
            noon = datetime.combine(date, datetime.min.time(),tzinfo=timezone.utc).replace(hour=20)
            dt = (stamp-noon).total_seconds()/86400
            if 0<dt<1 and stamp.date()==date:
                predictions['adaptive_drift_late'] = models[0].corrected(v,dt).forecast(tuple(h-dt for h in (1,2,3)))
        for name, forecasts in predictions.items():
            for h, p in enumerate(forecasts,1):
                target=date+timedelta(days=h)
                if target not in values or p['mean_sfu'] is None: continue
                rows.append({'origin':str(date),'target':str(target),'horizon_days':h,'method':name,
                             'origin_flux':y,'past_absolute_change':change,
                             'actual_sfu':values[target],**p})
    return rows


def metrics(rows):
    if not rows: return {'n':0}
    e=np.array([r['mean_sfu']-r['actual_sfu'] for r in rows])
    d={'n':len(rows),'mae_sfu':float(np.mean(abs(e))),'rmse_sfu':float(np.sqrt(np.mean(e*e))),
       'bias_sfu':float(np.mean(e))}
    probabilistic=[r for r in rows if 'sd_sfu' in r]
    if probabilistic:
        for level in (68,95):
            d['coverage'+str(level)] = float(np.mean([r['interval'+str(level)+'_sfu'][0] <= r['actual_sfu'] <= r['interval'+str(level)+'_sfu'][1] for r in probabilistic]))
        z=np.array([(r['mean_sfu']-r['actual_sfu'])/r['sd_sfu'] for r in probabilistic])
        d['standardized_error_rms']=float(np.sqrt(np.mean(z*z)))
        d['mean_sd_sfu']=float(np.mean([r['sd_sfu'] for r in probabilistic]))
    return d


def summarize(rows, train_values):
    """Activity cutoffs learned from training only; no claimed solar-cycle phase labels."""
    vals=np.array([y for d,y in train_values])
    if len(vals)<31: raise ValueError('At least 31 training observations required')
    qlo,qhi=np.quantile(vals,[1/3,2/3])
    changes=[abs(y-train_values[i-1][1]) for i,(d,y) in enumerate(train_values) if i and d-train_values[i-1][0]==timedelta(days=1)]
    rapid=float(np.quantile(changes,.9))
    grouped={}
    for name in sorted({r['method'] for r in rows}):
        grouped[name]={}
        for h in (1,2,3):
            rr=[r for r in rows if r['method']==name and r['horizon_days']==h]
            # Paired skill relative to persistence on exactly the same origin/target pairs.
            ref={(r['origin'],r['target']):r for r in rows if r['method']=='persistence' and r['horizon_days']==h}
            paired=[r for r in rr if (r['origin'],r['target']) in ref]
            m=metrics(rr)
            baseline=metrics([ref[(r['origin'],r['target'])] for r in paired])
            if baseline.get('rmse_sfu',0)>0:
                m['paired_rmse_skill_vs_persistence']=1-metrics(paired)['rmse_sfu']/baseline['rmse_sfu']
            m['subsets']={
                'quiet':metrics([r for r in rr if r['origin_flux']<=qlo]),
                'active':metrics([r for r in rr if r['origin_flux']>=qhi]),
                'recent_rapid_change':metrics([r for r in rr if r['past_absolute_change'] is not None and r['past_absolute_change']>=rapid])}
            grouped[name][str(h)]=m
    return {'thresholds_from_training':{'quiet_max_sfu':float(qlo),'active_min_sfu':float(qhi),'rapid_change_min_sfu':rapid},'methods':grouped}


def tune(series, base=Config()):
    """Fixed small candidate grid evaluated exclusively in 2013-2016.

    2004-2012 initializes filters; post-2016 data must not enter this function.
    Minimize mean of horizon RMSE, then freeze parameters.
    """
    if any(d.year>2016 for d,y in series): raise ValueError('Test data passed to tuning')
    chosen=base; audit=[]
    grids=[('adaptive_drift','drift_alpha',(0.1,0.25,0.45,0.82)),
           ('adaptive_regression','coefficient_diffusion',(0.001,0.01,0.1))]
    for name,field,candidates in grids:
        scores=[]
        for value in candidates:
            c=replace(chosen,**{field:value})
            rr=[r for r in hindcast(series,c) if '2013-01-01'<=r['origin'] and r['target']<'2017-01-01' and r['method']==name]
            if not rr: raise ValueError('No tuning-period forecast cases')
            score=float(np.mean([metrics([r for r in rr if r['horizon_days']==h])['rmse_sfu'] for h in (1,2,3)]))
            scores.append((score,value)); audit.append({'method':name,'parameter':field,'value':value,'score':score})
        chosen=replace(chosen,**{field:min(scores)[1]})
    return chosen,audit
