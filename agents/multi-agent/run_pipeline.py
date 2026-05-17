from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)  # type: ignore
    return mod


def run(rubric_path: Path, dataset_dir: Path, out_path: Path, limit: int | None = None, phase1: str = '', reset: bool = False, resume: bool = False):
    orchestrator = _load_module('paper_multi_orchestrator', ROOT / 'skills' / 'multi-agent-grader' / 'orchestrator.py')
    argv = [
        '--rubric', str(rubric_path),
        '--dataset', str(dataset_dir),
        '--out', str(out_path),
    ]
    if limit:
        argv += ['--limit', str(limit)]
    if phase1:
        argv += ['--phase1', phase1]
    if reset:
        argv += ['--reset']
    if resume:
        argv += ['--resume']
    rc = orchestrator.main(argv)
    report = {
        'return_code': rc,
        'rubric': str(rubric_path),
        'dataset': str(dataset_dir),
        'output': str(out_path),
        'phase1': phase1,
    }
    report_path = out_path.with_suffix('.multi_agent_report.json')
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Run paper-faithful multi-agent pipeline')
    ap.add_argument('--rubric', required=True)
    ap.add_argument('--dataset', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--limit', type=int, default=None)
    ap.add_argument('--phase1', default='')
    ap.add_argument('--reset', action='store_true')
    ap.add_argument('--resume', action='store_true')
    args = ap.parse_args()
    rep = run(Path(args.rubric), Path(args.dataset), Path(args.out), args.limit, args.phase1, args.reset, args.resume)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
