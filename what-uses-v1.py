from __future__ import annotations

import subprocess

with open('v1blobs') as f:
    v1blobs = set(f.read().splitlines())

# empty blob!
v1blobs.discard('e69de29bb2d1d6434b8b29ae775ad8c2e48c5391')

seen = set()

for cid in subprocess.check_output((
    'git', '-C', 'jaseci', 'log', '--all', '--format=%H',
)).decode().splitlines():
    for line in subprocess.check_output((
        'git', '-C', 'jaseci', 'ls-tree', '-r', cid,
    )).decode().splitlines():
        _, _, h, fn = line.split(maxsplit=3)
        if h in v1blobs and not fn.startswith('_v1') and (h, fn) not in seen:
            print(f'{cid} {h} {fn}')
            seen.add((h, fn))
