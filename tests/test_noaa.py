import pytest
from f107forecast.noaa import parse_noaa

def test_noaa_selects_noon_without_inventing_adjusted_flux():
    rows=[{'time_tag':'2026-09-16T20:00:00','frequency':2800,'flux':100,'reporting_schedule':'Noon'},
          {'time_tag':'2026-09-16T22:00:00','frequency':2800,'flux':101,'reporting_schedule':'Afternoon'}]
    result=parse_noaa(rows)
    assert len(result)==1 and result[0].observed==100 and result[0].adjusted is None
    rows.append({**rows[0],'flux':99})
    with pytest.raises(ValueError,match='Conflicting'):parse_noaa(rows)

def test_noaa_does_not_silently_relabel_noon_time():
    with pytest.raises(ValueError,match='timestamp'):
        parse_noaa([{'time_tag':'2026-09-16T19:00:00','frequency':2800,'flux':100,'reporting_schedule':'Noon'}])
