"""Headless runs of the original Japanese rules edition. No browser required."""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from web_app import AppError, GamebookService


def main(argv=None):
    parser = argparse.ArgumentParser(description='Run Jev or Random on 灰鐘の港と、名前のない朝 (full original rules)')
    parser.add_argument('--backend', choices=['random', 'jev', 'openrouter'], default='random')
    parser.add_argument('--runs', type=int, default=1)
    parser.add_argument('--seed', type=int, default=17)
    parser.add_argument('--jsonl', type=Path, default=Path('ashbell-runs.jsonl'))
    args = parser.parse_args(argv)
    if not 1 <= args.runs <= 10000: parser.error('--runs must be between 1 and 10000')
    if not 0 <= args.seed <= 2**32 - args.runs: parser.error('seed range exceeds 32 bits')
    if args.backend != 'random' and not GamebookService.key(args.backend):
        parser.error('Set the selected provider key in .env. No fallback or retry will be made.')
    args.jsonl.parent.mkdir(parents=True, exist_ok=True)
    endings = Counter()
    try:
        with args.jsonl.open('a', encoding='utf-8') as output:
            for index in range(args.runs):
                service = GamebookService()
                state = service.new_run({'book':'ashbell', 'seed':args.seed+index})
                while state['status'] == 'live':
                    state = service.step(state['run_id'], {'revision':state['revision'], 'backend':args.backend})
                result = service.export(state['run_id'])
                ending = (result['ending'] or {}).get('id', result['status'])
                endings[ending] += 1
                output.write(json.dumps({'run':index, 'backend':args.backend, **result}, ensure_ascii=False) + '\n')
                output.flush()
                print(f'run={index} ending={ending} steps={state["steps"]} hp={state["character"]["hp"]} tide={state["character"]["tide"]}')
    except AppError as error:
        print(f'Stopped: {error}. Completed runs remain in {args.jsonl}.', file=sys.stderr)
        return 1
    print(json.dumps({'backend':args.backend, 'runs':args.runs, 'endings':dict(endings), 'trace':str(args.jsonl)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
