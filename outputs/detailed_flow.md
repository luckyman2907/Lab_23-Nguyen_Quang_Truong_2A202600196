# Detailed Workflow Flow

## Scenario Routes

### 1. Simple Route (S01)
```
START → intake → classify → answer → finalize → END
```
**Nodes visited**: 4  
**Use case**: Informational queries (e.g., "How do I reset my password?")

### 2. Tool Route (S02)
```
START → intake → classify → tool → evaluate → answer → finalize → END
```
**Nodes visited**: 6  
**Use case**: Data lookup queries (e.g., "Check order status for 12345")

### 3. Missing Info Route (S03)
```
START → intake → classify → clarify → finalize → END
```
**Nodes visited**: 4  
**Use case**: Vague queries (e.g., "Can you fix it?")

### 4. Risky Route with HITL (S04, S06)
```
START → intake → classify → risky_action → approval → tool → evaluate → answer → finalize → END
```
**Nodes visited**: 8  
**Use case**: High-risk actions requiring approval (e.g., "Refund customer")  
**Special**: Interrupts at approval node for human decision

### 5. Error Route with Retry (S05)
```
START → intake → classify → retry → tool → evaluate → retry → tool → evaluate → answer → finalize → END
```
**Nodes visited**: 10  
**Use case**: Transient failures (e.g., "Timeout failure")  
**Special**: Retry loop with bounded attempts (max 3)

### 6. Dead Letter Route (S07)
```
START → intake → classify → retry → tool → evaluate → retry → dead_letter → finalize → END
```
**Nodes visited**: 5  
**Use case**: Unresolvable failures (e.g., "System failure cannot recover")  
**Special**: Exhausts retries (max=1) and escalates to dead letter

## Retry Loop Mechanics

The retry loop is the most complex part of the workflow:

```
tool → evaluate → [decision point]
                   ├─ success → answer
                   └─ needs_retry → retry → [bounded check]
                                            ├─ attempt < max → tool (loop back)
                                            └─ attempt >= max → dead_letter
```

**Key Components**:
1. **evaluate_node**: Acts as "done?" check (LangGraph advantage over LCEL)
2. **retry_or_fallback_node**: Increments attempt counter
3. **route_after_retry**: Enforces bounded loop (prevents infinite retries)
4. **dead_letter_node**: Escalates unresolvable failures

## HITL Approval Flow

For risky actions (S04, S06):

```
risky_action → approval → [interrupt] → [human decision]
                                        ├─ approved → tool → evaluate → answer
                                        └─ rejected → clarify
```

**Implementation**:
- Uses `interrupt()` when `LANGGRAPH_INTERRUPT=true`
- Waits for human decision (approve/reject)
- Logs reviewer and comment
- Resumes execution after decision

## State Transitions

### Append-Only Fields (Audit Trail)
- `messages`: Execution steps
- `tool_results`: All tool outputs
- `errors`: All errors encountered
- `events`: Complete audit trail

### Overwrite Fields (Current State)
- `route`: Current routing decision
- `attempt`: Current retry attempt
- `final_answer`: Final response
- `evaluation_result`: Latest evaluation

## Error Handling Strategy

Three-layer approach:

1. **Retry**: Transient failures (network timeout, rate limit)
2. **Fallback**: Alternative approach (not implemented in basic version)
3. **Dead Letter**: Escalate to human review

## Checkpointing

Every node execution creates a checkpoint:
- State snapshot saved to SQLite
- Parent-child relationships maintained
- Enables time-travel debugging
- Supports crash recovery

## Performance Characteristics

| Route | Avg Nodes | Retries | Interrupts | Latency |
|-------|-----------|---------|------------|---------|
| Simple | 4 | 0 | 0 | Low |
| Tool | 6 | 0 | 0 | Medium |
| Missing Info | 4 | 0 | 0 | Low |
| Risky | 8 | 0 | 1 | High (HITL) |
| Error (success) | 10 | 2 | 0 | High (retries) |
| Dead Letter | 5 | 1 | 0 | Medium |

**Average**: 6.43 nodes per execution
