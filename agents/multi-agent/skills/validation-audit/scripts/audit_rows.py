from typing import Iterable, Dict, Any


def audit_rows(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    rows = list(rows)
    ids = [str(r.get('student_id', '')).strip() for r in rows if str(r.get('student_id', '')).strip()]
    dupes = sorted({x for x in ids if ids.count(x) > 1})
    veto_count = sum(1 for r in rows if r.get('veto_flag'))
    return {
        'rows': len(rows),
        'duplicate_student_ids': dupes,
        'veto_count': veto_count,
        'ok': len(dupes) == 0,
    }
