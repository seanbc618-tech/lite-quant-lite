"""Generic endpoint audit adapted from the existing Alpha360 diagnostic loop.

No models, provider paths, private parameters or strategy selection are included.
"""
from __future__ import annotations
import pandas as pd


def audit_label_endpoints(sessions, sample_sessions, segment_end, horizon=1):
    calendar = pd.DatetimeIndex(sessions)
    dates = pd.DatetimeIndex(sample_sessions)
    if calendar.empty or calendar.hasnans or not calendar.is_unique or not calendar.is_monotonic_increasing:
        raise ValueError('Calendar must be nonempty, unique and increasing, without NaT')
    if not isinstance(horizon, int) or isinstance(horizon, bool) or horizon < 1:
        raise ValueError('horizon must be a positive integer')
    boundary = pd.Timestamp(segment_end)
    if boundary not in calendar:
        raise ValueError('Segment boundary must be in the calendar')
    locations = calendar.get_indexer(dates)
    if (locations < 0).any():
        raise ValueError('Sample date missing from calendar')
    if (dates > boundary).any():
        raise ValueError('Sample date exceeds its segment boundary')
    # Same t+1 entry / t+horizon+1 endpoint rule as the source diagnostic.
    end_locations = locations + horizon + 1
    within = end_locations < len(calendar)
    within[within] = calendar[end_locations[within]] <= boundary
    return [{'session': date.date().isoformat(),
             'label_end': calendar[end].date().isoformat() if end < len(calendar) else None,
             'status': ('VALID' if keep else 'INVALID_BOUNDARY') if end < len(calendar)
                       else 'INVALID_CALENDAR_COVERAGE'}
            for date, end, keep in zip(dates, end_locations, within)]
