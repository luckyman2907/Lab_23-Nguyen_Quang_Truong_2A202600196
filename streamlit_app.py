"""Streamlit UI for LangGraph Agent Lab with HITL Approval.

This app demonstrates Human-in-the-Loop (HITL) approval workflow with:
- Real-time scenario execution
- Interactive approval/rejection interface
- State history visualization
- Checkpoint time-travel
"""

import os
import streamlit as st
from typing import Any

# Set HITL mode before importing graph
os.environ["LANGGRAPH_INTERRUPT"] = "true"

from langgraph_agent_lab.graph import build_graph
from langgraph_agent_lab.persistence import build_checkpointer
from langgraph_agent_lab.state import initial_state, Scenario, Route
from langgraph_agent_lab.scenarios import load_scenarios


# Page config
st.set_page_config(
    page_title="LangGraph Agent Lab - HITL Demo",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better UI
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .scenario-card {
        background-color: #f0f2f6;
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
        border-left: 5px solid #1f77b4;
    }
    .approval-card {
        background-color: #fff3cd;
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
        border-left: 5px solid #ffc107;
    }
    .success-card {
        background-color: #d4edda;
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
        border-left: 5px solid #28a745;
    }
    .error-card {
        background-color: #f8d7da;
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
        border-left: 5px solid #dc3545;
    }
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3rem;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)


def initialize_session_state():
    """Initialize Streamlit session state."""
    if "graph" not in st.session_state:
        checkpointer = build_checkpointer("memory")
        st.session_state.graph = build_graph(checkpointer)
        st.session_state.checkpointer = checkpointer
    
    if "current_state" not in st.session_state:
        st.session_state.current_state = None
    
    if "execution_history" not in st.session_state:
        st.session_state.execution_history = []
    
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = None


def render_header():
    """Render app header."""
    st.markdown('<div class="main-header">🤖 LangGraph Agent Lab - HITL Demo</div>', unsafe_allow_html=True)
    st.markdown("---")


def render_sidebar():
    """Render sidebar with scenario selection and controls."""
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Load scenarios
        scenarios = load_scenarios("data/sample/scenarios.jsonl")
        
        # Scenario selection
        st.subheader("📋 Select Scenario")
        scenario_options = {
            f"{s.id}: {s.query[:50]}...": s for s in scenarios
        }
        
        selected_key = st.selectbox(
            "Choose a scenario to execute:",
            options=list(scenario_options.keys()),
            key="scenario_select"
        )
        
        selected_scenario = scenario_options[selected_key]
        
        # Display scenario details
        with st.expander("📝 Scenario Details", expanded=True):
            st.write(f"**ID:** {selected_scenario.id}")
            st.write(f"**Query:** {selected_scenario.query}")
            st.write(f"**Expected Route:** {selected_scenario.expected_route}")
            st.write(f"**Requires Approval:** {selected_scenario.requires_approval}")
            st.write(f"**Should Retry:** {selected_scenario.should_retry}")
            st.write(f"**Max Attempts:** {selected_scenario.max_attempts}")
            
            if selected_scenario.tags:
                st.write(f"**Tags:** {', '.join(selected_scenario.tags)}")
        
        st.markdown("---")
        
        # Execution controls
        st.subheader("🎮 Controls")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("▶️ Run", type="primary", use_container_width=True):
                st.session_state.selected_scenario = selected_scenario
                st.session_state.should_run = True
                st.rerun()
        
        with col2:
            if st.button("🔄 Reset", use_container_width=True):
                st.session_state.current_state = None
                st.session_state.execution_history = []
                st.session_state.thread_id = None
                st.rerun()
        
        st.markdown("---")
        
        # History
        if st.session_state.execution_history:
            st.subheader("📜 Execution History")
            st.write(f"Total runs: {len(st.session_state.execution_history)}")
            
            for i, hist in enumerate(reversed(st.session_state.execution_history[-5:])):
                with st.expander(f"Run {len(st.session_state.execution_history) - i}"):
                    st.write(f"**Scenario:** {hist['scenario_id']}")
                    st.write(f"**Route:** {hist['route']}")
                    st.write(f"**Status:** {hist['status']}")


def render_approval_interface(state: dict[str, Any], config: dict[str, Any]):
    """Render the approval interface when graph is interrupted."""
    st.markdown('<div class="approval-card">', unsafe_allow_html=True)
    
    st.subheader("⚠️ Approval Required")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.write("**Proposed Action:**")
        st.info(state.get("proposed_action", "No action description available"))
        
        st.write("**Risk Level:**")
        risk_level = state.get("risk_level", "unknown")
        risk_color = {
            "high": "🔴",
            "medium": "🟡",
            "low": "🟢",
            "unknown": "⚪"
        }
        st.write(f"{risk_color.get(risk_level, '⚪')} {risk_level.upper()}")
        
        st.write("**Query:**")
        st.write(state.get("query", "N/A"))
    
    with col2:
        st.write("**State Info:**")
        st.write(f"Thread: `{state.get('thread_id', 'N/A')}`")
        st.write(f"Scenario: `{state.get('scenario_id', 'N/A')}`")
        st.write(f"Attempt: {state.get('attempt', 0)}")
    
    st.markdown("---")
    
    # Approval form
    st.write("**Decision:**")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        comment = st.text_input(
            "Comment (optional):",
            placeholder="Add your review comment here...",
            key="approval_comment"
        )
    
    with col2:
        if st.button("✅ Approve", type="primary", use_container_width=True):
            decision = {
                "approved": True,
                "reviewer": "streamlit-user",
                "comment": comment or "Approved via Streamlit UI"
            }
            st.session_state.approval_decision = decision
            st.session_state.should_resume = True
            st.rerun()
    
    with col3:
        if st.button("❌ Reject", type="secondary", use_container_width=True):
            decision = {
                "approved": False,
                "reviewer": "streamlit-user",
                "comment": comment or "Rejected via Streamlit UI"
            }
            st.session_state.approval_decision = decision
            st.session_state.should_resume = True
            st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)


def render_state_visualization(state: dict[str, Any]):
    """Render current state visualization."""
    st.subheader("📊 Current State")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Route", state.get("route", "N/A"))
    
    with col2:
        st.metric("Risk Level", state.get("risk_level", "N/A"))
    
    with col3:
        st.metric("Attempt", state.get("attempt", 0))
    
    with col4:
        events = state.get("events", [])
        st.metric("Events", len(events))
    
    # Detailed state
    with st.expander("🔍 Detailed State", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Messages:**")
            messages = state.get("messages", [])
            if messages:
                for msg in messages[-5:]:
                    st.text(f"• {msg}")
            else:
                st.text("No messages yet")
            
            st.write("**Tool Results:**")
            tool_results = state.get("tool_results", [])
            if tool_results:
                for result in tool_results[-3:]:
                    st.text(f"• {result}")
            else:
                st.text("No tool results yet")
        
        with col2:
            st.write("**Events:**")
            events = state.get("events", [])
            if events:
                for event in events[-5:]:
                    st.text(f"• {event.get('node', 'N/A')}: {event.get('message', 'N/A')}")
            else:
                st.text("No events yet")
            
            st.write("**Errors:**")
            errors = state.get("errors", [])
            if errors:
                for error in errors:
                    st.error(error)
            else:
                st.text("No errors")


def render_final_result(state: dict[str, Any]):
    """Render final execution result."""
    final_answer = state.get("final_answer")
    
    if final_answer:
        st.markdown('<div class="success-card">', unsafe_allow_html=True)
        st.subheader("✅ Execution Complete")
        st.write("**Final Answer:**")
        st.success(final_answer)
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Show approval decision if any
    approval = state.get("approval")
    if approval:
        st.write("**Approval Decision:**")
        if approval.get("approved"):
            st.success(f"✅ Approved by {approval.get('reviewer', 'N/A')}")
        else:
            st.error(f"❌ Rejected by {approval.get('reviewer', 'N/A')}")
        
        if approval.get("comment"):
            st.write(f"*Comment: {approval['comment']}*")


def execute_scenario(scenario: Scenario):
    """Execute a scenario with the graph."""
    try:
        # Create initial state
        state = initial_state(scenario)
        thread_id = state["thread_id"]
        st.session_state.thread_id = thread_id
        
        config = {
            "configurable": {
                "thread_id": thread_id
            }
        }
        
        # Start execution
        graph = st.session_state.graph
        
        # Stream execution
        for event in graph.stream(state, config, stream_mode="values"):
            st.session_state.current_state = event
            
            # Check if interrupted (waiting for approval)
            snapshot = graph.get_state(config)
            if snapshot.next:
                # Graph is interrupted, waiting for input
                return "interrupted"
        
        # Execution completed
        return "completed"
        
    except Exception as e:
        st.error(f"Error during execution: {str(e)}")
        return "error"


def resume_execution():
    """Resume execution after approval decision."""
    try:
        graph = st.session_state.graph
        thread_id = st.session_state.thread_id
        
        config = {
            "configurable": {
                "thread_id": thread_id
            }
        }
        
        # Resume with approval decision
        decision = st.session_state.approval_decision
        
        # Continue execution
        for event in graph.stream(decision, config, stream_mode="values"):
            st.session_state.current_state = event
        
        # Clear approval state
        st.session_state.approval_decision = None
        st.session_state.should_resume = False
        
        return "completed"
        
    except Exception as e:
        st.error(f"Error during resume: {str(e)}")
        return "error"


def main():
    """Main app function."""
    initialize_session_state()
    render_header()
    render_sidebar()
    
    # Main content area
    if hasattr(st.session_state, "should_run") and st.session_state.should_run:
        scenario = st.session_state.selected_scenario
        
        with st.spinner(f"Executing scenario: {scenario.id}..."):
            status = execute_scenario(scenario)
        
        st.session_state.should_run = False
        
        # Add to history
        st.session_state.execution_history.append({
            "scenario_id": scenario.id,
            "route": st.session_state.current_state.get("route", "N/A"),
            "status": status
        })
    
    # Handle resume after approval
    if hasattr(st.session_state, "should_resume") and st.session_state.should_resume:
        with st.spinner("Resuming execution..."):
            status = resume_execution()
        
        # Update history
        if st.session_state.execution_history:
            st.session_state.execution_history[-1]["status"] = status
    
    # Display current state
    if st.session_state.current_state:
        state = st.session_state.current_state
        
        # Check if waiting for approval
        graph = st.session_state.graph
        config = {
            "configurable": {
                "thread_id": st.session_state.thread_id
            }
        }
        
        snapshot = graph.get_state(config)
        
        if snapshot.next:
            # Interrupted - show approval interface
            render_approval_interface(state, config)
        else:
            # Completed - show final result
            render_final_result(state)
        
        # Always show state visualization
        st.markdown("---")
        render_state_visualization(state)
    
    else:
        # Welcome screen
        st.info("👈 Select a scenario from the sidebar and click **Run** to start!")
        
        st.markdown("### 🎯 Features")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**🔄 Real-time Execution**")
            st.write("Watch scenarios execute step-by-step")
        
        with col2:
            st.markdown("**✋ HITL Approval**")
            st.write("Approve or reject risky actions")
        
        with col3:
            st.markdown("**📊 State Visualization**")
            st.write("See complete state and history")


if __name__ == "__main__":
    main()
