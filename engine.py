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

def execute(prompt: str, decision: Decision, mode='simulate') -> dict:
    """Never send PRIVATE requests to hosted NVIDIA endpoints."""
    if mode == 'simulate':
        return {'status':'SIMULATED','response':'[Simulation] Request would use '+decision.route+' route.', 'inference_ms': None, 'tokens':None, 'cost_usd':None}
    if mode != 'live':
        raise ValueError('mode must be simulate or live')
    from openai import OpenAI
    if decision.route == 'PRIVATE':
        base_url = os.getenv('PRIVATE_NIM_BASE_URL')
        if not base_url:
            return {'status':'BLOCKED', 'response':'No private NIM endpoint configured. No data transmitted.', 'inference_ms':None, 'tokens':None, 'cost_usd':None}
        if not (base_url.startswith('http://localhost:') or base_url.startswith('http://127.0.0.1:')):
            return {'status':'BLOCKED','response':'MVP permits only localhost private endpoints.', 'inference_ms':None, 'tokens':None,'cost_usd':None}
        client=OpenAI(base_url=base_url,api_key=os.getenv('PRIVATE_NIM_API_KEY','EMPTY'),timeout=25)
        model=os.getenv('PRIVATE_NIM_MODEL','nvidia/nemotron-3-super-120b-a12b')
    else:
        if not os.getenv('NVIDIA_API_KEY'):
            return {'status':'BLOCKED','response':'Missing NVIDIA_API_KEY. No data transmitted.', 'inference_ms':None,'tokens':None,'cost_usd':None}
        client=OpenAI(base_url='https://integrate.api.nvidia.com/v1',api_key=os.environ['NVIDIA_API_KEY'],timeout=25)
        model=os.getenv('NVIDIA_MODEL','nvidia/nemotron-3-super-120b-a12b')
    started=time.perf_counter()
    try:
        result=client.chat.completions.create(model=model,messages=[{'role':'user','content':prompt}],max_tokens=160,temperature=0.2)
        elapsed=round((time.perf_counter()-started)*1000,1)
        usage=result.usage
        return {'status':'COMPLETED','response':result.choices[0].message.content or '', 'inference_ms':elapsed,
                'tokens':getattr(usage,'total_tokens',None), 'cost_usd':None}
    except Exception as exc:
        return {'status':'ERROR','response':f'{type(exc).__name__}: {str(exc)[:120]}','inference_ms':round((time.perf_counter()-started)*1000,1),'tokens':None,'cost_usd':None}
