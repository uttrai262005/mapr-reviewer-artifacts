import json
import os
import re
import urllib.request
from pathlib import Path
from typing import Any, Dict, Tuple


def _get_gateway_config() -> Tuple[str, str, str]:
    url = os.environ.get('OPENCLAW_GATEWAY_URL', '').strip()
    token = os.environ.get('OPENCLAW_GATEWAY_TOKEN', '').strip()
    model = os.environ.get('OPENCLAW_MODEL', '').strip() or 'openai-codex/gpt-5.2'
    if url and not url.endswith('/chat/completions'):
        url = url.rstrip('/') + '/v1/chat/completions'
    if not url:
        url = 'http://127.0.0.1:8317/v1/chat/completions'
    if not token:
        raise RuntimeError('Missing OPENCLAW_GATEWAY_TOKEN')
    return url, token, model


def grade_once(rubric_text: str, submission_text: str, schema_hint: Dict[str, Any]) -> Dict[str, Any]:
    url, token, model = _get_gateway_config()
    system = 'Bạn là giám khảo. Chỉ dùng đúng rubric được cung cấp. Chấm toàn bộ bài trong MỘT lần gọi. Chỉ trả JSON hợp lệ.'
    user = (
        'RUBRIC:\n' + rubric_text + '\n\n'
        'BÀI LÀM:\n' + submission_text + '\n\n'
        'JSON SCHEMA HINT:\n' + json.dumps(schema_hint, ensure_ascii=False, indent=2) + '\n\n'
        'Chỉ xuất JSON.'
    )
    payload = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': user},
        ],
        'temperature': 0.1,
        'max_tokens': int(os.environ.get('OPENCLAW_MAX_TOKENS', '400')),
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'},
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        raw = resp.read().decode('utf-8', errors='ignore')
    data = json.loads(raw)
    content = data['choices'][0]['message']['content'].strip()
    try:
        return json.loads(content)
    except Exception:
        m = re.search(r'\{[\s\S]*\}', content)
        if not m:
            raise RuntimeError('Model did not return JSON')
        return json.loads(m.group(0))
