from datetime import date,datetime,timedelta,timezone
import copy
import numpy as np
import pytest
from f107forecast.data import parse,daily,HEADER
from f107forecast.model import Config,DriftFilter,RegressionFilter
from f107forecast.forecast import forecast_daily
from f107forecast.validation import hindcast,tune


def series(n=100):return [(date(2020,1,1)+timedelta(days=i),100+10*np.sin(i/9)) for i in range(n)]

@pytest.mark.parametrize('cls',[DriftFilter,RegressionFilter])
def test_flat_sequence(cls):
    m=cls()
    for _ in range(60):m.update(100.)
    pp=m.forecast()
    assert all(abs(p['mean_sfu']-100)<1e-10 for p in pp)
    assert all(p['sd_sfu']>0 for p in pp)
    assert pp[2]['sd_sfu']>=pp[0]['sd_sfu']

@pytest.mark.parametrize('cls',[DriftFilter,RegressionFilter])
def test_forecast_is_pure(cls):
    m=cls()
    for d,y in series():m.update(y)
    assert m.forecast()==m.forecast()


def test_future_cannot_change_past_predictions():
    a=series();b=a[:70]+[(d,y+10000) for d,y in a[70:]]
    ra=hindcast(a);rb=hindcast(b)
    pa={(r['origin'],r['horizon_days'],r['method']):r['mean_sfu'] for r in ra if r['origin']<str(a[70][0])}
    pb={(r['origin'],r['horizon_days'],r['method']):r['mean_sfu'] for r in rb if r['origin']<str(a[70][0])}
    assert pa==pb


def test_gap_resets_warmup_and_targets_are_calendar_dates():
    s=series();s.pop(50)
    rows=hindcast(s)
    assert not any('2020-02-21'<=r['origin']<'2020-03-21' for r in rows)
    assert all((date.fromisoformat(r['target'])-date.fromisoformat(r['origin'])).days==r['horizon_days'] for r in rows)


def test_daily_no_future_or_daily_average():
    txt=HEADER+'\n20200101 170000 2458849 2225 90 91 82\n20200101 200000 2458849 2225 100 101 91\n20200101 230000 2458849 2225 150 151 136'
    obs,rejects=parse(txt)
    assert not rejects
    assert daily(obs)==[(date(2020,1,1),100)]
    assert daily(obs,datetime(2020,1,1,19,tzinfo=timezone.utc))==[]
    assert daily(obs,series='adjusted')[0][1]==101


def test_duplicate_and_invalid_rows():
    row='20200101 200000 2458849 2225 100 101 91'
    obs,rejected=parse(HEADER+'\n'+row+'\n'+row+'\nbad row')
    assert len(obs)==1 and len(rejected)==1
    with pytest.raises(ValueError):parse(HEADER+'\n'+row+'\n'+row.replace('100','200'))
    with pytest.raises(ValueError):parse('<html>Service unavailable</html>')


def test_scalar_hand_calculation():
    # After first observation P=R=4, Q=25, drift=0.
    m=DriftFilter();m.update(100);m.update(110)
    assert m.x==pytest.approx(100+29/33*10)
    assert m.p==pytest.approx(29*4/33)
    assert m.drift==pytest.approx(4.5)
    assert m.q==pytest.approx(.95*25+.05*(100-4-4))


def test_late_update_uses_fractional_time_and_does_not_retrain_drift():
    m=DriftFilter()
    for d,y in series():m.update(y)
    x=m.x;drift=m.drift
    late=m.corrected(x+15,3/24)
    assert m.x==x and late.drift==drift
    assert late.forecast((1-3/24,))[0]['mean_sfu']>m.forecast()[0]['mean_sfu']


def test_tuning_refuses_test_data():
    with pytest.raises(ValueError):tune(series())


def test_insufficient_warmup():
    with pytest.raises(ValueError):forecast_daily(series(29))
