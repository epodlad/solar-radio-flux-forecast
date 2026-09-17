"""Single-worker FastAPI service. Network refresh is bounded, cached and serialized."""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
import asyncio
import hashlib
import json
import logging
import os
import threading
import time
from fastapi import FastAPI, HTTPException
from starlette.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from . import __version__
from .data import fetch, parse, daily, atomic_write
from .noaa import fetch_noaa, parse_noaa
from .forecast import forecast_daily
from .model import Config
from .operational import make_issue

log = logging.getLogger('f107')

class Store:
    def __init__(self,folder=None):
        self.folder=Path(folder or os.getenv('F107_DATA_DIR','data'))
        self.lock=threading.Lock();self.checked=0.;self.error=None;self.result=None;self.observations=[];self.meta={}
        self.ttl=max(60,int(os.getenv('F107_REFRESH_SECONDS','300')))
        self.provider=os.getenv('F107_PROVIDER','noaa')
        if self.provider not in ('noaa','canada'):raise ValueError('Unknown F107_PROVIDER')
        self.config=Config()
        config_path=Path(os.getenv('F107_CONFIG','results/config.json'))
        if config_path.exists():self.config=Config(**json.loads(config_path.read_text()))
        self.load_cache()
    def load_cache(self):
        if self.provider=='noaa':
            path=self.folder/'noaa_cache.json'
            if path.exists():
                try:
                    cached=json.loads(path.read_text());self.calculate(parse_noaa(cached['rows']),cached['metadata'],archive=False)
                except Exception as exc:self.error=type(exc).__name__
            return
        path=self.folder/'fluxtable.txt'
        if not path.exists():return
        try:
            records,_=parse(path.read_text())
            meta_path=self.folder/'source.json'
            meta=json.loads(meta_path.read_text()) if meta_path.exists() else {'retrieved_at_utc':None,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'source_status':'unverified local snapshot'}
            if meta['sha256']!=hashlib.sha256(path.read_bytes()).hexdigest():raise ValueError('cache hash mismatch')
            self.calculate(records,meta,archive=False)
        except Exception as exc:self.error=type(exc).__name__;log.warning('Cached data could not be loaded: %s',type(exc).__name__)
    def calculate(self,records,meta,archive=True):
        now=datetime.now(timezone.utc)
        records=[r for r in records if r.time<=now]
        result=make_issue(records,self.config)
        unchanged=self.result is not None and self.result["forecast_id"]==result["forecast_id"]
        if unchanged:
            self.observations=records;self.meta=meta
            self.result["latest_measurement"]=records[-1].json()
            self.result["provenance"]["retrieved_at_utc"]=meta.get("retrieved_at_utc")
            self.result["provenance"]["last_checked_snapshot_sha256"]=meta["sha256"]
            return
        result['latest_measurement']=records[-1].json()
        result['provenance']={**meta,'software_version':__version__,'git_commit':os.getenv('RENDER_GIT_COMMIT','unversioned'),
                              'calculation_time_utc':now.isoformat(),'status':'research prototype',
                              'late_correction':'experimental separate result; noon methods preserved'}
        identity=result['forecast_id']
        result['forecast_id']=identity
        if archive:
            p=self.folder/'forecasts'/(identity+'.json')
            if not p.exists():atomic_write(p,json.dumps(result,allow_nan=False).encode())
            from datetime import timedelta
            for old in (self.folder/'forecasts').glob('*.json'):
                if old.stat().st_mtime < (now-timedelta(days=30)).timestamp():old.unlink()
        self.result=result;self.observations=records;self.meta=meta
    def refresh(self):
        if time.monotonic()-self.checked<self.ttl:return
        if not self.lock.acquire(blocking=False):return
        try:
            if time.monotonic()-self.checked<self.ttl:return
            self.checked=time.monotonic()
            records,meta=(fetch_noaa if self.provider=='noaa' else fetch)(self.folder)
            if self.result is None or meta['sha256']!=self.meta.get('sha256'):
                self.calculate(records,meta)
            else:
                self.meta=meta;self.result['provenance']['retrieved_at_utc']=meta['retrieved_at_utc']
            self.error=None
        except Exception as exc:
            self.error=type(exc).__name__;log.warning('Penticton refresh failed; keeping last successful forecast: %s',type(exc).__name__)
        finally:self.lock.release()
    def status(self):
        age=None
        if self.observations:age=(datetime.now(timezone.utc)-self.observations[-1].time).total_seconds()/3600
        return {'status':'ok' if self.result and not self.error and age is not None and age<=48 else 'degraded',
                'forecast_available':self.result is not None,'latest_measurement_age_hours':age,
                'source_error':self.error,'storage_durable':os.getenv('F107_DURABLE_STORAGE','false')=='true',
                'scheduled_updates_guaranteed':False,'poll_interval_seconds':self.ttl,
                'issue_policy':'noon and evening when new inputs arrive; source corrections create revised issues'}

store=Store()

@asynccontextmanager
async def lifespan(app):
    async def poll():
        while True:
            await asyncio.to_thread(store.refresh)
            await asyncio.sleep(store.ttl)
    task=asyncio.create_task(poll())
    yield
    task.cancel()
    try:await task
    except asyncio.CancelledError:pass

app=FastAPI(title='Solar Radio Flux Forecast',version=__version__,lifespan=lifespan,
            description='Independent research software. Penticton observed F10.7, sfu; UTC timestamps. Not an official forecast.')

app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=5)

@app.get('/')
def home():return FileResponse(Path(__file__).parent/'static'/'index.html')

@app.get('/logo.png')
def logo():return FileResponse(Path(__file__).parent/'static'/'logo.png', headers={'Cache-Control':'public, max-age=86400'})

@app.get('/health')
def health():
    # Liveness: no download, forecast or scientific readiness assertion.
    return {'status':'alive','version':__version__}

@app.get('/api/status')
def status():return store.status()

def ready():
    store.refresh()
    if store.result is None:raise HTTPException(503,'No verified forecast available; Penticton data unavailable or insufficient warmup')

@app.get('/api/forecast')
def forecast():
    ready();return {**store.result,'service_status':store.status()}

@app.get('/api/latest')
def latest():
    ready();return {'observation':store.observations[-1].json(),'units':'sfu','source':store.meta,'service_status':store.status()}

@app.get('/api/history')
def history(days:int=30):
    if not 1<=days<=365:raise HTTPException(422,'days must be 1..365')
    ready()
    from datetime import timedelta
    cutoff=store.observations[-1].time-timedelta(days=days)
    return {'units':'sfu','series':'observed','observations':[r.json() for r in store.observations if r.time>=cutoff]}

@app.get('/api/provenance')
def provenance():
    ready();return store.result['provenance']

@app.get('/api/validation')
def validation():
    path=Path(os.getenv('F107_VALIDATION','results/validation.json'))
    if not path.exists():raise HTTPException(503,'Historical validation has not been generated')
    return json.loads(path.read_text())

@app.get('/api/backtest')
def backtest():
    """Retrospective last 30 days, cached by noon-data identity; not issued forecasts."""
    ready()
    from .validation import hindcast,metrics
    from datetime import timedelta
    series=daily(store.observations)
    key=hashlib.sha256(json.dumps([(str(d),v) for d,v in series]).encode()).hexdigest()
    cached=getattr(store,'backtest_cache',None)
    if cached and cached[0]==key:return cached[1]
    rows=hindcast(series,store.config)
    cutoff=str(series[-1][0]-timedelta(days=29))
    rows=[r for r in rows if r['origin']>=cutoff]
    methods={m:{str(h):metrics([r for r in rows if r['method']==m and r['horizon_days']==h]) for h in (1,2,3)} for m in sorted({r['method'] for r in rows})}
    result={'status':'retrospective archive-vintage hindcast, NOT archived issued forecasts',
            'period_start':cutoff,'period_end':str(series[-1][0]),'methods':methods,'rows':rows}
    store.backtest_cache=(key,result)
    return result
