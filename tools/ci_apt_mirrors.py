"""Configure Ubuntu mirrors only in disposable GitHub Actions runners."""
import os
from pathlib import Path
import re


MIRROR = re.compile(
    r'https?://(?:azure\.archive\.ubuntu\.com|'
    r'(?:[a-z0-9-]+\.)*ec2\.archive\.ubuntu\.com|'
    r'archive\.ubuntu\.com)/ubuntu(?=[/\s]|$)')


def configure(apt):
    apt = Path(apt)
    files = [apt/'sources.list', *apt.glob('sources.list.d/*.list'),
             *apt.glob('sources.list.d/*.sources'), *apt.glob('*mirrors*.txt')]
    for file in files:
        if not file.is_file():
            continue
        original = file.read_text()
        updated = MIRROR.sub('https://archive.ubuntu.com/ubuntu', original)
        if updated != original:
            file.write_text(updated)
    config = apt/'apt.conf.d/80ember-ci-network'
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('Acquire::Retries "3";\n'
                      'Acquire::http::Timeout "30";\n'
                      'Acquire::https::Timeout "30";\n')


if __name__ == '__main__':
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise SystemExit('This helper is only for disposable GitHub Actions runners.')
    configure('/etc/apt')
