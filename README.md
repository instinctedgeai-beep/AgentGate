# AgentGate — Enterprise AI Privacy & Policy Router

A two-hour portfolio MVP with a rule-based sensitive-data classifier, fail-closed routing, NVIDIA Nemotron hosted integration for public prompts, optional localhost private NIM, audit dashboard, and synthetic test suite.

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python evaluate.py
streamlit run app.py
```

Default mode is **simulate**; no prompt is sent to any remote API.

To test **live public inference**, generate a key from https://build.nvidia.com/nvidia/nemotron-3-super-120b-a12b , set `export NVIDIA_API_KEY='...'` in your terminal (do not paste into GitHub), switch to live, and submit a benign public prompt.

**Private means localhost only in this MVP.** Without `PRIVATE_NIM_BASE_URL`, sensitive prompts are blocked in live mode. The example `.env.example` is a template, *not* auto-loaded. A real NIM deployment requires separate GPU/serving setup and is not included. NVIDIA's public hosted API is NOT private/on-premises.

## Evaluation

`python evaluate.py` writes `results.csv` and `summary.json` from 30 synthetic labeled prompts. Report accuracy, sensitive recall, and false positive rate as synthetic test metrics, never as real-world privacy assurance. Inspection latency is distinct from end-to-end inference latency. Some test cases intentionally reveal gaps in rule detection.

## Scope and limitations

- Regex/keyword classifier only; **not** reliable enterprise DLP. No semantic privacy guarantee.
- Routing is request-text based, not complete agent tool-call or output interception.
- No actual OpenShell / NemoClaw integration or security sandbox.
- API/model costs are not shown because current applicable price cannot be inferred reliably. Token usage can be recorded from live responses.
- Audits exclude raw prompts to avoid retaining detected secrets. For real deployment also sanitize responses and exception messages.
- Dashboard audit history is in-memory per Streamlit session, not centralized or immutable.
- Detection policy is intentionally simple and misses names, confidential contract text, and other non-pattern secrets.

## Product brief

**User:** enterprise IT / AI platform administrator.

**Problem:** teams need visibility into when agents would send sensitive prompts to external inference providers.

**Solution:** demonstrate transparent pre-inference classification, configurable allow/block routes, and lightweight audit events.

**Primary success measures:** sensitive recall on a labeled synthetic suite, false-positive rate, median inspection overhead. Additional measured dimension: hosted inference latency when live mode is configured.

**Non-goals (MVP):** production DLP, self-hosted NIM deployment, sandbox policy enforcement, employee authentication, accurate cloud pricing.

**Next:** swap regex for an enterprise DLP detector, define policies in YAML, enforce routing in a gateway, add tests for prompts with mixed signals, redaction and human override.
