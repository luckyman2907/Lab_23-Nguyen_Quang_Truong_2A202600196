"""Node skeletons for the LangGraph workflow.

Each function should be small, testable, and return a partial state update. Avoid mutating the
input state in place.
"""

from __future__ import annotations

from .state import AgentState, ApprovalDecision, Route, make_event


def intake_node(state: AgentState) -> dict:
    """Normalize raw query into state fields.
    
    Performs basic normalization and validation before routing.
    """
    query = state.get("query", "").strip()
    
    # Basic validation
    if not query:
        return {
            "query": query,
            "messages": ["intake:empty_query"],
            "errors": ["Empty query received"],
            "events": [make_event("intake", "error", "empty query")],
        }
    
    return {
        "query": query,
        "messages": [f"intake:{query[:50]}..."],
        "events": [make_event("intake", "completed", f"query normalized, length={len(query)}")],
    }


def classify_node(state: AgentState) -> dict:
    """Classify the query into a route.

    Priority-based routing (highest to lowest):
    1. RISKY: refund, delete, send, cancel, remove, revoke, confirmation
    2. TOOL: status, order, lookup, check, track, find, search
    3. MISSING_INFO: very short queries (<5 words) with vague pronouns
    4. ERROR: timeout, fail, error, crash, unavailable, failure, cannot, recover
    5. SIMPLE: default fallback
    """
    import re
    
    query = state.get("query", "").lower()
    # Strip punctuation and normalize whitespace
    clean_query = re.sub(r'[^\w\s]', ' ', query)
    words = clean_query.split()
    
    route = Route.SIMPLE
    risk_level = "low"
    
    # Priority 1: RISKY keywords (highest priority - destructive/external actions)
    risky_keywords = ["refund", "delete", "send", "cancel", "remove", "revoke", "confirmation"]
    if any(keyword in words for keyword in risky_keywords):
        route = Route.RISKY
        risk_level = "high"
    
    # Priority 2: TOOL keywords (data lookup/retrieval)
    elif any(
        keyword in words
        for keyword in [
            "status",
            "order",
            "lookup",
            "check",
            "track",
            "find",
            "search",
        ]
    ):
        route = Route.TOOL
        risk_level = "low"
    
    # Priority 3: MISSING_INFO (vague/incomplete queries)
    elif len(words) < 5 and any(pronoun in words for pronoun in ["it", "this", "that"]):
        route = Route.MISSING_INFO
        risk_level = "low"
    
    # Priority 4: ERROR keywords (system failures)
    elif any(
        keyword in words
        for keyword in [
            "timeout",
            "fail",
            "failure",
            "error",
            "crash",
            "unavailable",
            "cannot",
            "recover",
        ]
    ):
        route = Route.ERROR
        risk_level = "medium"
    
    # Priority 5: SIMPLE (default - informational queries)
    # route already set to SIMPLE above
    
    return {
        "route": route.value,
        "risk_level": risk_level,
        "events": [make_event("classify", "completed", f"route={route.value}, risk={risk_level}")],
    }


def ask_clarification_node(state: AgentState) -> dict:
    """Ask for missing information instead of hallucinating.
    
    Generates context-aware clarification questions based on the vague query.
    """
    query = state.get("query", "").strip()
    
    # Generate more specific clarification based on what's missing
    if not query:
        question = (
            "I didn't receive your question. "
            "Could you please describe what you need help with?"
        )
    elif len(query.split()) < 3:
        question = (
            f"Your request '{query}' is too vague. "
            "Could you provide more details about what you need?"
        )
    else:
        question = (
            "Could you provide more context? For example, the order ID, "
            "account details, or specific issue you're experiencing?"
        )
    
    return {
        "pending_question": question,
        "final_answer": question,
        "messages": ["clarify:requested_more_info"],
        "events": [make_event("clarify", "completed", "clarification question generated")],
    }


def tool_node(state: AgentState) -> dict:
    """Call a mock tool.

    Simulates transient failures for error-route scenarios to demonstrate retry loops.
    For ERROR route scenarios, fails on first 2 attempts, succeeds on 3rd.
    """
    attempt = int(state.get("attempt", 0))
    scenario_id = state.get("scenario_id", "unknown")
    route = state.get("route", "")
    
    # Simulate transient failures for ERROR route scenarios
    # This allows retry loop to be tested
    if route == Route.ERROR.value and attempt < 2:
        result = f"ERROR: transient failure (attempt={attempt}, scenario={scenario_id})"
        return {
            "tool_results": [result],
            "messages": [f"tool:failed_attempt_{attempt}"],
            "events": [make_event("tool", "error", f"transient failure on attempt {attempt}")],
        }
    
    # Success case - return mock data
    if "order" in state.get("query", "").lower():
        result = f"Order 12345: Status=Shipped, ETA=2 days (scenario={scenario_id})"
    else:
        result = f"Tool execution successful (scenario={scenario_id}, attempt={attempt})"
    
    return {
        "tool_results": [result],
        "messages": [f"tool:success_attempt_{attempt}"],
        "events": [
            make_event(
                "tool", "completed", f"tool executed successfully on attempt {attempt}"
            )
        ],
    }


def risky_action_node(state: AgentState) -> dict:
    """Prepare a risky action for approval.
    
    Creates a detailed proposed action with risk assessment and evidence.
    """
    query = state.get("query", "")
    risk_level = state.get("risk_level", "unknown")
    
    # Extract action type from query
    action_type = "unknown action"
    if "refund" in query.lower():
        action_type = "customer refund"
    elif "delete" in query.lower():
        action_type = "account deletion"
    elif "send" in query.lower():
        action_type = "external communication"
    elif "cancel" in query.lower():
        action_type = "order cancellation"
    
    proposed_action = (
        f"Prepare {action_type} (risk_level={risk_level}). "
        "Requires approval before execution."
    )
    
    return {
        "proposed_action": proposed_action,
        "messages": [f"risky_action:prepared_{action_type}"],
        "events": [
            make_event(
                "risky_action", "pending_approval", f"action prepared: {action_type}"
            )
        ],
    }


def approval_node(state: AgentState) -> dict:
    """Human approval step with optional LangGraph interrupt().

    Set LANGGRAPH_INTERRUPT=true to use real interrupt() for HITL demos.
    Default uses mock decision so tests and CI run offline.

    TODO(student): implement reject/edit decisions and timeout escalation.
    """
    import os

    if os.getenv("LANGGRAPH_INTERRUPT", "").lower() == "true":
        from langgraph.types import interrupt

        value = interrupt({
            "proposed_action": state.get("proposed_action"),
            "risk_level": state.get("risk_level"),
        })
        if isinstance(value, dict):
            decision = ApprovalDecision(**value)
        else:
            decision = ApprovalDecision(approved=bool(value))
    else:
        decision = ApprovalDecision(approved=True, comment="mock approval for lab")
    return {
        "approval": decision.model_dump(),
        "events": [make_event("approval", "completed", f"approved={decision.approved}")],
    }


def retry_or_fallback_node(state: AgentState) -> dict:
    """Record a retry attempt or fallback decision.
    
    Implements bounded retry with attempt tracking.
    Logs retry metadata for debugging and metrics.
    """
    attempt = int(state.get("attempt", 0)) + 1
    max_attempts = int(state.get("max_attempts", 3))
    scenario_id = state.get("scenario_id", "unknown")
    
    error_msg = f"Retry attempt {attempt}/{max_attempts} for scenario {scenario_id}"
    
    return {
        "attempt": attempt,
        "errors": [error_msg],
        "messages": [f"retry:attempt_{attempt}_of_{max_attempts}"],
        "events": [
            make_event(
                "retry",
                "completed",
                error_msg,
                attempt=attempt,
                max_attempts=max_attempts,
            )
        ],
    }


def answer_node(state: AgentState) -> dict:
    """Produce a final response.
    
    Grounds the answer in tool results, approval decisions, and query context.
    """
    query = state.get("query", "")
    tool_results = state.get("tool_results", [])
    approval = state.get("approval")
    route = state.get("route", "")
    
    # Generate context-aware answer
    if route == Route.RISKY.value and approval:
        if approval.get("approved"):
            result = tool_results[-1] if tool_results else "Completed successfully."
            answer = f"Action approved and executed. {result}"
        else:
            comment = approval.get("comment", "No comment provided")
            answer = f"Action rejected by reviewer: {comment}"
    elif tool_results:
        latest_result = tool_results[-1]
        if "ERROR" not in latest_result:
            answer = f"I found: {latest_result}"
        else:
            answer = f"Tool execution encountered an issue: {latest_result}"
    elif route == Route.SIMPLE.value:
        # Generate helpful response for simple queries
        if "password" in query.lower():
            answer = (
                "To reset your password, go to the login page and "
                "click 'Forgot Password'. Follow the email instructions."
            )
        else:
            answer = "I can help you with that. This is a standard support response."
    else:
        answer = "Request processed successfully."
    
    return {
        "final_answer": answer,
        "messages": ["answer:generated"],
        "events": [make_event("answer", "completed", f"answer generated for route={route}")],
    }


def evaluate_node(state: AgentState) -> dict:
    """Evaluate tool results — the 'done?' check that enables retry loops.
    
    This is a critical node for retry logic. It determines whether:
    - Tool execution succeeded → proceed to answer
    - Tool execution failed → retry (if attempts remaining)
    """
    tool_results = state.get("tool_results", [])
    attempt = int(state.get("attempt", 0))
    
    if not tool_results:
        return {
            "evaluation_result": "needs_retry",
            "errors": ["No tool results to evaluate"],
            "events": [make_event("evaluate", "completed", "no tool results, retry needed")],
        }
    
    latest = tool_results[-1]
    
    # Check for error indicators in tool result
    if "ERROR" in latest or "failure" in latest.lower():
        return {
            "evaluation_result": "needs_retry",
            "messages": [f"evaluate:failure_detected_attempt_{attempt}"],
            "events": [
                make_event(
                    "evaluate",
                    "completed",
                    f"tool failure detected on attempt {attempt}, retry needed",
                )
            ],
        }
    
    # Success case
    return {
        "evaluation_result": "success",
        "messages": [f"evaluate:success_attempt_{attempt}"],
        "events": [
            make_event(
                "evaluate",
                "completed",
                f"tool result satisfactory on attempt {attempt}",
            )
        ],
    }


def dead_letter_node(state: AgentState) -> dict:
    """Log unresolvable failures for manual review.

    Third layer of error strategy: retry -> fallback -> dead letter.
    This node is reached when max retry attempts are exhausted.
    """
    attempt = state.get("attempt", 0)
    max_attempts = state.get("max_attempts", 3)
    scenario_id = state.get("scenario_id", "unknown")
    
    error_summary = f"Scenario {scenario_id} failed after {attempt}/{max_attempts} attempts"
    
    return {
        "final_answer": (
            f"Request could not be completed after {max_attempts} retry attempts. "
            f"Logged for manual review. Reference: {scenario_id}"
        ),
        "messages": ["dead_letter:max_retries_exceeded"],
        "errors": [error_summary],
        "events": [
            make_event(
                "dead_letter",
                "completed",
                error_summary,
                attempt=attempt,
                max_attempts=max_attempts,
            )
        ],
    }


def finalize_node(state: AgentState) -> dict:
    """Finalize the run and emit a final audit event."""
    return {"events": [make_event("finalize", "completed", "workflow finished")]}
