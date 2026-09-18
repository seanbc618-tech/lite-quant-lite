"""Bounded development-only capacity comparison on audited corrected rows."""
import argparse
import hashlib
import json
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=Path('.cache/reports/fusion_coverage'))
    parser.add_argument('--output', type=Path, default=Path('.cache/reports/fusion_capacity_20260919'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    paths = [args.input/'eligibility.parquet', args.input/'corrected_eligibility.parquet', args.input/'manifest.json']
    manifest = json.loads(paths[2].read_text())
    data = pd.read_parquet(paths[0])
    fixed = pd.read_parquet(paths[1])
    assert data[['ticker','session']].equals(fixed[['ticker','session']])
    qcols = ['roe_ttm','cash_conversion_ttm','debt_to_assets']
    pcols = [c for c in manifest['expressions'] if c != 'label']
    data[qcols] = fixed[qcols]
    # Restrict ranks to actual provider members, matching the original protocol.
    data = data[data.member].copy()
    cols = pcols+qcols
    data[cols+['label']] = data[cols+['label']].replace([np.inf,-np.inf],np.nan)
    ranks = data.groupby('session')[cols].rank(pct=True)-0.5
    complete = data[cols+['label']].notna().all(axis=1)
    configurations = {
        'reference': dict(max_depth=4,num_leaves=15,min_child_samples=100),
        'depth3': dict(max_depth=3,num_leaves=7,min_child_samples=100),
        'depth2': dict(max_depth=2,num_leaves=3,min_child_samples=100),
    }
    protocol = dict(configurations=configurations,years=[2022,2023,2024],
                    fixed=dict(n_estimators=100,learning_rate=0.03,reg_alpha=1.,reg_lambda=10.,random_state=20260525),
                    inputs={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
                    gate='All annual fusion ICs > 0, MSE below zero baseline in >=2 years, IC above paired price in >=2 years.',
                    scope='Previously inspected development years only; no fresh holdout, portfolio, execution, or automatic promotion.')
    (args.output/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n')
    rows, panels = [], []
    for name, params in configurations.items():
        for year in protocol['years']:
            end = pd.Timestamp(year-1,12,31)
            vend = pd.Timestamp(year,12,31)
            tr = data.session.le(end)&data.label_end.le(end)&complete
            period = data.session.between(pd.Timestamp(year,1,1),vend)
            va = period&data.label_end.le(vend)&complete
            y = data.loc[tr].groupby('session').label.transform(lambda s:(s-s.mean())/s.std())
            vy = data.loc[va].groupby('session').label.transform(lambda s:(s-s.mean())/s.std())
            assert y.notna().all() and vy.notna().all()
            for model_name, features in [('price',pcols),('fusion',cols)]:
                model = lgb.LGBMRegressor(**protocol['fixed'],**params,n_jobs=4,verbosity=-1)
                model.fit(ranks.loc[tr,features],y)
                pred = pd.Series(model.predict(ranks.loc[va,features]),index=vy.index)
                comparison = pd.DataFrame(dict(session=data.loc[va,'session'],pred=pred,label=vy))
                ic = [g.pred.corr(g.label,method='spearman') if g.pred.nunique()>1 else np.nan for _,g in comparison.groupby('session')]
                row = dict(configuration=name,year=year,model=model_name,train_rows=int(tr.sum()),valid_rows=int(va.sum()),
                           rank_ic=float(np.nanmean(ic)),ic_sessions=int(np.isfinite(ic).sum()),
                           mse=float(((pred-vy)**2).mean()),zero_mse=float((vy**2).mean()))
                rows.append(row)
                panel = data.loc[period,['ticker','session','label_end']].copy()
                panel['prediction'] = pred.reindex(panel.index)
                panel['configuration'],panel['model'] = name,model_name
                panel['status'] = np.where(panel.prediction.notna(),'VALID','INVALID_MISSING_OR_BOUNDARY')
                panels.append(panel)
                print(row,flush=True)
    gates = {}
    for name in configurations:
        fusion = [r for r in rows if r['configuration']==name and r['model']=='fusion']
        price = {r['year']:r for r in rows if r['configuration']==name and r['model']=='price'}
        passed = all(r['rank_ic']>0 for r in fusion) and sum(r['mse']<r['zero_mse'] for r in fusion)>=2 and sum(r['rank_ic']>price[r['year']]['rank_ic'] for r in fusion)>=2
        gates[name] = 'PASS_DEVELOPMENT_ONLY' if passed else 'FAIL'
    pd.concat(panels).to_parquet(args.output/'validation_predictions.parquet',index=False)
    (args.output/'results.json').write_text(json.dumps(dict(gates=gates,rows=rows,limits=protocol['scope']),indent=2,allow_nan=False)+'\n')
    print(gates)


if __name__ == '__main__':
    main()
