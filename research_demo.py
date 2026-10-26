"""Offline normalization and temporal-validation demonstration on authored facts."""
from __future__ import annotations
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import pandas as pd
from us_quant.fundamentals import extract_canonical_facts, build_daily_quality_snapshot
from us_quant.provider_audit import parse_calendar, read_instrument_symbols
from us_quant.validation import audit_label_endpoints

ROOT = Path(__file__).resolve().parent
METRICS = ['net_income_ttm', 'roe_ttm', 'cash_conversion_ttm', 'debt_to_assets']


def information_panel(facts, fixture):
    sessions = fixture['sessions']
    daily = build_daily_quality_snapshot(facts, sessions)
    lookup = {(r['session'].date().isoformat(), r['ticker']): r for r in daily.to_dict('records')}
    panel = []
    for i, signal in enumerate(sessions):
        information = sessions[i - 1] if i else None
        for issuer in fixture['issuers']:
            row = lookup.get((information, issuer['ticker']))
            item = {'signal_session': signal, 'information_session': information,
                    'ticker': issuer['ticker'], 'filed_date': None, 'accession_number': None,
                    'status': 'NOT_YET_AVAILABLE', 'metrics': dict.fromkeys(METRICS),
                    'observed_metrics': dict.fromkeys(METRICS), 'ttm_source': None,
                    'debt_to_assets_source': None}
            if row is not None:
                assert row['filed_date'] <= pd.Timestamp(information) < pd.Timestamp(signal)
                item.update(filed_date=row['filed_date'].date().isoformat(),
                            accession_number=row['accession_number'],
                            ttm_source=row['ttm_source'], debt_to_assets_source=row['debt_to_assets_source'])
                item['observed_metrics'] = {key: None if pd.isna(row[key]) else round(float(row[key]), 12) for key in METRICS}
                if issuer.get('declared_missing_fields'):
                    item.update(status='INVALID_DECLARED_GAP', gap_reason=issuer['gap_reason'],
                                declared_missing_fields=issuer['declared_missing_fields'])
                elif any(v is None for v in item['observed_metrics'].values()):
                    item['status'] = 'INVALID_INCOMPLETE_INPUT'
                else:
                    item.update(status='VALID', metrics=item['observed_metrics'].copy())
            panel.append(item)
    return panel


def run():
    source = ROOT / 'examples/research-fixture.json'
    fixture = json.loads(source.read_text())
    sessions = fixture['sessions']
    provider = ROOT / 'examples/provider'
    calendar = parse_calendar(provider)
    calendar_values = (provider / 'calendars/day.txt').read_text().splitlines()
    symbols = read_instrument_symbols(provider / 'instruments/synthetic.txt')
    assert sessions == calendar_values
    assert symbols == {i['ticker'] for i in fixture['issuers']}
    facts = pd.concat([extract_canonical_facts(i['ticker'], i['cik'], i['companyfacts']) for i in fixture['issuers']], ignore_index=True)
    panel = information_panel(facts, fixture)
    without_amendment = facts.loc[facts['accession_number'] != 'SYN-Q2-AMEND']
    earlier = information_panel(without_amendment, fixture)
    cutoff = sessions[9]
    assert [r for r in panel if r['signal_session'] < cutoff] == [r for r in earlier if r['signal_session'] < cutoff]
    a = {r['signal_session']: r for r in panel if r['ticker'] == 'SYN_A'}
    assert a[sessions[2]]['metrics']['net_income_ttm'] == 100
    assert a[sessions[6]]['metrics']['net_income_ttm'] == 110
    assert a[sessions[8]]['metrics']['net_income_ttm'] == 110
    assert a[sessions[9]]['metrics']['net_income_ttm'] == 120
    # Deliberately wrong latest-record join: an independent expected early value catches it.
    leaky_early_value = a[sessions[-1]]['metrics']['net_income_ttm']
    assert leaky_early_value != 100
    assert facts.loc[(facts.ticker == 'SYN_A') & (facts.accession_number == 'SYN-FY') & (facts.field == 'revenue'), 'value'].tolist() == [400]
    assert len(panel) == 24
    assert all(all(v is None for v in r['metrics'].values()) for r in panel if r['status'] == 'INVALID_DECLARED_GAP')
    split_rows = []
    lookup = {(r['signal_session'], r['ticker']): r for r in panel}
    for name, start, end in [('train', 0, 5), ('validation', 6, 9)]:
        audit = audit_label_endpoints(sessions, sessions[start:end+1], sessions[end])
        assert sum(r['status'] == 'INVALID_BOUNDARY' for r in audit) == 2
        for row in audit:
            for symbol in sorted(symbols):
                available = lookup[row['session'], symbol]
                split_rows.append({'split': name, 'ticker': symbol, **row,
                                   'availability_status': available['status'],
                                   'eligible': True if row['status'] == 'VALID' and available['status'] == 'VALID' else None})
    # Deliberately malformed calendars / unknown sample dates must fail clearly.
    guards = []
    for calendar_input, sample in [(sessions[::-1], [sessions[0]]),
                                   ([sessions[0], *sessions], [sessions[0]]),
                                   (sessions, ['1999-01-01'])]:
        try:
            audit_label_endpoints(calendar_input, sample, sessions[5])
        except ValueError:
            guards.append(True)
        else:
            raise AssertionError('Invalid calendar input was accepted')
    tail = audit_label_endpoints(sessions, sessions[-2:], sessions[-1])
    assert all(r['status'] == 'INVALID_CALENDAR_COVERAGE' and r['label_end'] is None for r in tail)
    paths = ['RESEARCH_PROTOCOL.md', 'examples/research-fixture.json', 'examples/provider/calendars/day.txt', 'examples/provider/instruments/synthetic.txt']
    return {'scope': 'Synthetic research engineering; no fitted model or market evidence',
            'sha256': {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in paths},
            'provider': {**asdict(calendar), 'symbols': sorted(symbols), 'calendar_kind': 'authored synthetic session list'},
            'canonical_facts': json.loads(facts.to_json(orient='records', date_format='iso', double_precision=12)),
            'information_panel': panel, 'panel_status_counts': dict(Counter(r['status'] for r in panel)),
            'split_audit': split_rows, 'split_status_counts': dict(Counter(r['status'] for r in split_rows)),
            'eligible_cells': sum(r['eligible'] is True for r in split_rows),
            'reserved_sessions_not_scored': sessions[10:],
            'negative_control': {'early_expected_income_ttm': 100, 'wrong_latest_join_income_ttm': leaky_early_value, 'leak_detected': True},
            'checks': {'prefix_invariance': True, 'tag_precedence': True, 'ttm_bridge': True,
                       'next_session_amendment_visibility': True, 'full_grid_retained': True,
                       'declared_gaps_null': True, 'boundary_purge': True, 'calendar_guards': all(guards),
                       'missing_endpoint_guard': True}}


if __name__ == '__main__':
    if not __debug__:
        raise SystemExit('Run without -O to retain verification assertions')
    print(json.dumps(run(), sort_keys=True, indent=2, allow_nan=False))
