
# AgentGate — Enterprise AI Governance

**A policy-governed AI agent prototype powered by NVIDIA Nemotron.**

AgentGate explores how organizations can use AI agents while maintaining control over sensitive information, tool execution, and human approvals.

Built with Python, NVIDIA Nemotron, and a custom web console, AgentGate makes AI policy enforcement observable and explainable.

## Features

- **Privacy-aware routing:** Classifies prompts before hosted inference.
- **NVIDIA Nemotron agent:** Supports tool calling and generates answers from approved public tool results.
- **Governed tools:** Synthetic document search, customer lookup, and email drafting.
- **Policy enforcement:** Allows, blocks, or requires approval for tool execution.
- **Human approvals:** Local approval and rejection workflow with single-use execution authorization.
- **Document protection:** Redacts confidential synthetic documents.
- **Agent auditing:** Records request IDs, timestamps, tool outcomes, and execution latency.
- **Observability:** Tracks request activity, blocked actions, tool executions, and latency.
- **Automated testing:** 58 regression tests passed locally as of October 2026.

## AgentGate Console

The primary interface is a custom HTML, CSS, and JavaScript governance console with five sections:

| Section | Purpose |
|---|---|
| Route | Inspect and route public or sensitive prompts |
| Activity | Explore routing activity and outcomes |
| Gateway | Test governed tool execution and local approvals |
| Evidence | Review synthetic evaluation results and routing history |
| Agent | Interact with Nemotron and inspect execution audits |

## Getting Started

Requires Python 3.12 or another compatible Python version.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

Start the primary console:

```bash
python console_server.py
```

Open http://127.0.0.1:8600

## NVIDIA Configuration

Create a local `.env` file using `.env.example` as a reference.

Set `NVIDIA_API_KEY` to enable hosted inference.

The console defaults to simulation mode. Hosted inference is an external service and must not receive sensitive information.

A localhost NIM endpoint can optionally be configured for private routing, but configuring a URL does not deploy or verify a local NIM server.

Never commit API credentials.

## Architecture

AgentGate separates:

1. Privacy inspection and routing
2. NVIDIA model inference
3. Tool policy evaluation
4. Tool execution and human approval
5. Request-level auditing and observability

See [Architecture](docs/ARCHITECTURE.md) and [Product Requirements](docs/PRD.md).

## Testing

Run:

```bash
python -m unittest discover -s tests -v
```

For optional responsive browser tests:

```bash
python -m pip install playwright
python -m playwright install chromium
python tools/responsive_check.py
```

The browser tests require the console to be running locally.

## Security Limitations

AgentGate is a portfolio prototype, not a production security system.

- Privacy inspection is pattern-based and may miss sensitive information.
- Business documents and customer records are synthetic.
- Local approvals do not authenticate individual reviewers.
- Approval state and console analytics are held in memory.
- Tool functions are not operating-system-level sandboxes.
- Hosted NVIDIA inference must not be treated as on-premises or confidential processing.
- Synthetic evaluation results do not establish real-world security accuracy.

## Current Direction

AgentGate demonstrates privacy-aware routing, governed agent actions, human oversight, and explainable AI operations. Future development includes stronger authorization, adversarial evaluation, persistent governance logs, and richer operational analytics.
