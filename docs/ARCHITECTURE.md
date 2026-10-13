# AgentGate 2.0 — Architecture (v0.1)

```mermaid
flowchart TD
    U[Employee / Demo User] --> UI[AgentGate Web Console]
    UI --> AG[Single Nemotron Agent]
    AG --> PROP[Proposed tool call]
    PROP --> P[Policy Engine: ALLOW / DENY / APPROVAL]
    P -->|ALLOW| T[Sandboxed tool executor]
    P -->|DENY| X[Blocked with reason]
    P -->|APPROVAL| H[Human approval queue]
    H -->|Approved| T
    H -->|Rejected| X
    T --> R[Tool result]
    R --> AG
    P --> LOG[Redacted event log]
    T --> LOG
    X --> LOG
    LOG --> DASH[Metrics & decision timeline]
```

## Current vs planned
- **Current:** console_server.py (local HTTP API and console backend), web/ (HTML/CSS/JavaScript frontend), policy_engine.py and engine.py (privacy inspection and routing), model_client.py (model execution), nemotron_agent.py (Nemotron agent orchestration), tool_gateway.py (governed tool execution), approval_manager.py (single-use approvals), agent_audit.py (request-level auditing), and evaluate.py / final_test.py (development evaluation).

- **Planned:** `agent/` (one agent), `tools/` (synthetic tools), `policies/` (declarative policy engine), `observability/` (redacted action events). Add modules incrementally; do not refactor working features until regression tests are in place.

## Trust boundaries
1. Hosted NVIDIA endpoint is external: never send test secrets or live confidential data there.
2. Private route is **blocked** without a separately provisioned, verified private NIM endpoint.
3. Agent text and proposed actions are **untrusted**. Code enforces tool permissions before execution.
4. External actions (especially email delivery and writes) are disabled in the initial demo.
5. Logs contain event metadata, not raw secrets or full prompts.

## Decision record (proposed)
`request_id`, `timestamp`, `tool_name`, `action_summary_redacted`, `classification`, `policy_id`, `decision`, `reason`, `execution_mode`, `execution_status`, `policy_latency_ms`

## Week 1 engineering boundary
Add CI and regression tests, commit this architecture, and record existing behavior. Do **not** implement new agent actions until Week 2.
