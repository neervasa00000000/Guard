#!/usr/bin/env python3
"""Extra units at 42 px (= 10 pt at 300 DPI, the resolution of the FOIA scans): surnames, words, emails x
LiberationSans (Arial-metric), LiberationSerif (Times-metric), DejaVuSans. Same protocol as e1_run.unit (N=2000)."""
import os,sys,json
from multiprocessing import Pool
sys.path.insert(0,os.path.dirname(__file__));import e1_run
if __name__=='__main__':
    if len(sys.argv) != 1:
        raise SystemExit('Usage: e1_run_300dpi.py (configure E1_OUTPUT and E1_PROCS via the environment)')
    e1_run.E.check_render_inputs()
    for name in ('emails','surnames','words'):
        e1_run.E.get_dict(name)
    units=[(d,f,42) for d in ('emails','surnames','words') for f in ('LiberationSans','LiberationSerif','DejaVuSans')]
    with Pool(int(os.environ.get('E1_PROCS',6))) as p:
        for s in p.imap_unordered(e1_run.unit,units):pass
    print('300DPI DONE')
