"""Offline coverage audit of the frozen fusion experiment; never fits a model."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import qlib
from qlib.data import D

from build_modern_qlib_provider import normalize_ohlcv


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def summary(frame):
    return dict(rows=len(frame), symbols=frame.ticker.nunique(), sessions=frame.session.nunique(),
                first=str(frame.session.min().date()) if len(frame) else None,
                last=str(frame.session.max().date()) if len(frame) else None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('/Volumes/数据分区/美股自动化交易'))
    parser.add_argument('--provider', type=Path, default=Path.home()/'.qlib/qlib_data/us_modern_liquid100')
    parser.add_argument('--price-csv-dir', type=Path, default=Path.home()/'.qlib/stock_data/source/us_data')
    parser.add_argument('--output', type=Path, default=Path('.cache/reports/fusion_coverage'))
    args = parser.parse_args()
    source, provider, out = args.source.resolve(), args.provider.resolve(), args.output.resolve()
    if out == source or source in out.parents:
        raise ValueError('Diagnostic output must not modify the source checkout')
    out.mkdir(parents=True, exist_ok=True)
    script = source/'scripts/screen_price_quality_fusion.py'
    tree = ast.parse(script.read_text())
    expressions = next(ast.literal_eval(n.value) for n in ast.walk(tree)
                       if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'expressions' for t in n.targets))
    qlib.init(provider_uri=str(provider), region='us', expression_cache=None, dataset_cache=None, kernels=1)
    calendar = pd.DatetimeIndex(D.calendar())
    membership = pd.read_csv(provider/'instruments/liquid100.txt', sep='\t', names=['ticker','start','end'], parse_dates=['start','end'])
    sessions = calendar[(calendar >= '2020-11-02') & (calendar <= '2024-12-31')]
    full = pd.MultiIndex.from_product([membership.ticker.unique(), sessions], names=['ticker','session']).to_frame(index=False)
    full = full.merge(membership, on='ticker', validate='many_to_one')
    full['member'] = full.session.between(full.start, full.end)
    data = D.features(D.instruments('liquid100'), list(expressions.values()), start_time=sessions.min(), end_time=sessions.max())
    data.columns = list(expressions)
    data = data.reset_index().rename(columns={'instrument':'ticker','datetime':'session'})
    full = full.merge(data, on=['ticker','session'], how='left', indicator='provider_join', validate='one_to_one')
    assert (full.member == full.provider_join.eq('both')).all()
    quality_path = source/'.cache/fundamentals/quality_daily.parquet'
    quality = pd.read_parquet(quality_path)
    quality['session'] = pd.to_datetime(quality.session)
    quality['filed_date'] = pd.to_datetime(quality.filed_date)
    full['information_session'] = full.session.map(pd.Series(calendar[:-1], index=calendar[1:]))
    full = full.merge(quality.rename(columns={'session':'information_session'}), on=['ticker','information_session'], how='left', indicator='snapshot_join', validate='one_to_one')
    known = full.filed_date.notna()
    assert (full.loc[known,'filed_date'] <= full.loc[known,'information_session']).all()
    assert (full.loc[known,'information_session'] < full.loc[known,'session']).all()
    pcols = [c for c in expressions if c != 'label']
    qcols = ['roe_ttm','cash_conversion_ttm','debt_to_assets']
    full['raw_debt_to_assets'] = full.debt_to_assets
    full.loc[full.debt_to_assets_source.ne('reported'),'debt_to_assets'] = np.nan
    full[pcols+qcols+['label']] = full[pcols+qcols+['label']].replace([np.inf,-np.inf],np.nan)
    locations = calendar.get_indexer(full.session)
    assert (locations >= 0).all() and (locations+6 < len(calendar)).all()
    full['label_end'] = calendar[locations+6]
    # Read local raw binaries, including their start-index headers, to separate
    # insufficient local history from holes/invalid values inside that history.
    raw_records = []
    csv_records = []
    starts = {}
    for ticker in membership.ticker:
        csv_path = args.price_csv_dir/f'{ticker}.csv'
        csv_frame = normalize_ohlcv(ticker,pd.read_csv(csv_path))
        csv_equal = True
        for field in ['close','high','low','volume']:
            path = provider/'features'/ticker.lower()/f'{field}.day.bin'
            vals = np.fromfile(path, dtype='<f4')
            start = int(vals[0]); values = vals[1:]
            csv_values = csv_frame.reindex(calendar[start:start+len(values)])[field].to_numpy(dtype='float32')
            csv_equal &= bool(np.array_equal(csv_values,values,equal_nan=True))
            valid = np.isfinite(values) & (values > 0)
            indexes = np.flatnonzero(valid)
            raw_records.append(dict(ticker=ticker, field=field, path=str(path), sha256=digest(path),
                                    start_index=start, rows=len(values), nonfinite=int((~np.isfinite(values)).sum()),
                                    nonpositive=int((np.isfinite(values)&(values<=0)).sum()),
                                    first_valid=str(calendar[start+indexes[0]].date()) if len(indexes) else None,
                                    last_valid=str(calendar[start+indexes[-1]].date()) if len(indexes) else None))
            if field == 'close':
                starts[ticker] = start+indexes[0] if len(indexes) else len(calendar)
        csv_records.append(dict(ticker=ticker,path=str(csv_path),sha256=digest(csv_path),rows=len(csv_frame),
                                first=str(csv_frame.index.min().date()),last=str(csv_frame.index.max().date()),ohlcv_binary_equal=csv_equal))
    full['history_sessions'] = locations-full.ticker.map(starts)
    flags = {
        'outside_membership': ~full.member,
        'warmup_252': full.member & full.momentum_12_1.isna() & full.history_sessions.lt(252),
        'other_price_nonfinite': full.member & full[pcols].isna().any(axis=1) & ~(full.momentum_12_1.isna() & full.history_sessions.lt(252)),
        'missing_snapshot': full.snapshot_join.ne('both'),
        'missing_ttm_ratios': full[['roe_ttm','cash_conversion_ttm']].isna().any(axis=1),
        'missing_leverage_value': full.raw_debt_to_assets.isna(),
        'nonreported_leverage': full.debt_to_assets_source.ne('reported'),
        'nonfinite_label': full.label.isna(),
    }
    for name, mask in flags.items(): full[name] = mask
    complete = full[pcols+qcols+['label']].notna().all(axis=1)
    full['complete'] = complete
    folds, waterfall, period_rows, overlap, features = [], [], [], [], []
    for year, expected in [(2022,2304),(2023,18739),(2024,35651)]:
        for segment in ['train','validation']:
            end = pd.Timestamp(year-1 if segment=='train' else year,12,31)
            period = full.session.le(end) if segment=='train' else full.session.between(pd.Timestamp(year,1,1),end)
            masks = dict(flags, boundary_purge=full.label_end.gt(end))
            keep = period.copy()
            for stage, mask in [('all_universe_cells',pd.Series(False,index=full.index)),*masks.items()]:
                removed = keep & mask
                keep &= ~mask
                waterfall.append(dict(year=year,segment=segment,stage=stage,exclusive_loss=int(removed.sum()),
                                      overlapping_loss=int((period & (True if stage=='outside_membership' else full.member) & mask).sum()), **summary(full[keep])))
                for frequency in ['M','Y']:
                    buckets = full.session.dt.to_period(frequency)
                    for bucket in sorted(buckets[period].unique()):
                        group = full[keep & buckets.eq(bucket)]
                        period_rows.append(dict(year=year,segment=segment,stage=stage,frequency=frequency,period=str(bucket),**summary(group)))
            assert keep.equals(period & full.member & complete & full.label_end.le(end))
            if segment=='train': assert int(keep.sum()) == expected
            folds.append(dict(year=year,segment=segment,total=int((period&full.member).sum()), **summary(full[keep]),
                              price_only_rows=int((period&full.member&full[pcols+['label']].notna().all(axis=1)&full.label_end.le(end)).sum()),
                              quality_only_rows=int((period&full.member&full[qcols+['label']].notna().all(axis=1)&full.label_end.le(end)).sum())))
            for a, ma in masks.items():
                for b, mb in masks.items():
                    overlap.append(dict(year=year,segment=segment,reason_a=a,reason_b=b,rows=int((period&full.member&ma&mb).sum())))
            for col in pcols+qcols+['label']:
                features.append(dict(year=year,segment=segment,feature=col,missing_rows=int((period&full.member&full[col].isna()).sum()),**summary(full[period&full.member&full[col].notna()])))
    for name, rows in [('folds',folds),('waterfall',waterfall),('period_stages',period_rows),('overlap',overlap),('feature_coverage',features),('provider_files',raw_records),('price_csv_trace',csv_records)]:
        pd.DataFrame(rows).to_csv(out/f'{name}.csv',index=False)
    full.to_parquet(out/'eligibility.parquet',index=False)
    full[full.member].groupby('ticker')[list(flags)[1:]].sum().to_csv(out/'ticker_losses.csv')
    paths = [script,quality_path,source/'.cache/fundamentals/sec_facts.parquet', source/'.cache/reports/price_quality_fusion/results.json',provider/'calendars/day.txt',provider/'instruments/liquid100.txt']
    manifest = dict(inputs={str(p):digest(p) for p in paths}, calendar_first=str(calendar.min().date()),calendar_last=str(calendar.max().date()),
                    universe_symbols=len(membership),expressions=expressions,folds=folds,
                    interpretation='Offline reproduction; overlapping reasons are not additive. All artifacts are new; no fitting, orders or downloads.')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2,default=int)+'\n')
    print(pd.DataFrame(folds).to_string(index=False),flush=True)


if __name__ == '__main__':
    main()
