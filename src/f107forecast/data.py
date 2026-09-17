"""Penticton only. Preserve every accepted record and explicitly report rejects."""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math
import os
import re
import tempfile
import urllib.request

SOURCE = 'https://www.spaceweather.gc.ca/solar_flux_data/daily_flux_values/fluxtable.txt'
HEADER = 'fluxdate fluxtime fluxjulian fluxcarrington fluxobsflux fluxadjflux fluxursi'

@dataclass(frozen=True)
class Observation:
    time: datetime
    observed: float
    adjusted: float
    ursi: float
    julian: float
    carrington: float

    def json(self):
        d = asdict(self)
        d['time'] = self.time.isoformat()
        return d


def parse(text):
    if HEADER not in ' '.join(text.split()):
        raise ValueError('Missing official Penticton table header')
    records, rejected, by_time = [], [], {}
    for line_number, line in enumerate(text.splitlines(), 1):
        fields = line.split()
        if not fields or fields[0] == 'fluxdate' or set(fields[0]) == {'-'}:
            continue
        try:
            if len(fields) != 7 or not re.fullmatch(r'\d{8}', fields[0]):
                raise ValueError('invalid row format')
            stamp = datetime.strptime(fields[0] + fields[1].zfill(6), '%Y%m%d%H%M%S').replace(tzinfo=timezone.utc)
            vals = [float(v) for v in fields[2:]]
            if not all(math.isfinite(v) and v > 0 for v in vals):
                raise ValueError('nonpositive or nonfinite value')
            obs = Observation(stamp, vals[2], vals[3], vals[4], vals[0], vals[1])
            if stamp in by_time:
                if by_time[stamp] != obs:
                    raise ValueError('conflicting duplicate timestamp')
                continue
            by_time[stamp] = obs
            records.append(obs)
        except ValueError as exc:
            rejected.append({'line': line_number, 'reason': str(exc)})
    if not records:
        raise ValueError('No valid observations')
    # Ambiguous duplicate values must not silently become a forecast input.
    if any('conflicting' in r['reason'] for r in rejected):
        raise ValueError('Conflicting duplicate measurements; inspect source snapshot')
    return sorted(records, key=lambda x: x.time), rejected


def daily(records, cutoff=None, series='observed'):
    if series not in ('observed', 'adjusted'):
        raise ValueError('series must be observed or adjusted')
    # Explicit strict convention: no nearest-time substitution, daily averaging or interpolation.
    return [(r.time.date(), getattr(r, series)) for r in records
            if r.time.hour == 20 and r.time.minute == 0 and r.time.second == 0
            and (cutoff is None or r.time <= cutoff)]


def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def fetch(folder, url=SOURCE):
    """No fallback provider. Validate before replacing a good cached snapshot."""
    if url != SOURCE:
        raise ValueError('Only the configured official Penticton endpoint is supported')
    req = urllib.request.Request(url, headers={'User-Agent': 'SolarRadioFluxForecast/0.1 research'})
    with urllib.request.urlopen(req, timeout=25) as response:
        raw = response.read(10_000_001)
    if len(raw) > 10_000_000:
        raise ValueError('Unexpectedly large response')
    records, rejected = parse(raw.decode('utf-8-sig'))
    now = datetime.now(timezone.utc)
    if any(r.time > now for r in records):
        raise ValueError('Future observation timestamp')
    sha = hashlib.sha256(raw).hexdigest()
    metadata = {'source': url, 'retrieved_at_utc': now.isoformat(), 'sha256': sha,
                'records': len(records), 'rejected': rejected,
                'publication_times_available': False}
    folder = Path(folder)
    atomic_write(folder / 'snapshots' / (sha + '.txt'), raw)
    atomic_write(folder / 'fluxtable.txt', raw)
    atomic_write(folder / 'source.json', json.dumps(metadata, indent=2).encode())
    return records, metadata
