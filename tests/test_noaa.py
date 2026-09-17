import pytest
from f107forecast.noaa import parse_noaa

def test_noaa_preserves_noon_and_afternoon_without_inventing_adjusted_flux():
    rows=[{'time_tag':'2026-09-16T20:00:00','frequency':2800,'flux':100,'reporting_schedule':'Noon'},
          {'time_tag':'2026-09-16T22:00:00','frequency':2800,'flux':101,'reporting_schedule':'Afternoon'}]
    result=parse_noaa(rows)
    assert len(result)==2 and result[0].observed==100 and result[0].adjusted is None
    rows.append({**rows[0],'flux':99})
    with pytest.raises(ValueError,match='Conflicting'):parse_noaa(rows)

def test_noaa_does_not_silently_relabel_noon_time():
    with pytest.raises(ValueError,match='timestamp'):
        parse_noaa([{'time_tag':'2026-09-16T19:00:00','frequency':2800,'flux':100,'reporting_schedule':'Noon'}])


def test_afternoon_timestamp_preserved_and_ambiguity_rejected():
    noon={'time_tag':'2026-09-16T20:00:00','frequency':2800,'flux':100,'reporting_schedule':'Noon'}
    late={**noon,'time_tag':'2026-09-16T22:00:00','reporting_schedule':'Afternoon','flux':103}
    rows=parse_noaa([noon,late])
    assert rows[-1].time.hour==22
    with pytest.raises(ValueError,match='Ambiguous'):
        parse_noaa([noon,late,{**late,'time_tag':'2026-09-16T23:00:00'}])


def test_cache_roundtrip_and_revised_afternoon_tag(tmp_path,monkeypatch):
    import json
    from datetime import datetime,timezone
    from f107forecast import noaa
    from datetime import timedelta
    day=(datetime.now(timezone.utc)-timedelta(days=3)).date().isoformat()
    rows=[{'time_tag':day+'T20:00:00','frequency':2800,'flux':100,'reporting_schedule':'Noon'},
          {'time_tag':day+'T22:00:00','frequency':2800,'flux':103,'reporting_schedule':'Afternoon'}]
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,*args):return json.dumps(rows).encode()
    monkeypatch.setattr(noaa.urllib.request,'urlopen',lambda *a,**k:Response())
    rec,_=noaa.fetch_noaa(tmp_path)
    assert rec==parse_noaa(json.loads((tmp_path/'noaa_cache.json').read_text())['rows'])
    rows[-1]['time_tag']=day+'T23:00:00'
    rec,_=noaa.fetch_noaa(tmp_path)
    assert len(rec)==2 and rec[-1].time.hour==23
