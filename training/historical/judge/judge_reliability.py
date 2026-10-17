"""Transport/schema protection only; historical sanitizing and scoring stay in train.py."""
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone


class JudgeFailure(RuntimeError):
    def __init__(self, kind):
        self.kind = kind
        # Never retain response bodies, URLs, headers, or provider exception text.
        super().__init__(f"AI judge unavailable ({kind}); aborting without a quality reward")


def record_event(status, **fields):
    path = os.getenv("AI_JUDGE_STATUS_PATH")
    if path:
        with open(path, "a", encoding="utf-8") as stream:
            stream.write(json.dumps({"time": datetime.now(timezone.utc).isoformat(),
                                     "status": status, **fields}) + "\n")


def validate_response(value):
    """Reject invalid structure before historical semantic filtering can run."""
    if not isinstance(value, dict) or value.get("status") != "ok":
        raise JudgeFailure("schema")
    if not isinstance(value.get("findings"), list):
        raise JudgeFailure("schema")
    for finding in value["findings"]:
        if not isinstance(finding, dict):
            raise JudgeFailure("schema")
        for key in ("category", "subcategory", "severity", "evidence", "reason"):
            if not isinstance(finding.get(key), str):
                raise JudgeFailure("schema")
        for key in ("line_start", "line_end"):
            if type(finding.get(key)) is not int:
                raise JudgeFailure("schema")
    # Taxonomy values, severity normalization, evidence and span heuristics are
    # deliberately left to the unmodified historical sanitizer.
    return value


def request_judge(request, timeout, parse_content, *, opener=None, sleep=None):
    opener = opener or urllib.request.urlopen
    sleep = sleep or time.sleep
    for attempt in range(1, 4):
        record_event("attempt", attempt=attempt)
        try:
            with opener(request, timeout=timeout) as response:
                body = response.read().decode("utf-8")
            try:
                envelope = json.loads(body)
                content = envelope["choices"][0]["message"]["content"]
                if not isinstance(content, (str, dict)):
                    raise JudgeFailure("schema")
                result = validate_response(parse_content(content))
            except (json.JSONDecodeError, UnicodeError, ValueError):
                raise JudgeFailure("parse") from None
            except (KeyError, IndexError, TypeError):
                raise JudgeFailure("schema") from None
            record_event("ok", attempt=attempt)
            return result
        except urllib.error.HTTPError as exc:
            kind, transient = "http", exc.code in {408, 429, 500, 502, 503, 504}
            record_event("error", kind=kind, attempt=attempt, http_status=exc.code)
        except (TimeoutError, urllib.error.URLError, OSError):
            kind, transient = "network_timeout", True
            record_event("error", kind=kind, attempt=attempt)
        except UnicodeError:
            kind, transient = "parse", False
            record_event("error", kind=kind, attempt=attempt)
        except JudgeFailure as exc:
            kind, transient = exc.kind, False
            record_event("error", kind=kind, attempt=attempt)
        if not transient or attempt == 3:
            record_event("fatal", kind=kind, attempt=attempt)
            raise JudgeFailure(kind) from None
        record_event("retry", kind=kind, attempt=attempt)
        sleep(float(attempt))  # exactly 1s then 2s; each request timeout is bounded
