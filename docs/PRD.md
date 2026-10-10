# AgentGate 2.0 — Product Requirements (v0.1)

**Status:** Planned | **Product:** Enterprise AI agent governance prototype

## Problem
Organizations adopting AI agents need an understandable way to prevent unsafe tool actions and sensitive data transfers, while explaining decisions to their IT and AI platform teams. Prompt filtering alone cannot control what an agent does after interpreting a request.

## Primary user
**AI platform engineer / IT administrator:** configures policies, reviews audit decisions, investigates blocked actions. **Secondary user:** employee using an internal AI assistant who needs clear feedback when an action requires approval.

## Job to be done
"When an employee delegates work to an AI agent, help me enforce which data and tools it can access before an action executes, and explain what happened afterward."

## MVP (AgentGate 2.0)
1. One Nemotron-assisted agent with three **sandboxed** tools: synthetic document search, synthetic customer lookup, and email **draft** (never send by default).
2. A policy gate validates every proposed tool call *before execution*: **ALLOW**, **DENY**, or **REQUIRE_APPROVAL**.
3. Admin-configurable rules for tool, data classification, and destination.
4. Decision trace: request ID, action, route, triggered policy, status, timestamp, latency (no raw sensitive prompt in audit export).
5. Simulation-first dashboard with one-click examples, a decision timeline, and clearly labeled live vs simulated metrics.

## Explicit non-goals
- No guaranteed prevention of all private-data leaks or prompt injection.
- No unsupervised sending of email, production system writes, or accessing real confidential data.
- No claim of local/private inference until an actual private endpoint has been deployed and tested.
- No multi-agent orchestration or enterprise identity integration in the MVP.

## Success measures (targets, not current results)
- 100% of *instrumented* proposed tool calls are checked before execution in integration tests.
- 0 unauthorized tool calls execute in the frozen adversarial test suite.
- >=95% sensitive recall and <=5% false positive rate on a new, frozen, labeled dataset.
- p95 deterministic policy decision overhead <10 ms measured on the specified test machine.
- Every decision has an explanation and an audit event.

## Acceptance criteria
- Synthetic confidential-document-to-external-email scenario is denied or held for approval before tool execution.
- Public document search succeeds without unnecessary approval.
- Reviewer can see tool intent, triggered rule, decision, and outcome in one view.
- Offline demo works without an NVIDIA API key; hosted inference only sends safe synthetic test prompts.

## Key risks and mitigations
- **Pattern blind spots:** frozen evaluation set, report false negatives and limitations.
- **Prompt injection:** enforce tool permissions in Python, not by model instruction alone.
- **Leaks in logs:** store metadata, redact inputs, use synthetic fixtures.
- **Cost spikes:** simulation default; request caps for deployed live demo.

## Release boundary
The current repository is a prompt-level privacy router with hosted Nemotron inference, simulation, and session-local audit metadata. The agent and tool-governance features above are **planned**, not shipped.
