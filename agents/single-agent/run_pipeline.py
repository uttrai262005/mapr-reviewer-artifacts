from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from openpyxl import Workbook, load_workbook

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)  # type: ignore
    return mod


def _load_rubric_parser(rubric_path: Path):
    src = ROOT / 'skills' / 'multi-agent-grader' / 'scripts'
    low = rubric_path.name.lower()
    if 'bt1' in low:
        return _load_module('rubric_bt1_parser', src / 'rubric_bt1_parser.py').parse_rubric_bt1
    if 'bt2' in low:
        return _load_module('rubric_bt2_parser', src / 'rubric_bt2_parser.py').parse_rubric_bt2
    if 'bt3' in low:
        return _load_module('rubric_bt3_parser', src / 'rubric_bt3_parser.py').parse_rubric_bt3
    return _load_module('rubric_bt4_parser', src / 'rubric_bt4_parser.py').parse_rubric_bt4


def _load_docx_text_reader():
    mod = _load_module('bt1_inc', ROOT / 'bt1_grade_incremental.py')
    return mod.read_docx_text


def _normalize_text(s: str) -> str:
    return (s or '').strip()


def _extract_mssv(name: str) -> str:
    m = re.search(r'(\d{6,})', name)
    return m.group(1) if m else name


def _schema_hint(rubric: Any) -> Dict[str, Any]:
    hint: Dict[str, Any] = {}
    for i in range(1, 6):
        k = f'tc{i}_max'
        if hasattr(rubric, k):
            hint[f'tc{i}'] = f'number 0..{getattr(rubric, k)}'
    return hint


def _round_quarter(x: float) -> float:
    return round(float(x) * 4) / 4


def _round_half(x: float) -> float:
    return round(float(x) * 2) / 2


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


def _dataset_items(dataset_dir: Path) -> List[Tuple[str, List[Path]]]:
    files = sorted([p for p in dataset_dir.iterdir() if p.is_file() and p.suffix.lower() in {'.pdf','.docx','.txt','.png','.jpg','.jpeg','.webp','.md'}])
    if files:
        return [(_extract_mssv(p.stem), [p]) for p in files]
    out: List[Tuple[str, List[Path]]] = []
    for sub in sorted([p for p in dataset_dir.iterdir() if p.is_dir()]):
        docs = sorted([q for q in sub.rglob('*') if q.is_file() and q.suffix.lower() in {'.pdf','.docx','.txt','.png','.jpg','.jpeg','.webp','.md'}])
        out.append((_extract_mssv(sub.name), docs))
    return out


def _ensure_xlsx(path: Path, headers: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    wb = Workbook()
    ws = wb.active
    ws.title = 'single_agent'
    ws.append(headers)
    wb.save(path)


def run(rubric_path: Path, dataset_dir: Path, out_path: Path, limit: int | None = None, reset: bool = False):
    ingest_mod = _load_module('single_ingest', BASE / 'skills' / 'document-ingestion' / 'scripts' / 'ingest.py')
    eval_mod = _load_module('single_grade', BASE / 'skills' / 'agentic-evaluation' / 'scripts' / 'grade_once.py')
    audit_mod = _load_module('single_audit', BASE / 'skills' / 'validation-audit' / 'scripts' / 'audit_rows.py')
    export_mod = _load_module('single_export', BASE / 'skills' / 'export' / 'scripts' / 'export_xlsx.py')

    parse_rubric = _load_rubric_parser(rubric_path)
    read_docx_text = _load_docx_text_reader()
    rubric, rubric_raw = parse_rubric(rubric_path)
    rubric_text = read_docx_text(rubric_path)
    items = _dataset_items(dataset_dir)
    if limit:
        items = items[:limit]

    if reset and out_path.exists():
        out_path.unlink()

    has_tc5 = hasattr(rubric, 'tc5_max')
    headers = ['student_id', 'tc1', 'tc2', 'tc3', 'tc4'] + (['tc5'] if has_tc5 else []) + ['total', 'note']
    _ensure_xlsx(out_path, headers)

    rows_for_export = []
    audit_rows = []
    for student_id, paths in items:
        note = ''
        if not paths:
            row = [student_id, 0, 0, 0, 0] + ([0] if has_tc5 else []) + [0, 'NO_FILES']
            rows_for_export.append(row)
            audit_rows.append({'student_id': student_id, 'note': 'NO_FILES'})
            continue
        parts = []
        for p in paths:
            try:
                parts.append(f'\n\n===== FILE: {p.name} =====\n' + ingest_mod.ingest(str(p)))
            except Exception as e:
                parts.append(f'\n\n===== FILE: {p.name} (extract_error) =====\n{e}')
        submission_text = _normalize_text('\n'.join(parts))
        if len(submission_text) < 20:
            row = [student_id, 0, 0, 0, 0] + ([0] if has_tc5 else []) + [0, 'EMPTY_TEXT']
            rows_for_export.append(row)
            audit_rows.append({'student_id': student_id, 'note': 'EMPTY_TEXT'})
            continue
        try:
            res = eval_mod.grade_once(rubric_text, submission_text, _schema_hint(rubric))
            tc1 = _round_quarter(_clamp(float(res.get('tc1', 0.0)), 0.0, float(getattr(rubric, 'tc1_max', 0.0))))
            tc2 = _round_quarter(_clamp(float(res.get('tc2', 0.0)), 0.0, float(getattr(rubric, 'tc2_max', 0.0))))
            tc3 = _round_quarter(_clamp(float(res.get('tc3', 0.0)), 0.0, float(getattr(rubric, 'tc3_max', 0.0))))
            tc4 = _round_quarter(_clamp(float(res.get('tc4', 0.0)), 0.0, float(getattr(rubric, 'tc4_max', 0.0))))
            vals = [tc1, tc2, tc3, tc4]
            if has_tc5:
                tc5 = _round_quarter(_clamp(float(res.get('tc5', 0.0)), 0.0, float(getattr(rubric, 'tc5_max', 0.0))))
                vals.append(tc5)
            total = _round_half(sum(vals))
            row = [student_id] + vals + [total, note]
            rows_for_export.append(row)
            audit_rows.append({'student_id': student_id, 'total': total})
        except Exception as e:
            row = [student_id, 0, 0, 0, 0] + ([0] if has_tc5 else []) + [0, f'ERROR:{type(e).__name__}']
            rows_for_export.append(row)
            audit_rows.append({'student_id': student_id, 'note': f'ERROR:{type(e).__name__}'})

    export_mod.export_rows(str(out_path), headers, rows_for_export)
    audit = audit_mod.audit_rows(audit_rows)
    report = {
        'rubric': rubric_raw,
        'items': len(items),
        'audit': audit,
        'output': str(out_path),
    }
    report_path = out_path.with_suffix('.single_agent_report.json')
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Run paper-faithful single-agent pipeline')
    ap.add_argument('--rubric', required=True)
    ap.add_argument('--dataset', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--limit', type=int, default=None)
    ap.add_argument('--reset', action='store_true')
    args = ap.parse_args()
    rep = run(Path(args.rubric), Path(args.dataset), Path(args.out), args.limit, args.reset)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
