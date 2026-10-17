def numbered_python_code(code: str) -> str:
    return '\n'.join((f'{line_number:>4}: {line}' for line_number, line in enumerate(code.splitlines(), start=1)))

def build_ai_judge_user_prompt(task_prompt: str, code: str, reference_code: str='') -> str:
    return AI_JUDGE_USER_TEMPLATE.format(task_prompt=task_prompt.strip() or '(task prompt unavailable)', numbered_code=numbered_python_code(code), reference_code=reference_code.strip() or '(reference solution unavailable)')

def parse_json_object(text: str) -> dict:
    if isinstance(text, dict):
        return text
    stripped = str(text).strip()
    if stripped.startswith('```'):
        stripped = re.sub('^```(?:json)?', '', stripped, flags=re.IGNORECASE).strip()
        stripped = re.sub('```$', '', stripped).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find('{')
        end = stripped.rfind('}')
        if start != -1 and end != -1 and (end > start):
            return json.loads(stripped[start:end + 1])
        raise

def code_lines_for_span(code: str, line_start: int, line_end: int) -> str:
    lines = code.splitlines()
    if line_start <= 0 or line_end <= 0:
        return ''
    start_index = max(0, line_start - 1)
    end_index = min(len(lines), max(line_start, line_end))
    return '\n'.join(lines[start_index:end_index])

def sanitize_ai_judge_findings(raw_response: dict, code: str='') -> list[dict]:
    findings = raw_response.get('findings', [])
    if not isinstance(findings, list):
        return []
    sanitized = []
    for finding in findings[:AI_JUDGE_MAX_FINDINGS]:
        if not isinstance(finding, dict):
            continue
        category = str(finding.get('category', '')).strip()
        subcategory = str(finding.get('subcategory', '')).strip()
        severity = str(finding.get('severity', '')).strip().lower()
        if category not in AI_JUDGE_ALLOWED_SUBCATEGORIES:
            continue
        if subcategory not in AI_JUDGE_ALLOWED_SUBCATEGORIES[category]:
            continue
        if severity not in AI_JUDGE_SEVERITY_WEIGHTS:
            continue
        evidence = str(finding.get('evidence', '')).strip()[:300]
        reason = str(finding.get('reason', '')).strip()[:500]
        weak_naming_reason = re.search('\\bnot descriptive\\b|\\bmore descriptive\\b|\\bdescriptive enough\\b', reason, re.IGNORECASE)
        conventional_names = re.search('\\b(i|j|idx|idx2|elem|elem2|x|y)\\b', evidence)
        stronger_naming_issue = re.search('\\bshadow|built-?in|reuse|reused|ambiguous|ambiguity|misleading|different meanings|same identifier\\b', reason, re.IGNORECASE)
        if subcategory == 'Confusing Variable Naming' and weak_naming_reason and conventional_names and (not stronger_naming_issue):
            continue
        try:
            line_start = int(finding.get('line_start', 0))
            line_end = int(finding.get('line_end', line_start))
        except (TypeError, ValueError):
            line_start = 0
            line_end = 0
        span_text = code_lines_for_span(code, line_start, line_end)
        evidence_and_span = f'{evidence}\n{span_text}'
        if subcategory == 'Unnecessary Else' and (not re.search('\\belse\\s*:', evidence_and_span)):
            continue
        sanitized.append({'category': category, 'subcategory': subcategory, 'severity': severity, 'line_start': max(0, line_start), 'line_end': max(0, line_end), 'evidence': evidence, 'reason': reason})
    return sanitized

def score_ai_judge_findings(findings: list[dict]) -> float:
    penalty = sum((AI_JUDGE_SEVERITY_WEIGHTS.get(finding.get('severity', ''), 0.0) for finding in findings))
    return max(0.0, min(1.0, 1.0 - penalty))
