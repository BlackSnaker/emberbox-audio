#!/usr/bin/env python3
"""Read-only dependency report for Emberbox Audio."""
import argparse
import json
from pathlib import Path
import sys

sys.dont_write_bytecode=True
if sys.version_info<(3,10):raise SystemExit('Emberbox needs Python 3.10 or newer.')
import dependencies
from installer_ui import Terminal


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lang',choices=('auto','en','ru'),default='auto')
    parser.add_argument('--plain',action='store_true')
    parser.add_argument('--json',action='store_true',help='Machine-readable report without account data')
    args=parser.parse_args(argv)
    report=dependencies.inspect()
    if args.json:
        print(json.dumps({'ready':report.ready,'distribution':report.distribution.name,
            'family':report.distribution.family,'supported':report.distribution.supported,
            'checks':report.checks,'missing':list(report.missing),'versions':report.versions},indent=2))
    else:
        ui=Terminal(language=args.lang,plain=args.plain)
        ui.banner((Path(__file__).resolve().parents[1]/'VERSION').read_text().strip())
        ui.item(report.distribution.name)
        for key,value in report.checks.items():ui.item(dependencies.LABELS.get(key,key),value)
        if report.ready:ui.success('Dependencies are ready. No changes made.','Компоненты готовы. Ничего не изменено.')
        else:ui.warning('Run ./install.sh to prepare missing dependencies. No changes made.',
                        'Запусти ./install.sh для установки недостающего. Ничего не изменено.')
    return 0 if report.ready else 1


if __name__=='__main__':raise SystemExit(main())
