# Day 08 Lab Report

## 1. Team / student

- **Name**: Nguyễn Quang Trường-2A202600196
- **Repo**: https://github.com/luckyman2907/Lab_23-Nguyen_Quang_Truong_2A202600196
- **Date**: 2026-05-11

---

## 2. Architecture

### Graph Overview

The workflow implements a production-grade support ticket agent with 11 nodes and priority-based conditional routing:

```
START → intake → classify → [conditional routing]
  ├─ simple       → answer → finalize → END
  ├─ tool         → tool → evaluate → answer → finalize → END
  ├─ missing_info → clarify → finalize → END
  ├─ risky        → risky_action → approval → tool → evaluate → answer → finalize → END
  └─ error        → retry → tool → evaluate → [retry loop or dead_letter] → finalize → END
```

### Node Responsibilities

| Node | Purpose |
|---|---|
| **intake** | Normalize query, initialize state |
| **classify** | Priority-based keyword routing (risky > tool > missing_info > error > simple) |
| **answer** | Generate final response |
| **tool** | Execute mock tool (simulates API calls) |
| **evaluate** | Retry loop gate - checks if tool result needs retry |
| **clarify** | Ask for missing information |
| **risky_action** | Prepare high-risk action for approval |
| **approval** | HITL approval gate (uses `interrupt()` when enabled) |
| **retry** | Increment attempt counter, record retry event |
| **dead_letter** | Escalate unresolvable failures |
| **finalize** | Cleanup, audit trail, final validation |

### Routing Logic

**Priority-based classification** (checked in order):
1. **risky** (highest): refund, delete, send, cancel, remove, revoke
2. **tool**: status, order, lookup, check, track, find, search
3. **missing_info**: queries < 5 words with vague pronouns (it, that, this)
4. **error**: timeout, fail, error, crash, unavailable
5. **simple** (default): everything else

**Conditional edges**:
- `classify → route_after_classify`: Maps route string to next node
- `evaluate → route_after_evaluate`: `needs_retry` → retry, `success` → answer
- `retry → route_after_retry`: Bounded loop check (attempt < max_attempts)
- `approval → route_after_approval`: approved → tool, rejected → clarify

### Key Design Decisions

1. **Bounded retry loop**: `evaluate` node acts as "done?" gate (LangGraph advantage over LCEL)
2. **Priority routing**: Prevents keyword conflicts (e.g., "refund order" → risky, not tool)
3. **All paths terminate**: Every route reaches `finalize → END`
4. **Append-only audit**: messages, tool_results, errors, events use `add` reducer

---

## 3. State schema

| Field | Reducer | Why |
|---|---|---|
| `messages` | append (`add`) | Complete audit trail of execution steps |
| `tool_results` | append (`add`) | All tool outputs for debugging |
| `errors` | append (`add`) | All errors encountered during execution |
| `events` | append (`add`) | Structured event log for metrics |
| `route` | overwrite | Current routing decision only |
| `attempt` | overwrite | Current retry attempt counter |
| `final_answer` | overwrite | Latest response (only final one matters) |
| `evaluation_result` | overwrite | Latest evaluation (`needs_retry` or `success`) |
| `approval` | overwrite | Latest approval decision |
| `thread_id` | overwrite | Unique identifier per scenario run |
| `scenario_id` | overwrite | Scenario identifier for metrics |
| `query` | overwrite | User query (immutable after intake) |
| `max_attempts` | overwrite | Retry limit (from scenario config) |

**Design rationale**:
- **Append-only fields** provide complete audit trail for debugging and compliance
- **Overwrite fields** keep state lean and avoid memory bloat
- All fields are JSON-serializable for SQLite persistence

---

## 4. Scenario results

### Original 7 Scenarios (scenarios.jsonl)

| Scenario | Expected route | Actual route | Success | Nodes | Retries | Interrupts |
|---|---|---|---:|---:|---:|---:|
| S01_simple | simple | simple | ✅ | 4 | 0 | 0 |
| S02_tool | tool | tool | ✅ | 6 | 0 | 0 |
| S03_missing | missing_info | missing_info | ✅ | 4 | 0 | 0 |
| S04_risky | risky | risky | ✅ | 8 | 0 | 1 |
| S05_error | error | error | ✅ | 10 | 2 | 0 |
| S06_delete | risky | risky | ✅ | 8 | 0 | 1 |
| S07_dead_letter | error | error | ✅ | 5 | 1 | 0 |

**Summary**: 7/7 pass (100%), avg 6.43 nodes, 3 retries, 2 interrupts

### Hidden 15 Scenarios (scenarios_hidden.jsonl)

| Scenario | Expected route | Actual route | Success | Nodes | Retries | Interrupts |
|---|---|---|---:|---:|---:|---:|
| G01_simple | simple | simple | ✅ | 4 | 0 | 0 |
| G02_simple2 | simple | simple | ✅ | 4 | 0 | 0 |
| G03_tool | tool | tool | ✅ | 6 | 0 | 0 |
| G04_tool2 | tool | tool | ✅ | 6 | 0 | 0 |
| G05_tool3 | tool | tool | ✅ | 6 | 0 | 0 |
| G06_missing | missing_info | missing_info | ✅ | 4 | 0 | 0 |
| G07_missing2 | missing_info | missing_info | ✅ | 4 | 0 | 0 |
| G08_risky | risky | risky | ✅ | 8 | 0 | 1 |
| G09_risky2 | risky | risky | ✅ | 8 | 0 | 1 |
| G10_risky3 | risky | risky | ✅ | 8 | 0 | 1 |
| G11_risky4 | risky | risky | ✅ | 8 | 0 | 1 |
| G12_error | error | error | ✅ | 10 | 2 | 0 |
| G13_error2 | error | error | ✅ | 10 | 2 | 0 |
| G14_dead | error | error | ✅ | 5 | 1 | 0 |
| G15_mixed | risky | risky | ✅ | 8 | 0 | 1 |

**Summary**: 15/15 pass (100%), avg 6.6 nodes, 5 retries, 5 interrupts

### Overall Metrics

- **Total scenarios tested**: 22 (7 original + 15 hidden)
- **Success rate**: 100%
- **Average nodes visited**: 6.5
- **Total retries**: 8
- **Total interrupts**: 7
- **All tests pass**: 11/11 pytest tests ✅

---

## 5. Failure analysis

### 1. Retry Loop Failure (S05_error, G12_error, G13_error)

**Scenario**: Tool returns transient error (timeout, network failure)

**Behavior**:
- `tool_node` returns result containing "ERROR"
- `evaluate_node` detects error → sets `evaluation_result = "needs_retry"`
- `route_after_evaluate` routes to `retry` node
- `retry_node` increments `attempt` counter
- `route_after_retry` checks: `attempt < max_attempts` → back to `tool`
- Loop continues until success or max attempts exhausted

**Bounded loop protection**:
```python
if state["attempt"] >= state["max_attempts"]:
    return "dead_letter"  # Prevent infinite loop
return "tool"  # Try again
```

**Evidence**: S05_error retried 2 times before success (10 nodes visited)

### 2. Risky Action Without Approval (S04_risky, S06_delete)

**Scenario**: User requests destructive action (refund, delete, cancel)

**Behavior**:
- `classify_node` detects risky keywords → routes to `risky_action`
- `risky_action_node` prepares action, sets `proposed_action`
- `approval_node` checks for approval:
  - If `LANGGRAPH_INTERRUPT=true`: calls `interrupt()` → waits for human
  - Otherwise: mock approval (`approved=True`)
- `route_after_approval`:
  - `approved=True` → proceed to `tool`
  - `approved=False` → route to `clarify` (ask for more info)

**Safety guarantee**: Risky actions CANNOT execute without passing through approval node

**Evidence**: S04_risky and S06_delete both show `interrupt_count=1`, `approval_observed=true`

### 3. Dead Letter Escalation (S07_dead_letter, G14_dead)

**Scenario**: Unrecoverable failure after max retries

**Behavior**:
- Scenario sets `max_attempts=1` (immediate exhaustion)
- First retry fails → `attempt=1 >= max_attempts=1`
- `route_after_retry` routes to `dead_letter`
- `dead_letter_node` logs failure, sets final message
- Routes to `finalize → END`

**Evidence**: S07_dead_letter shows 5 nodes (intake → classify → retry → tool → evaluate → dead_letter → finalize), 1 retry, then escalation

---

## 6. Persistence / recovery evidence

### SQLite Checkpointer Implementation

**Configuration** (`configs/lab.yaml`):
```yaml
checkpointer: sqlite
```

**Implementation** (`persistence.py`):
```python
def build_checkpointer(config_type: str) -> BaseCheckpointSaver:
    if config_type == "sqlite":
        conn = sqlite3.connect("checkpoints.db", check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging
        saver = SqliteSaver(conn)
        saver.setup()  # Create tables
        return saver
    return MemorySaver()
```

### Evidence

**1. Database file created**:
```
checkpoints.db (311 KB)
checkpoints.db-shm
checkpoints.db-wal
```

**2. Thread ID per run**:
Each scenario gets unique thread_id:
- S01_simple → `thread-S01_simple`
- S02_tool → `thread-S02_tool`
- etc.

**3. Checkpoint count**:
- 7 scenarios × ~8 checkpoints/scenario = ~56 checkpoints
- Each node execution creates a checkpoint
- State snapshot includes all fields (messages, tool_results, errors, events)

**4. Crash recovery capability**:
- SQLite persists state to disk after each node
- If process crashes, can resume from last checkpoint:
```python
config = {"configurable": {"thread_id": "thread-S02_tool"}}
state = graph.get_state(config)  # Retrieve last checkpoint
graph.invoke(None, config)  # Resume from checkpoint
```

**5. State history**:
```python
history = graph.get_state_history(config)
for checkpoint in history:
    print(checkpoint.values)  # Time-travel debugging
```

### WAL Mode Benefits

- **Concurrent reads**: Multiple readers don't block
- **Atomic writes**: Checkpoint writes are atomic
- **Performance**: Faster than default rollback journal

---

## 7. Extension work

### Extension 1: SQLite Persistence 

**Implementation**: Full SQLite checkpointer with WAL mode, thread-safe connections, automatic table setup

**Evidence**: 
- Database file: `checkpoints.db` (311 KB)
- Config: `configs/lab.yaml` → `checkpointer: sqlite`
- Code: `src/langgraph_agent_lab/persistence.py`

### Extension 2: Streamlit HITL UI (Major Bonus)

**Implementation**: Production-ready Streamlit app (500+ lines) with:
- Interactive scenario selection
- Real-time execution visualization
- Approval/rejection interface with `interrupt()` support
- State visualization with metrics
- Execution history tracking

**Features**:
- Select scenario from dropdown
- Click "Run Scenario" → graph executes
- When approval needed → "Approve" / "Reject" buttons appear
- Shows state updates in real-time
- Displays final metrics

**Launch**: `streamlit run streamlit_app.py` or `run_streamlit.bat`

**Evidence**:
- File: `streamlit_app.py` (complete implementation)
- Launch script: `run_streamlit.bat`

### Extension 3: Graph Diagrams (Medium Bonus)

**Implementation**: Automated diagram generation in 4 formats

**Generated files** (in `outputs/`):
1. **Mermaid diagram** (`graph_diagram.md`): For GitHub/VS Code rendering
2. **ASCII art** (`graph_ascii.txt`): Terminal-friendly visualization
3. **Detailed flow** (`detailed_flow.md`): Complete documentation with routing logic
4. **PNG image** (`graph_diagram.png`): Visual diagram with graphviz

**Script**: `generate_graph_diagram.py`

**Evidence**: All 4 files present in `outputs/` directory

---

## 8. Improvement plan

If I had one more day, I would prioritize these production improvements:

### 1. Real LLM Integration (Highest Priority)

**Current**: Mock responses in all nodes
**Improvement**: 
- Integrate OpenAI/Anthropic API for `classify_node` and `answer_node`
- Use structured output (JSON mode) for classification
- Add prompt templates with few-shot examples
- Implement token counting and cost tracking

**Why**: Current keyword-based routing is brittle. LLM classification would handle:
- Ambiguous queries ("I need help" → missing_info)
- Multi-intent queries ("Check order and refund" → risky takes priority)
- Typos and variations ("refnd" → still detects risky)

### 2. Observability & Tracing

**Add**:
- LangSmith integration for trace visualization
- Structured logging (JSON logs with trace_id)
- Metrics dashboard (Grafana + Prometheus)
- Alert on dead_letter escalations

**Why**: Production systems need visibility into:
- Which routes are most common
- Where retries happen most
- Average latency per route
- Approval rejection rate

### 3. Advanced Retry Strategies

**Current**: Fixed retry with exponential backoff simulation
**Improvement**:
- Exponential backoff with jitter (avoid thundering herd)
- Circuit breaker pattern (stop retrying if service is down)
- Fallback to alternative tools (primary API fails → try backup)
- Retry budget per time window (rate limiting)

**Implementation**:
```python
def should_retry(state: AgentState) -> bool:
    if circuit_breaker.is_open():
        return False  # Service is down, don't retry
    if state["attempt"] >= state["max_attempts"]:
        return False
    backoff = min(2 ** state["attempt"] + random.uniform(0, 1), 60)
    time.sleep(backoff)
    return True
```

### 4. Parallel Tool Execution (Fan-out/Fan-in)

**Use case**: "Check order status AND refund policy"
**Implementation**:
```python
from langgraph.types import Send

def fan_out(state: AgentState) -> list[Send]:
    return [
        Send("tool_order_status", state),
        Send("tool_refund_policy", state),
    ]

# Results merge via add reducer
state["tool_results"] = [result1, result2]
```

**Why**: Reduces latency for multi-tool queries (parallel > sequential)

### 5. Real HITL with Slack/Email Integration

**Current**: Mock approval or Streamlit UI
**Improvement**:
- Send Slack message when approval needed
- Include approve/reject buttons (Slack interactive components)
- Email fallback if Slack fails
- Timeout after 5 minutes → auto-reject

**Why**: Real support teams use Slack, not Streamlit apps

### 6. Security & Compliance

**Add**:
- Input sanitization (prevent injection attacks)
- PII detection and masking (email, phone, SSN)
- Audit log encryption
- RBAC for approval (only managers can approve refunds > $100)

**Why**: Production systems handle sensitive customer data

### Priority Order

1. **LLM integration** (biggest impact on accuracy)
2. **Observability** (required for production debugging)
3. **Advanced retry** (improves reliability)
4. **Parallel tools** (improves latency)
5. **Real HITL** (improves UX for support teams)
6. **Security** (required for compliance)

---


