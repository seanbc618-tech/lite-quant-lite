"""Repeat the research demo in isolated Python processes and compare frozen output."""
import json
from pathlib import Path
import subprocess
import sys

if not __debug__:
    raise SystemExit('Run without -O')
ROOT = Path(__file__).resolve().parent
launcher = """
import sys, runpy
# Audit hooks guard this process, not arbitrary native extensions or the OS.
def deny_network(event, args):
    if event.startswith(('socket.', 'urllib.')):
        raise RuntimeError('Network is outside this offline demonstration')
sys.addaudithook(deny_network)
sys.path.insert(0, '.')
runpy.run_path('research_demo.py', run_name='__main__')
"""
command = [sys.executable, '-I', '-B', '-c', launcher]
first = subprocess.check_output(command, cwd=ROOT)
second = subprocess.check_output(command, cwd=ROOT)
assert first == second == (ROOT/'reports/research-results.json').read_bytes()
r = json.loads(first)
assert len(r['information_panel']) == 24 and len(r['split_audit']) == 20
assert len(r['provider']['symbols']) == 2
assert r['negative_control']['leak_detected']
assert all(r['checks'].values())
print('PASS: research output matches twice; 24 information cells, 20 split cells; temporal controls and gap checks pass')
