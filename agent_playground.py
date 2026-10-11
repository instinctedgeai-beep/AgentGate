
"""Streamlit interface for the AgentGate Nemotron agent."""

import streamlit as st

from nemotron_agent import run_agent
from approval_demo import render_approval_demo


EXAMPLE_PROMPTS = {
    "Public document": (
        "Find the public product overview and summarize "
        "what AgentGate does in one sentence."
    ),
    "Customer lookup": (
        "Use the lookup_customer tool to retrieve the fictional "
        "customer record for CUST-1001. Do not search documents."
    ),
    "Private request": (
        "My email is alex@example.com. "
        "Can you summarize my information?"
    ),
}


def render_agent_playground():
    """Render the policy-governed AI agent interface."""

    st.title("AI Agent Playground")

    st.caption(
        "NVIDIA Nemotron with AgentGate policy enforcement"
    )

    st.info(
        "Prototype using synthetic enterprise data. "
        "Public prompts may be sent to NVIDIA's hosted API."
    )

    example = st.selectbox(
        "Try an example",
        ["Custom prompt"] + list(EXAMPLE_PROMPTS),
        key="agent_example",
    )

    default_prompt = EXAMPLE_PROMPTS.get(example, "")

    prompt = st.text_area(
        "Your request",
        value=default_prompt,
        height=120,
        key=f"agent_prompt_{example}",
        placeholder="Ask the agent to find a public document...",
    )

    run_clicked = st.button(
        "Run Agent",
        type="primary",
        use_container_width=True,
    )

    if not run_clicked:
        st.divider()
        render_approval_demo()
        return

    if not prompt.strip():
        st.warning("Enter a request before running the agent.")
        return

    with st.spinner("Checking policies and running Nemotron..."):
        try:
            result = run_agent(prompt)
        except Exception:
            st.error(
                "The agent request failed. "
                "Check the terminal for connection details."
            )
            return

    st.subheader("Execution status")

    status = result.get("status", "UNKNOWN")

    if status == "COMPLETED":
        st.success("Agent completed the request.")
    elif status == "ACTION_REQUIRED":
        st.warning(
            "An action was blocked or requires review."
        )
    else:
        st.error(
            f"{status}: {result.get('reason', 'No reason provided')}"
        )

    if result.get("answer"):
        st.subheader("Nemotron response")
        st.write(result["answer"])

    if result.get("tools"):
        st.subheader("Tool execution")

        for index, tool in enumerate(result["tools"], 1):
            with st.expander(
                f"{index}. {tool['tool']} — {tool['status']}",
                expanded=True,
            ):
                st.write(
                    "**Policy explanation:**",
                    tool.get("reason", "Not available"),
                )

                if tool.get("status") == "COMPLETED":
                    st.json(tool.get("result", {}))

    st.divider()
    render_approval_demo()