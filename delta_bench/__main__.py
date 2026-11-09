"""Run with python -m delta_bench."""
import argparse
import csv
import json
from pathlib import Path
import sys
from .core import compare, InputError
from .report import render_html


def main(argv=None):
    parser = argparse.ArgumentParser(description='Compare numeric CSV snapshots by unique key.')
    parser.add_argument('baseline', type=Path)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('--key', required=True)
    parser.add_argument('--columns', required=True, help='Comma-separated numeric columns')
    parser.add_argument('--atol', type=float, default=0.0)
    parser.add_argument('--rtol', type=float, default=0.0)
    parser.add_argument('--json', type=Path, help='Write machine report (stdout is always JSON)')
    parser.add_argument('--html', type=Path, help='Write standalone HTML report')
    args = parser.parse_args(argv)
    try:
        inputs = {args.baseline.resolve(), args.candidate.resolve()}
        outputs = [p.resolve() for p in (args.json, args.html) if p]
        # resolve detects symlink aliases; samefile also detects hard links.
        aliases = any(a.exists() and b.exists() and a.samefile(b)
                      for i, a in enumerate(outputs)
                      for b in list(inputs) + outputs[:i])
        if len(set(outputs)) != len(outputs) or inputs.intersection(outputs) or aliases:
            raise InputError('report destinations must be distinct and cannot overwrite inputs')
        result = compare(args.baseline, args.candidate, args.key,
                         [c.strip() for c in args.columns.split(',')], args.atol, args.rtol)
        serialized = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
        if args.json:
            args.json.write_text(serialized, encoding='utf-8')
        if args.html:
            args.html.write_text(render_html(result), encoding='utf-8')
        print(serialized, end='')
        return 0 if result['passed'] else 1
    except (InputError, OSError, csv.Error, UnicodeError, OverflowError, ValueError) as exc:
        print(json.dumps({'error': str(exc), 'passed': False}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
