"""NOAA-distributed Canadian F10.7. No mixing with Canadian archive values."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import hashlib,json,math,urllib.request
from .data import Observation,atomic_write
SOURCE='https://services.swpc.noaa.gov/json/f107_cm_flux.json'

def parse_noaa(payload):
    rows=json.loads(payload) if isinstance(payload,(str,bytes)) else payload
    if not isinstance(rows,list):raise ValueError('Expected NOAA list')
    selected={}
    for row in rows:
        if row.get('frequency')!=2800 or row.get('reporting_schedule')!='Noon':continue
        stamp=datetime.fromisoformat(row['time_tag'].replace('Z','+00:00'))
        if stamp.tzinfo is None:stamp=stamp.replace(tzinfo=timezone.utc)
        stamp=stamp.astimezone(timezone.utc)
        if (stamp.hour,stamp.minute,stamp.second)!=(20,0,0):raise ValueError('Unexpected NOAA noon timestamp')
        v=float(row['flux'])
        if not math.isfinite(v) or v<=0:raise ValueError('Invalid NOAA flux')
        if stamp in selected and selected[stamp].observed!=v:raise ValueError('Conflicting NOAA rows')
        selected[stamp]=Observation(stamp,v,None,None,None,None)
    if not selected:raise ValueError('No NOAA noon observations')
    return sorted(selected.values(),key=lambda r:r.time)

def fetch_noaa(folder):
    with urllib.request.urlopen(SOURCE,timeout=25) as response:raw=response.read(2_000_001)
    if len(raw)>2_000_000:raise ValueError('Oversize NOAA response')
    incoming=parse_noaa(raw);now=datetime.now(timezone.utc)
    if any(r.time>now for r in incoming):raise ValueError('Future NOAA timestamp')
    path=Path(folder)/'noaa_cache.json';merged={}
    if path.exists():
        previous=json.loads(path.read_text())
        for r in parse_noaa(previous['rows']):merged[r.time]=r
    # Revisions from the same provider replace earlier values; never merge providers.
    merged.update({r.time:r for r in incoming})
    records=[r for t,r in sorted(merged.items()) if t>=now-timedelta(days=90)]
    rows=[{'time_tag':r.time.isoformat(),'frequency':2800,'reporting_schedule':'Noon','flux':r.observed} for r in records]
    meta={'source':SOURCE,'provider':'NOAA SWPC','measurement_origin':'Canadian Solar Radio Monitoring Program / Penticton',
          'series':'NOAA-reported F10.7 noon flux; provider precision retained',
          'retrieved_at_utc':now.isoformat(),'sha256':hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest(),
          'download_sha256':hashlib.sha256(raw).hexdigest(),'retention_days':90,
          'selection':'Noon at 20:00 UTC only; intraday correction disabled pending timestamp reconciliation',
          'publication_times_available':False}
    atomic_write(path,json.dumps({'rows':rows,'metadata':meta},allow_nan=False).encode())
    return records,meta
