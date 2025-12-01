from __future__ import annotations

import contextlib
import os.path
import re
import shlex
import subprocess
import sys
from collections.abc import Generator

GIT_FILTER_REPO = os.path.abspath('venv/bin/git-filter-repo')


def run(*cmd: str) -> None:
    print(f'+ {shlex.join(cmd)}', flush=True, file=sys.stderr)
    subprocess.check_call(cmd)


def runo(*cmd: str) -> str:
    print(f'+ {shlex.join(cmd)} # captured', flush=True, file=sys.stderr)
    return subprocess.check_output(cmd, text=True)


@contextlib.contextmanager
def cd(d: str) -> Generator[None]:
    print(f'pushd {d}', flush=True, file=sys.stderr)
    with contextlib.chdir(d):
        yield
    print('popd', flush=True, file=sys.stderr)


def commit_by_msg(msg: str) -> str:
    out = runo('git', 'log', '--grep', f'^{re.escape(msg)}$', '--format=%H')
    assert len(out.splitlines()) == 1, out
    return out.strip()


def _fixup_backward_merge() -> None:
    msg = "Merge branch 'repo_reorg' into jaccloud"

    def _parents_order() -> str:
        c = commit_by_msg(msg)
        return runo(
            'git', 'show', '--no-patch', '--format=%s',
            f'{c}^1', f'{c}^2',
        )

    assert _parents_order() == '''\
big move
fixed github stuff
'''

    callback = f'''\
  if commit.original_id == {commit_by_msg(msg).encode()!r}:
    assert len(commit.parents) == 2, vars(commit)
    commit.parents.reverse()
'''
    run(GIT_FILTER_REPO, '--commit-callback', callback)

    # check we were successful
    assert _parents_order() == '''\
fixed github stuff
big move
'''


def reachable_tags() -> list[str]:
    head = runo('git', 'rev-parse', 'HEAD').strip()

    merged_out = runo('git', 'tag', '--merged', 'HEAD')
    merged_tags = frozenset(merged_out.splitlines())

    forked_tags = [*sorted(merged_tags)]
    for tag in runo('git', 'tag').splitlines():
        if tag in merged_tags:
            continue
        try:
            merge_base = runo('git', 'merge-base', tag, 'HEAD').strip()
        except subprocess.CalledProcessError:
            continue
        else:
            if merge_base == head:
                continue
            else:
                forked_tags.append(tag)
    return forked_tags


@contextlib.contextmanager
def _branch(cid: str, name: str) -> Generator[tuple[str, ...]]:
    orig = runo('git', 'rev-parse', cid).strip()
    run('git', 'checkout', orig, '-b', name)
    yield (GIT_FILTER_REPO, '--force', '--refs', 'HEAD', *reachable_tags())

    run('git', 'checkout', 'main')
    run('git', 'replace', orig, name)
    run(GIT_FILTER_REPO, '--proceed')
    run('git', 'branch', '-D', name)


def _rename_mtllm() -> None:
    c = commit_by_msg('pulling it together')

    with _branch(f'{c}^', 'jac-mtllm-rewrite') as rewrite:
        run(*rewrite, '--to-subdirectory-filter=jac-mtllm')


def _rename_jac_cloud() -> None:
    c = commit_by_msg('big move')

    with _branch(f'{c}^', 'jac-cloud-rewrite') as rewrite:
        run(*rewrite, '--to-subdirectory-filter=jac-cloud')


def _rename_jaseci_v1() -> None:
    c = commit_by_msg('Jaseci-wide repo reorg')

    with _branch(f'{c}^', 'jaseci-v1-rewrite') as rewrite:
        # remove later-deleted things
        run(
            *rewrite,
            '--path=experiments/config.py',
            '--path=.github',
            '--invert-paths',
        )
        run(*rewrite, '--to-subdirectory-filter=jaseci_v1')


def _trailing_rewrites() -> None:
    removals = '''\
# v1 workflows
.github/ISSUE_TEMPLATE/bug_report.md
.github/ISSUE_TEMPLATE/feature_request.md
.github/workflows/black.yml
.github/workflows/build-and-release-studio.yml
.github/workflows/build-and-release.yml
.github/workflows/jac-extension-test.yml
.github/workflows/jac-misc-test.yml
.github/workflows/jac-nlp-test.yml
.github/workflows/jac-speech-test.yml
.github/workflows/jac-vision-test.yml
.github/workflows/jaseci-core-test.yml
.github/workflows/jaseci-serv-test.yml
.github/workflows/jaseci-studio-test.yml
# rm _v1 entirely!
_v1
# large things
docs/book_html
docs/docs/assets/playground_demo.mp4
docs/docs/assets/vsce/jaclang-extension-2025.7.17.vsix
docs/docs/learn/examples/mtp_examples/assets/rpg_demo.mp4
jac/support/jac-lang.org/docs/assets/mtllm demo.mp4
support/vscode_ext/jac/jac-0.0.1.vsix
# trash
docs/book/book.synctex(busy)
.github/archived_workflows
'''
    run(
        GIT_FILTER_REPO,
        '--path-rename=jaclang:jac',
        '--path-rename=jaseci_v1:_v1',
        '--path-rename=jac-mtllm:jac-byllm',
        *(
            f'--path={p}'
            for p in removals.splitlines()
            if not p.startswith('#')
        ),
        # this funny file has control characters in its name
        '--path-glob', 't.replace*',
        '--invert-paths',
    )


def _squash_prs() -> None:
    callback = '''\
  if (
     commit.message.startswith(b"Merge pull request ") and
     len(commit.parents) == 2
  ):
    del commit.parents[1]
'''
    run(GIT_FILTER_REPO, '--commit-callback', callback)


def main() -> int:
    run('rm', '-rf', 'jaseci')
    run('cp', '-r', 'original', 'jaseci')

    with cd('jaseci'):
        _fixup_backward_merge()
        _rename_mtllm()
        _rename_jac_cloud()
        _rename_jaseci_v1()
        _trailing_rewrites()
        _squash_prs()

    run('du', '-hs', 'original/.git', 'jaseci/.git')
    run('git', '-C', 'original', 'rev-list', '--count', '--all')
    run('git', '-C', 'jaseci', 'rev-list', '--count', '--all')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
