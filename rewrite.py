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


def _delete_other_refs() -> None:
    run('git', 'remote', 'rm', 'origin')
    tags = runo('git', 'tag', '--list').splitlines()
    run('git', 'tag', '-d', *tags)


@contextlib.contextmanager
def _branch(cid: str, name: str) -> Generator[tuple[str, ...]]:
    orig = runo('git', 'rev-parse', cid).strip()
    run('git', 'checkout', orig, '-b', name)
    yield (GIT_FILTER_REPO, '--force', '--refs', 'HEAD')

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
# v1 files
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
_v1
# large things
docs/book_html
docs/docs/assets/playground_demo.gif
docs/docs/assets/playground_demo.mp4
docs/docs/assets/photo.jpg
docs/docs/learn/examples/littleX/images
docs/docs/examples/littleX/images
jac/support/jac-lang.org/docs/examples/littleX/images
jac/support/jac-lang.org/docs/learn/littleX/images
docs/docs/learn/examples/rag_chatbot/solution/docs/clinical_medicine.pdf
docs/docs/assets/runtime.gif
docs/docs/assets/vsce/jaclang-extension-2025.7.17.vsix
docs/docs/learn/examples/mtp_examples/assets/rpg_demo.gif
docs/docs/learn/examples/mtp_examples/assets/rpg_demo.mp4
jac/support/jac-lang.org/docs/assets/mtllm demo.mp4
support/vscode_ext/jac/jac-0.0.1.vsix
# trash
docs/book/book.synctex(busy)
.github/archived_workflows
# removed
jac-cloud
# compiled playground removed
docs/docs/playground/assets
docs/docs/playground/favicon.ico
docs/docs/playground/index.html
docs/docs/playground/jac_examples.json
docs/docs/playground/jaseci.png
docs/docs/playground/language-configuration.json
docs/docs/playground/language-reference.json
docs/docs/playground/onigasm.wasm
docs/docs/playground/python
docs/docs/playground/robots.txt
# codedoc (removed!)
jac-byllm/docs/.codedoc
jac-byllm/docs/docs/assets
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


def _rename_jaclang() -> None:
    c = commit_by_msg('bringing jaclang over')

    with _branch(f'{c}^', 'jaclang-rewrite') as rewrite:
        run(*rewrite, '--to-subdirectory-filter=jac')
        run(
            *rewrite,
            '--path-rename=jac/.github:.github',
            '--path-rename=jac/jac:jac/jaclang',
        )


def _typeshed_was_always_a_submodule() -> None:
    c = commit_by_msg('Merge pull request #2160 from jaseci-labs/type_01')

    env = {**os.environ, 'GIT_EDITOR': 'sed -i "0,/pick/s//edit/"'}
    cmd = ('git', 'rebase', '-i', f'{c}^')
    print(f'+ {shlex.join(cmd)}')
    subprocess.check_call(cmd, env=env)

    run('git', 'rm', '-r', 'jac/jaclang/vendor/typeshed')
    run(
        'git', 'submodule', 'add',
        'https://github.com/python/typeshed', 'jac/jaclang/vendor/typeshed',
    )

    run(
        'git', '-C', 'jac/jaclang/vendor/typeshed',
        'checkout', 'df3b5f3cdd7736079ad3124db244e4553625590c',
    )

    run('git', 'add', 'jac/jaclang/vendor/typeshed')
    run('git', 'commit', '--amend', '--no-edit')
    # should fail with conflict!
    assert subprocess.call(('git', 'rebase', '--continue'))
    # make sure we're resolving the correct one
    out = runo('git', 'status', '--porcelain', '--', 'jac')
    assert out == 'AA jac/jaclang/vendor/typeshed\n', out
    run(
        'git', '-C', 'jac/jaclang/vendor/typeshed',
        'checkout', 'bbbf7530a987e59c8458127351cacad2e57f04bf',
    )
    run('git', 'add', 'jac/jaclang/vendor/typeshed')
    run('git', 'commit', '--no-edit')
    run('git', 'rebase', '--continue')


def _more_deletions() -> None:
    run(
        GIT_FILTER_REPO,
        '--path=jac/support/vscode_ext',
        '--path=jac/jaclang/vendor/mypy/typeshed',
        '--invert-paths',
    )


def main() -> int:
    run('rm', '-rf', 'jaseci')
    run('cp', '-r', 'original', 'jaseci')

    with cd('jaseci'):
        _delete_other_refs()
        _rename_mtllm()
        _rename_jac_cloud()
        _rename_jaseci_v1()
        _trailing_rewrites()
        _squash_prs()
        # idk why this has to be at the end? haunted?
        _rename_jaclang()
        _typeshed_was_always_a_submodule()
        _more_deletions()

    run('du', '--exclude', 'modules', '-hs', 'original/.git', 'jaseci/.git')
    run('git', '-C', 'original', 'rev-list', '--count', '--all')
    run('git', '-C', 'jaseci', 'rev-list', '--count', '--all')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
