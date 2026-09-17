from datetime import datetime,timezone
import time
from fastapi.testclient import TestClient
from f107forecast import api
from f107forecast.data import HEADER


def test_unavailable_is_explicit(tmp_path,monkeypatch):
    s=api.Store(tmp_path);s.next_check_utc=api.next_check(datetime.now(timezone.utc))
    monkeypatch.setattr(api,'store',s)
    c=TestClient(api.app)
    assert c.get('/health').status_code==200
    assert c.get('/api/forecast').status_code==503
    assert c.get('/api/status').json()['status']=='degraded'
    assert c.get('/').status_code==200


def test_failed_refresh_keeps_cache(tmp_path,monkeypatch):
    from f107forecast.data import parse
    from datetime import date,timedelta
    text=HEADER+'\n'+'\n'.join(f'{date(2020,1,1)+timedelta(days=i):%Y%m%d} 200000 2458850 2225 100 101 91' for i in range(40))
    rec,_=parse(text)
    s=api.Store(tmp_path);s.calculate(rec,{'sha256':'test','retrieved_at_utc':None})
    expected=s.result['forecast_id']
    def fail(*a,**k):raise TimeoutError()
    monkeypatch.setattr(api,'fetch_noaa',fail);s.refresh()
    assert s.result['forecast_id']==expected and s.error=='TimeoutError'
    assert s.status()['status']=='degraded'


def test_duplicate_snapshot_does_not_recalculate(tmp_path,monkeypatch):
    from f107forecast.data import parse
    from datetime import date,timedelta
    text=HEADER+'\n'+'\n'.join(f'{date(2020,1,1)+timedelta(days=i):%Y%m%d} 200000 2458850 2225 100 101 91' for i in range(40))
    rec,_=parse(text);meta={'sha256':'same','retrieved_at_utc':'first'}
    s=api.Store(tmp_path);s.calculate(rec,meta)
    first=s.result['provenance']['calculation_time_utc']
    monkeypatch.setattr(api,'fetch_noaa',lambda *a:(rec,{**meta,'retrieved_at_utc':'second'}))
    s.refresh()
    assert s.result['provenance']['calculation_time_utc']==first
    assert len(list((tmp_path/'forecasts').glob('*.json')))==1


def test_noon_evening_and_morning_issue_policy():
    from f107forecast.data import parse
    from f107forecast.operational import make_issue
    from datetime import date,timedelta
    text=HEADER+'\n'+'\n'.join(f'{date(2020,1,1)+timedelta(days=i):%Y%m%d} 200000 2458850 2225 100 101 91' for i in range(40))
    rec,_=parse(text)
    noon=make_issue(rec)
    evening,_=parse(text+'\n20200209 220000 2458850 2225 110 111 100')
    late=make_issue(evening)
    assert late['issue_stage']=='evening' and noon['issue_stage']=='noon'
    assert late['forecast_id']!=noon['forecast_id']
    assert late['methods']['adaptive_regression']==noon['methods']['adaptive_regression']
    assert 'adaptive_drift_late_experimental' in late['methods']
    morning,_=parse(text+'\n20200209 220000 2458850 2225 110 111 100\n20200210 180000 2458850 2225 112 113 102')
    assert make_issue(morning)['forecast_id']==late['forecast_id']


def test_seasonal_check_schedule():
    from datetime import datetime,timezone
    def t(v):return datetime.fromisoformat(v).replace(tzinfo=timezone.utc)
    assert api.next_check(t('2026-09-17T20:45'))==t('2026-09-17T23:45')
    assert api.next_check(t('2026-11-01T20:45'))==t('2026-11-01T22:45')
    assert api.next_check(t('2026-10-31T23:45'))==t('2026-11-01T20:45')

def test_requests_do_not_poll_source_before_scheduled_time(tmp_path,monkeypatch):
    s=api.Store(tmp_path)
    s.next_check_utc=api.next_check(datetime.now(timezone.utc))
    def forbidden(*args):raise AssertionError('unexpected source fetch')
    monkeypatch.setattr(api,'fetch_noaa',forbidden)
    s.refresh()
    assert s.error is None
