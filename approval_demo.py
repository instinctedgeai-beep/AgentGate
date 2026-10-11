
"""Local approval demonstration using synthetic customer records."""

import streamlit as st

from approval_manager import ApprovalManager
from tool_gateway import run_tool


def render_approval_demo():
    st.subheader("Human Approval Console")

    st.caption(
        "Local synthetic-data workflow. "
        "No requests are sent to NVIDIA."
    )

    if "demo_approval_manager" not in st.session_state:
        st.session_state.demo_approval_manager = ApprovalManager()

    manager = st.session_state.demo_approval_manager

    if "demo_approval_id" not in st.session_state:
        st.session_state.demo_approval_id = None

    st.markdown("**Customer record request**")
    st.code("lookup_customer(customer_id='CUST-1001')")

    if st.button("Request approval", key="request_approval"):
        request = manager.create_request(
            "lookup_customer",
            {"customer_id": "CUST-1001"},
        )
        st.session_state.demo_approval_id = request.approval_id
        st.session_state.demo_execution_result = None

    approval_id = st.session_state.demo_approval_id

    if not approval_id:
        st.info("No approval request submitted yet.")
        return

    request = manager.requests[approval_id]

    st.write("**Approval status:**", request.status)

    if request.status == "PENDING":
        left, right = st.columns(2)

        if left.button("Approve", key="approve_action"):
            manager.approve(approval_id)
            st.rerun()

        if right.button("Reject", key="reject_action"):
            manager.reject(approval_id)
            st.rerun()

    elif request.status == "APPROVED":
        if st.button("Execute approved action"):
            result = run_tool(
                request.tool_name,
                request.arguments,
                approval_id=approval_id,
                approval_manager=manager,
            )
            st.session_state.demo_execution_result = result
            st.rerun()

    elif request.status == "REJECTED":
        st.error("Request rejected. Tool execution is disabled.")

    elif request.status == "CONSUMED":
        st.success("Approval consumed. Action cannot run again.")

    if st.session_state.get("demo_execution_result"):
        result = st.session_state.demo_execution_result
        st.write("**Execution result:**")
        st.json(result)
