def validate_response(response, code):
    if not isinstance(response, dict) or response.get('status') != 'ok':
        raise ValueError('Response must be an object with status=ok')
    if not isinstance(response.get('findings'), list):
        raise ValueError('findings must be a list, including [] for a clean review')
    if len(response['findings']) > 8:
        raise ValueError('More than eight findings; do not silently truncate')
    for item in response['findings']:
        if not isinstance(item, dict):
            raise ValueError('Finding must be an object')
        if item.get('subcategory') not in ALLOWED.get(item.get('category'), set()):
            raise ValueError('Unknown category/subcategory')
        if item.get('severity') not in WEIGHTS:
            raise ValueError('Unknown severity')
        start, end = (item.get('line_start'), item.get('line_end'))
        if type(start) is not int or type(end) is not int or (not 1 <= start <= end <= len(code.splitlines())):
            raise ValueError('Invalid line span')
        if not all((isinstance(item.get(k), str) and item[k].strip() for k in ('evidence', 'reason'))):
            raise ValueError('Finding needs nonempty evidence and reason')
    return response['findings']

def quality_score(accepted_findings, mode='sum'):
    """Input is already semantically accepted and deduplicated; None = unavailable.

Callers must distinguish [] (valid clean review) from None (no valid review).
Do not call directly on raw model output.
"""
    if accepted_findings is None:
        return None
    if mode not in {'sum', 'category_cap', 'smooth'}:
        raise ValueError('Unknown score mode')
    penalties = [WEIGHTS[f['severity']] for f in accepted_findings]
    if mode == 'sum':
        return max(0.0, 1.0 - sum(penalties))
    if mode == 'category_cap':
        by_category = {}
        for item in accepted_findings:
            key = item['subcategory']
            by_category[key] = max(by_category.get(key, 0), WEIGHTS[item['severity']])
        return max(0.0, 1.0 - sum(by_category.values()))
    return math.exp(-sum(penalties))
def read_env(path):
    """Read literal KEY=value settings; never execute shell expansion."""
    if path is None:
        return {}
    allowed = {'AI_JUDGE_BASE_URL', 'AI_JUDGE_MODEL', 'AI_JUDGE_TIMEOUT_SECONDS', 'AI_JUDGE_API_KEY', 'AI_JUDGE_API_STYLE'}
    settings = {}
    for number, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        key, separator, value = line.partition('=')
        key, value = (key.strip(), value.strip())
        if not separator:
            raise ValueError(f"Missing '=' at line {number}")
        if key not in allowed:
            raise ValueError(f'Unsupported setting at line {number}; see .env.example for supported keys')
        if key in settings:
            raise ValueError(f'Duplicate setting at line {number}')
        if len(value) >= 2 and value[0] == value[-1] and (value[0] in '"\''):
            value = value[1:-1]
        if not value and key != 'AI_JUDGE_API_KEY':
            raise ValueError(f'Empty setting at line {number}')
        if key == 'AI_JUDGE_API_KEY' and any((c in value for c in '\r\n')):
            raise ValueError(f'Invalid header value at line {number}')
        settings[key] = value
    return settings

def make_request(row, prompt, model, seed, temperature, max_tokens, api_style='ollama'):
    numbered = '\n'.join((f'{i}: {line}' for i, line in enumerate(row['code'].splitlines(), 1)))
    payload = {'model': model, 'stream': False, 'format': 'json', 'messages': [{'role': 'system', 'content': prompt}, {'role': 'user', 'content': 'Review this Python code:\n<code>\n' + numbered + '\n</code>'}], 'options': {'seed': seed, 'temperature': temperature, 'top_p': 1.0, 'num_predict': max_tokens}}
    if api_style == 'litellm':
        payload.pop('format')
        payload.pop('options')
        payload.update(response_format={'type': 'json_object'}, seed=seed, temperature=temperature, top_p=1.0, max_tokens=max_tokens)
    return payload
