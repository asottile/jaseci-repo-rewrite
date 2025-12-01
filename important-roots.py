from __future__ import annotations

import os
import subprocess
import sys


def main() -> int:
    os.chdir(sys.argv[1])

    merges = []

    for cid in subprocess.check_output((
        'git', 'log', '--merges', '--format=%h',
    )).decode().splitlines():
        if subprocess.call(
            ('git', 'merge-base', f'{cid}^1', f'{cid}^2'),
            stdout=subprocess.DEVNULL,
        ):
            merges.append(cid)

    def _roots_n(parent: str) -> tuple[str, int]:
        out = subprocess.check_output((
            'git', 'log', parent, '--max-parents=0', '--format=%h',
        )).decode().strip()
        n_out = subprocess.check_output((
            'git', 'rev-list', '--count', parent,
        )).decode()
        n = int(n_out) - 1
        return out, n

    indent = 0
    print('|')
    for merge in merges:
        left, leftn = _roots_n(f'{merge}^1')
        right, rightn = _roots_n(f'{merge}^2')

        if len(left.splitlines()) == 1 and len(right.splitlines()) == 1:
            print(
                f'{' ' * indent}{left} <=> {leftn: 4} commits <=> {merge} '
                f'<=> {rightn: 4} commits <=> {right}',
            )
        elif len(left.splitlines()) == 1:
            print(f'{' ' * indent}{left} <=> {leftn: 4} commits <=> {merge} ')
            indent += 20
            print(f'{' ' * indent}|')
        elif len(right.splitlines()) == 1:
            print(f'{' ' * indent}{merge} <=> {rightn: 4} commits <=> {right}')
            print(f'{' ' * indent}|')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
