# AgentGate — Enterprise AI Policy & Agent Governance

**A policy-governed AI infrastructure prototype built around NVIDIA Nemotron.**

AgentGate explores how organizations can use AI systems while retaining control over sensitive information and agent actions. It combines privacy-aware prompt routing, explainable policy decisions, governed tool execution, and human approval workflows in a Streamlit-based control room.

## What AgentGate Does

- **Privacy-aware routing:** Inspects prompts for sensitive-data patterns before deciding whether hosted inference is eligible.
- **NVIDIA Nemotron integration:** Supports hosted Nemotron inference for eligible public prompts, with optional separately configured localhost NIM support.
- **Tool governance:** Provides three synthetic enterprise tools: document search, customer lookup, and email drafting.
- **Policy enforcement:** Validates tool names and arguments, then allows, blocks, or requires approval before execution.
- **Human-in-the-loop controls:** Tracks approval requests and supports single-use authorization tied to the specific tool and arguments.
- **Document redaction:** Prevents confidential document bodies from appearing in synthetic search results.
- **Decision visibility:** Includes a Streamlit dashboard for routing decisions and policy analytics.

## Architecture

AgentGate separates privacy inspection, model execution, policy evaluation, and tool dispatch.

1. A request enters the application.
2. The policy engine classifies its sensitive-data indicators.
3. Eligible public prompts may use hosted NVIDIA inference; sensitive requests are restricted to the configured private route or blocked.
4. Agent tool requests pass through the policy gateway.
5. Allowed actions execute, restricted actions are blocked, and approval-required actions cannot execute without valid authorization.

See [Architecture](docs/ARCHITECTURE.md) and [Product Requirements](docs/PRD.md).

## Getting Started

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests -v
streamlit run app.py
```

The application defaults to simulation mode.

For hosted Nemotron inference, configure `NVIDIA_API_KEY` locally. Never commit credentials or private information.

## Testing

The current development branch has passed **24 automated tests** covering privacy routing, gateway permissions, document protection, and approval handling.

The repository also includes a separate synthetic prompt evaluation using `evaluate.py`. Its results are development metrics, not evidence of production-grade privacy protection.

## Technology

Python · Streamlit · NVIDIA Nemotron · OpenAI-compatible API · unittest · GitHub Actions

## Development Status

**Implemented**
- Privacy inspection and routing
- Hosted public-prompt inference integration
- Streamlit routing dashboard
- Three synthetic enterprise tools
- Tool policy and execution gateway
- Restricted-document redaction
- In-memory approval lifecycle and single-use approval enforcement
- Automated regression tests and CI

**In progress**
- Nemotron agent function calling through the policy gateway
- Integrated approval experience in the dashboard
- Agent-level auditing and analytics
- Expanded adversarial and end-to-end evaluation

## Security Limitations

AgentGate is a portfolio prototype, not a production security platform. It uses pattern-based privacy inspection and synthetic business data. Its approval manager is in-memory and does not authenticate individual approvers. The Python tools are not OS-level sandboxed, and the current dashboard does not yet provide a complete autonomous-agent workflow.

Hosted NVIDIA inference is an external service and must not be treated as private or on-premises. Sensitive data should not be sent to it.

## Product Direction

AgentGate is evolving from a privacy-aware model router into a governed AI agent platform that demonstrates how teams can balance AI capabilities, human oversight, and policy enforcement.