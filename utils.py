from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Optional, Iterable

ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"

def parse_time(ts: str) -> datetime:
    # Expect Zulu ISO. If any offset appears, rely on fromisoformat fallback.
    try:
        if ts.endswith('Z'):
            return datetime.strptime(ts, ISO_FMT).replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(ts.replace('Z','+00:00'))
    except Exception:
        return datetime.fromisoformat(ts.replace('Z','+00:00'))

def to_iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime(ISO_FMT)

def latest_within(records, t: datetime, window_hours: int):
    """
    records: iterable of (time, value). Return value for the latest time within [t-window, t], else None.
    """
    window_start = t - timedelta(hours=window_hours)
    latest_t = None
    latest_val = None
    for rt, val in records:
        if window_start <= rt <= t:
            if latest_t is None or rt > latest_t:
                latest_t, latest_val = rt, val
    return latest_val

def norm_fio2(val, unit: Optional[str]):
    """Return FiO2 as a fraction between 0 and 1. Accepts percent or fraction."""
    if val is None:
        return None
    if unit:
        u = unit.strip().lower()
        if u in ['%', 'percent', 'perc']:
            return float(val) / 100.0
    v = float(val)
    if v > 1.5:
        return v / 100.0
    return v

def safe_float(x):
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None

def round_times_to_observation_ticks(times: Iterable[datetime]) -> list[datetime]:
    uniq = sorted(set(times))
    return uniq

VENT_KEYWORDS = [
    'ventilator', 'mechanical ventilation', 'intubated', 'cpap', 'bipap',
    'high flow', 'oxygen therapy', 'o2 device', 'respiratory support'
]

def looks_like_resp_support(text: str) -> bool:
    if not text:
        return False
    s = text.lower()
    return any(k in s for k in VENT_KEYWORDS)
