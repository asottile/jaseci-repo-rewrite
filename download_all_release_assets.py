from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.request


def main() -> int:
    subprocess.check_call(('rm', '-rf', 'assets'))
    os.makedirs('assets')

    url = 'https://api.github.com/repos/jaseci-labs/jaseci/releases'
    resp = urllib.request.urlopen(url)
    contents = json.load(resp)

    for release in contents:
        target = f'assets/{release["tag_name"]}'
        if release['assets']:
            print(f'* {release["tag_name"]}')
            os.makedirs(target)
            for a in release['assets']:
                print(f'    - {a["name"]}')
                with open(os.path.join(target, a['name']), 'wb') as f:
                    resp = urllib.request.urlopen(a['browser_download_url'])
                    shutil.copyfileobj(resp, f)

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
