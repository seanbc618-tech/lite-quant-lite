"""Verify frozen demo output and accounting properties, using only stdlib."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

if not __debug__:
    raise SystemExit('Run without -O: verification assertions must remain enabled')
command = [sys.executable, '-I', '-S', '-B', '-c',
           "import runpy,sys; sys.path.insert(0, '.'); runpy.run_path('demo.py', run_name='__main__')"]
first = subprocess.check_output(command, cwd=ROOT)
second = subprocess.check_output(command, cwd=ROOT)
assert first == second, 'Repeated runs differ'
assert first == (ROOT / 'reports/demo-results.json').read_bytes(), 'Frozen output differs'
report = json.loads(first)
rows = {(r['scenario'], r['cost_bps']): r for r in report['results']}
assert len(rows) == 6
assert rows['flat', 0]['ending_equity'] == 1000
assert rows['flat', 10]['ending_equity'] < 1000
assert rows['falling', 10]['ending_equity'] < rows['falling', 0]['ending_equity'] < 1000
for cost in (0, 10):
    gap = rows['declared_missing', cost]
    assert gap['status'] == 'INVALID_DECLARED_GAP'
    assert gap['gaps'] == [{'observation': 3, 'symbol': 'SYN_B'}]
    assert all(gap[k] is None for k in ('ending_equity', 'total_return', 'cost', 'traded_notional'))
    assert gap['ledger'] == []
print('PASS: two isolated stdlib runs match frozen output; six cases, accounting, negative outcomes, null gaps')
