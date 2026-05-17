from typing import Iterable, Dict, Any


def audit_rows(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    rows = list(rows)
    ids = [str(r.get('student_id', '')).strip() for r in rows if str(r.get('student_id', '')).strip()]
    dupes = sorted({x for x in ids if ids.count(x) > 1})
    return {
        'rows': len(rows),
        'duplicate_student_ids': dupes,
        'ok': len(dupes) == 0,
    }
