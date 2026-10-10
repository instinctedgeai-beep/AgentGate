import os, re, time, uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

PATTERNS = {
    'EMAIL': r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b',
    'PHONE': r'(?<!\w)(?:\+1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\w)',
    'SSN': r'\b\d{3}-\d{2}-\d{4}\b',
    'CARD': r'\b(?:\d[ -]*?){13,19}\b',
    'ACCOUNT': r'\b(?:account|acct)\s*(?:number|no\.?|#|:)\s*[:#-]?\s*\d{6,17}\b',
    'HEALTH': r'\b(?:diagnosed with|patient record|medical record|prescription for|HIV status)\b',
    'SECRET': r'\b(?:api[_ -]?key|private[_ -]?key|password)\s*[:=]\s*\S+',
    'PRIVATE_CONTRACT': r'\bprivate\s+contract\b',
    'EMPLOYEE_RECORD': r'\bemployee\s+[A-Z][a-z]+\s+[A-Z][a-z]+\b',
    'CONFIDENTIAL': r'\bconfidential\b',
    'UNANNOUNCED_DEAL': r'\bunannounced\s+acquisition\b',
    'CUSTOMER_ID': r'\bCUST-\d+\b',
    'NONPUBLIC_FINANCIAL': r'\b(?:unreleased|nonpublic|non-public|unpublished)\b.{0,80}\b(?:earnings|financial|revenue|results|forecast)\b',
    'SENSITIVE_DEAL': r'\b(?:internal|confidential|private|unannounced)\b.{0,80}\b(?:merger|acquisition|negotiations|deal)\b',
    'SECRET_ROADMAP': r'\b(?:secret|confidential|internal|nonpublic)\b.{0,80}\b(?:roadmap|product plans|strategy)\b',
    'UNPUBLISHED_FORECAST': r'\b(?:unpublished|unreleased|nonpublic)\b.{0,80}\b(?:sales|revenue|financial)\s+(?:forecast|forecasts|projections)\b',
}

@dataclass
class Decision:
    request_id: str
    timestamp: str
    route: str
    policy_id: str
    signals: list
    reason: str
    inspection_ms: float

def inspect(prompt: str) -> Decision:
    started = time.perf_counter()
    signals = [name for name, pat in PATTERNS.items() if re.search(pat, prompt, flags=re.I)]
    sensitive = bool(signals)
    return Decision(
        request_id=str(uuid.uuid4())[:8], timestamp=datetime.now(timezone.utc).isoformat(),
        route='PRIVATE' if sensitive else 'CLOUD',
        policy_id='PII-001' if sensitive else 'PUBLIC-001',
        signals=signals, reason='Detected ' + ', '.join(signals) if sensitive else 'No configured sensitive pattern detected',
        inspection_ms=round((time.perf_counter()-started)*1000, 3)
    )