"""Trace frozen SEC gaps to local raw cache and measure a bounded currency fix."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from diagnose_fusion_coverage import digest, summary
from build_sec_fundamentals import cached_submission_cik
from us_quant.fundamentals import (
    ACCEPTED_FORMS, FIELD_TAGS, build_cik_mapping, build_daily_quality_snapshot,
    extract_canonical_facts,
)


def raw_records(payload, field):
    return [dict(r, taxonomy=taxonomy, tag=tag, unit=unit)
            for taxonomy, tag in FIELD_TAGS[field]
            for unit, records in payload.get('facts', {}).get(taxonomy, {}).get(tag, {}).get('units', {}).items()
            for r in records]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('/Volumes/数据分区/美股自动化交易'))
    parser.add_argument('--output', type=Path, default=Path('.cache/reports/fusion_coverage'))
    args = parser.parse_args()
    source, out = args.source.resolve(), args.output.resolve()
    if out == source or source in out.parents:
        raise ValueError('Never write diagnostic output to the frozen source checkout')
    raw = source/'.cache/sec/raw'
    mapping_path = raw/'ticker_mapping.json'
    mapping = build_cik_mapping(json.loads(mapping_path.read_text()))
    panel = pd.read_parquet(out/'eligibility.parquet')
    facts = pd.read_parquet(source/'.cache/fundamentals/sec_facts.parquet')
    daily = pd.read_parquet(source/'.cache/fundamentals/quality_daily.parquet')
    hashes = {str(mapping_path):digest(mapping_path)}
    payloads, inventories, rebuild = {}, [], []
    for ticker in sorted(panel.ticker.unique()):
        cik = mapping.get(ticker)
        path = raw/str(cik)/'companyfacts.json'
        if not cik or not path.exists():
            inventories.append(dict(ticker=ticker,cik=cik,raw_exists=False,field=None,unit=None,rows=0))
            continue
        hashes[str(path)] = digest(path)
        payload = json.loads(path.read_text())
        payloads[ticker] = payload
        normalized = extract_canonical_facts(ticker,cik,payload)
        original = facts[facts.ticker.eq(ticker)]
        # Compare as a multiset; ordering and parquet dtypes are not provenance.
        def canonical(frame):
            return sorted(frame.fillna('<null>').astype(str).apply(tuple,axis=1).tolist())
        equal = canonical(normalized) == canonical(original)
        rebuild.append(dict(ticker=ticker,raw_rows=len(normalized),frozen_rows=len(original),equal=equal))
        assert equal, f'Normalized cache differs from raw rebuild: {ticker}'
        print(f'{ticker}: raw normalization matches frozen facts ({len(original)} rows)',flush=True)
        for field in FIELD_TAGS:
            records = raw_records(payload,field)
            for unit in sorted({r['unit'] for r in records}):
                rs = [r for r in records if r['unit']==unit and r.get('form') in ACCEPTED_FORMS]
                inventories.append(dict(ticker=ticker,cik=cik,raw_exists=True,field=field,unit=unit,rows=len(rs),
                                        first_filed=min((r['filed'] for r in rs),default=None),
                                        last_filed=max((r['filed'] for r in rs),default=None)))
            if not records:
                inventories.append(dict(ticker=ticker,cik=cik,raw_exists=True,field=field,unit=None,rows=0))
    pd.DataFrame(inventories).to_csv(out/'raw_field_inventory.csv',index=False)
    pd.DataFrame(rebuild).to_csv(out/'raw_rebuild_check.csv',index=False)
    # The current mapping omitted EA despite cached SEC issuer identity and facts.
    ea_cik = cached_submission_cik(raw,'EA')
    assert 'EA' not in mapping and ea_cik == '0000712515'
    ea_raw, ea_identity = raw/ea_cik/'companyfacts.json', raw/ea_cik/'submissions.json'
    hashes.update({str(p):digest(p) for p in [ea_raw,ea_identity]})
    ea_facts = extract_canonical_facts('EA',ea_cik,json.loads(ea_raw.read_text()))
    ea_daily = build_daily_quality_snapshot(ea_facts,daily.session.unique())
    ea_facts.to_parquet(out/'ea_recovered_facts.parquet',index=False)
    ea_daily.to_parquet(out/'ea_recovered_snapshots.parquet',index=False)
    (out/'ea_mapping_evidence.json').write_text(json.dumps(dict(current_mapping_has_EA=False,
        submissions_path=str(ea_identity),submissions_tickers=json.loads(ea_identity.read_text())['tickers'],
        cik=ea_cik,raw_path=str(ea_raw),recovered_fact_rows=len(ea_facts)),indent=2)+'\n')
    # Every excluded reported-leverage filing is checked in ALL cached currencies.
    leverage = []
    bad = panel[panel.member & panel.snapshot_join.eq('both') & panel.nonreported_leverage]
    for (ticker, accn, period_end), group in bad.groupby(['ticker','accession_number','period_end']):
        matches = [r for r in raw_records(payloads[ticker],'total_liabilities')
                   if r.get('accn')==accn and r.get('end')==str(period_end.date())]
        leverage.append(dict(ticker=ticker,accession_number=accn,period_end=str(period_end.date()),
                             raw_matching_liabilities=len(matches),
                             status='INVALID_DECLARED_GAP' if not matches else 'UNVERIFIED_EXTRACTION_OR_CALCULATION',
                             scope='Direct total-liabilities fact in this cached filing and period; no claim about all SEC disclosures',
                             source=str(raw/mapping[ticker]/'companyfacts.json'), **summary(group)))
    pd.DataFrame(leverage).to_csv(out/'leverage_source_gaps.csv',index=False)
    calculations = []
    for (ticker,accn,period_end), group in panel[panel.member & panel.snapshot_join.eq('both') & panel.missing_ttm_ratios].groupby(['ticker','accession_number','period_end']):
        row = group.iloc[0]
        current = facts[facts.ticker.eq(ticker)&facts.accession_number.eq(accn)&facts.period_end.eq(period_end)]
        values = current.sort_values('period_start').drop_duplicates('field').set_index('field').value
        for metric,components in [('roe_ttm',['net_income','stockholders_equity']),('cash_conversion_ttm',['net_income','operating_cash_flow'])]:
            if pd.notna(row[metric]): continue
            missing = [field for field in components if field not in values]
            reason = 'current_canonical_field_missing:'+','.join(missing) if missing else None
            denominator = 'stockholders_equity' if metric=='roe_ttm' else 'net_income'
            if reason is None and values.get(denominator)==0: reason='zero_denominator'
            if reason is None:
                for field in [c for c in components if c!='stockholders_equity']:
                    history = facts[facts.ticker.eq(ticker)&facts.field.eq(field)&facts.filed_date.le(row.filed_date)&facts.period_start.notna()]
                    fy = history[history.fiscal_period.eq('FY')&history.period_end.lt(period_end)]
                    prior = history[history.accession_number.eq(accn)&history.period_end.lt(period_end)]
                    if fy.empty: reason='missing_prior_fy:'+field; break
                    if prior.empty: reason='missing_same_filing_prior_ytd:'+field; break
            calculations.append(dict(ticker=ticker,accession_number=accn,period_end=str(period_end.date()),metric=metric,
                                     reason=reason or 'UNVERIFIED_BRIDGE_OR_RATIO', **summary(group)))
    pd.DataFrame(calculations).to_csv(out/'ttm_calculation_causes.csv',index=False)
    # Representative cases retain actual records, not just absence assertions.
    cases = []
    for ticker in ['PDD','PAYX','ABNB','MRVL','CEG','FISV','TSLA','AMD','SWKS','SBUX']:
        rows = panel[panel.member & panel.ticker.eq(ticker) & panel.snapshot_join.eq('both') &
                     (panel.missing_ttm_ratios | panel.nonreported_leverage)]
        if rows.empty: continue
        row = rows.iloc[0]
        accn, cutoff = row.accession_number, str(row.information_session.date())
        rs = {field:[r for r in raw_records(payloads[ticker],field) if r.get('accn')==accn]
              for field in FIELD_TAGS}
        fy = {field:[r for r in raw_records(payloads[ticker],field)
                    if r.get('fp')=='FY' and r.get('filed','9999')<=cutoff and r.get('form') in ACCEPTED_FORMS]
              for field in ['net_income','operating_cash_flow']}
        alternative = {}
        for tag in ['NetIncomeLossAvailableToCommonStockholdersBasic','NetCashProvidedByUsedInOperatingActivitiesContinuingOperations']:
            alternative[tag] = [dict(r,unit=unit) for unit,records in payloads[ticker].get('facts',{}).get('us-gaap',{}).get(tag,{}).get('units',{}).items()
                                for r in records if r.get('filed','9999')<=cutoff and (r.get('accn')==accn or r.get('fp')=='FY')]
        cases.append(dict(ticker=ticker,signal_session=str(row.session.date()),information_session=cutoff,
                          snapshot=json.loads(row[daily.columns.drop('session').tolist()].to_json(date_format='iso')),
                          raw_path=str(raw/mapping[ticker]/'companyfacts.json'),raw_same_filing=rs,
                          visible_fy_records=fy,alternative_tags_not_assumed_equivalent=alternative,
                          normalized_same_filing=json.loads(facts[facts.ticker.eq(ticker)&facts.accession_number.eq(accn)].to_json(orient='records',date_format='iso'))))
    (out/'sec_trace_cases.json').write_text(json.dumps(cases,indent=2,ensure_ascii=False)+'\n')
    # Explicit currency correction is confined to PDD. No tag aliases, estimates,
    # unknown currencies, amendments or source gaps are filled.
    fixed_facts = extract_canonical_facts('PDD',mapping['PDD'],payloads['PDD'],monetary_unit='CNY')
    assert set(fixed_facts.loc[fixed_facts.field.ne('shares_outstanding'),'unit'])=={'CNY'}
    fixed = build_daily_quality_snapshot(fixed_facts,daily.session.unique())
    fixed_facts.to_parquet(out/'pdd_cny_facts.parquet',index=False)
    fixed.to_parquet(out/'pdd_cny_snapshots.parquet',index=False)
    fixed_panel = panel.copy()
    qcols = ['roe_ttm','cash_conversion_ttm','debt_to_assets']
    selected = panel[panel.ticker.eq('PDD')][['information_session','ticker']]
    joined = selected.merge(fixed.rename(columns={'session':'information_session'}),on=['information_session','ticker'],how='left',validate='one_to_one')
    joined.index = selected.index
    joined.loc[joined.debt_to_assets_source.ne('reported'),'debt_to_assets'] = np.nan
    assert (joined.loc[joined.filed_date.notna(),'filed_date'] <= joined.loc[joined.filed_date.notna(),'information_session']).all()
    fixed_panel.loc[selected.index,qcols] = joined[qcols]
    expressions = json.loads((out/'manifest.json').read_text())['expressions']
    required = list(expressions)+qcols
    fixed_panel['corrected_complete'] = fixed_panel[required].replace([np.inf,-np.inf],np.nan).notna().all(axis=1)
    currency_only = fixed_panel.corrected_complete.copy()
    selected = panel[panel.ticker.eq('EA')][['information_session','ticker']]
    joined = selected.merge(ea_daily.rename(columns={'session':'information_session'}),on=['information_session','ticker'],how='left',validate='one_to_one')
    joined.index = selected.index
    joined.loc[joined.debt_to_assets_source.ne('reported'),'debt_to_assets'] = np.nan
    fixed_panel.loc[selected.index,qcols] = joined[qcols]
    fixed_panel['corrected_complete'] = fixed_panel[required].replace([np.inf,-np.inf],np.nan).notna().all(axis=1)
    assert (joined.loc[joined.filed_date.notna(),'filed_date'] <= joined.loc[joined.filed_date.notna(),'information_session']).all()
    effects = []
    for year in [2022,2023,2024]:
        for segment in ['train','validation']:
            end = pd.Timestamp(year-1 if segment=='train' else year,12,31)
            period = panel.session.le(end) if segment=='train' else panel.session.between(pd.Timestamp(year,1,1),end)
            eligible = period & panel.member & panel.label_end.le(end)
            before = eligible & panel.complete
            after = eligible & fixed_panel.corrected_complete
            effects.append(dict(year=year,segment=segment,before=int(before.sum()),pdd_currency_only=int((eligible&currency_only).sum()),
                                ea_mapping_only=int((before | (after & panel.ticker.eq('EA'))).sum()),
                                after_both=int(after.sum()),gained=int((after&~before).sum()),lost=int((before&~after).sum())))
    pd.DataFrame(effects).to_csv(out/'minimal_fix_effect.csv',index=False)
    fixed_panel[['ticker','session','label_end','complete','corrected_complete',*qcols]].to_parquet(out/'corrected_eligibility.parquet',index=False)
    # Original missing cells stay null. Declarations are scoped to verified cache
    # absences; acquisition failures and semantic ambiguities remain unresolved.
    panel['status'] = np.where(panel.complete & panel.member,'COMPLETE_BEFORE_BOUNDARY','INVALID_UNVERIFIED')
    panel['gap_scope'] = ''
    panel.loc[panel.ticker.eq('EA'),'gap_scope'] = 'CONFIRMED_MAPPING_DEFECT_RAW_CACHE_PRESENT'
    panel.loc[panel.ticker.isin(['SPY','QQQ']),'gap_scope'] = 'BENCHMARK_ETFS_EXCLUDED_BY_SEC_BUILDER'
    for row in leverage:
        if row['status']=='INVALID_DECLARED_GAP':
            mask = panel.ticker.eq(row['ticker']) & panel.accession_number.eq(row['accession_number']) & panel.period_end.eq(pd.Timestamp(row['period_end'])) & panel.member
            panel.loc[mask,'status'] = 'INVALID_DECLARED_GAP'
            panel.loc[mask,'gap_scope'] = 'cached_filing_direct_total_liabilities_absent'
    # Confirm no preceding FY for the given CIK in any accepted raw currency.
    for ticker in ['ABNB','MRVL','CEG']:
        for cutoff, indexes in panel[panel.ticker.eq(ticker)&panel.member&panel.missing_ttm_ratios].groupby('information_session').groups.items():
            if pd.isna(cutoff): continue
            visible = [r for r in raw_records(payloads[ticker],'net_income') if r.get('fp')=='FY' and r.get('filed','9999')<=str(cutoff.date()) and r.get('form') in ACCEPTED_FORMS and r.get('start')]
            if not visible:
                panel.loc[indexes,'status']='INVALID_DECLARED_GAP'
                panel.loc[indexes,'gap_scope']='cached_current_CIK_annual_net_income_absent_asof'
    panel.loc[~panel.member,'status'] = 'OUTSIDE_PROVIDER_MEMBERSHIP'
    panel[['ticker','session','status','gap_scope',*qcols]].to_parquet(out/'gap_status.parquet',index=False)
    # Rebuild frozen snapshots with the unchanged default extraction; check no
    # unnoticed cache staleness or join-format problem explains the counts.
    rebuilt = build_daily_quality_snapshot(facts,daily.session.unique())
    pd.testing.assert_frame_equal(rebuilt,daily,check_dtype=False,check_exact=True)
    (out/'sec_manifest.json').write_text(json.dumps(dict(raw_hashes=hashes,normalized_rebuild_equal=True,
        snapshot_rebuild_equal=True,currency_fix=effects,
        gap_limit='Absence is verified only in the local cached dataset and named CIK/filing, not all SEC filings or predecessor entities'),indent=2)+'\n')
    print(pd.DataFrame(effects).to_string(index=False))
    print('All raw normalized facts and frozen daily snapshots reproduced exactly.')


if __name__ == '__main__':
    main()
