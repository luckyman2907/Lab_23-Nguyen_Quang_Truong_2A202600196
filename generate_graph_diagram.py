"""Generate graph diagram in multiple formats.

This script generates visual representations of the LangGraph workflow:
1. Mermaid diagram (for markdown/documentation)
2. ASCII art (for terminal/text files)
3. PNG image (if graphviz installed)
"""

from rich.console import Console
from rich.panel import Panel

from langgraph_agent_lab.graph import build_graph
from langgraph_agent_lab.persistence import build_checkpointer

console = Console()


def generate_mermaid_diagram():
    """Generate Mermaid diagram for documentation."""
    console.print("\n[bold cyan]Generating Mermaid Diagram...[/bold cyan]\n")
    
    # Build graph without checkpointer for diagram
    graph = build_graph(checkpointer=None)
    
    # Get Mermaid representation
    try:
        mermaid = graph.get_graph().draw_mermaid()
        
        # Save to file
        with open("outputs/graph_diagram.md", "w", encoding="utf-8") as f:
            f.write("# LangGraph Workflow Diagram\n\n")
            f.write("## Architecture Overview\n\n")
            f.write("This diagram shows the complete workflow with all nodes, edges, and conditional routing.\n\n")
            f.write("```mermaid\n")
            f.write(mermaid)
            f.write("\n```\n\n")
            f.write("## Node Descriptions\n\n")
            f.write("- **intake**: Normalize and validate query\n")
            f.write("- **classify**: Route based on keywords (priority-based)\n")
            f.write("- **answer**: Generate final response\n")
            f.write("- **tool**: Execute mock tool\n")
            f.write("- **evaluate**: Check if tool result is satisfactory (retry gate)\n")
            f.write("- **clarify**: Ask for missing information\n")
            f.write("- **risky_action**: Prepare high-risk action\n")
            f.write("- **approval**: HITL approval gate\n")
            f.write("- **retry**: Record retry attempt\n")
            f.write("- **dead_letter**: Escalate unresolvable failure\n")
            f.write("- **finalize**: Cleanup and final audit\n\n")
            f.write("## Routing Logic\n\n")
            f.write("### After Classify\n")
            f.write("- `simple` → answer\n")
            f.write("- `tool` → tool\n")
            f.write("- `missing_info` → clarify\n")
            f.write("- `risky` → risky_action\n")
            f.write("- `error` → retry\n\n")
            f.write("### After Evaluate (Retry Loop Gate)\n")
            f.write("- `needs_retry` → retry\n")
            f.write("- `success` → answer\n\n")
            f.write("### After Retry (Bounded Loop)\n")
            f.write("- `attempt < max_attempts` → tool\n")
            f.write("- `attempt >= max_attempts` → dead_letter\n\n")
            f.write("### After Approval\n")
            f.write("- `approved=true` → tool\n")
            f.write("- `approved=false` → clarify\n")
        
        console.print(f"[green]✓ Mermaid diagram saved to: outputs/graph_diagram.md[/green]")
        console.print(f"[yellow]Preview: {len(mermaid)} characters[/yellow]\n")
        
        return mermaid
        
    except Exception as e:
        console.print(f"[red]Error generating Mermaid diagram: {e}[/red]")
        return None


def generate_ascii_diagram():
    """Generate ASCII art diagram for text files."""
    console.print("\n[bold cyan]Generating ASCII Diagram...[/bold cyan]\n")
    
    ascii_art = """
╔════════════════════════════════════════════════════════════════════════════╗
║                    LangGraph Agent Workflow Architecture                   ║
╚════════════════════════════════════════════════════════════════════════════╝

                                  ┌─────────┐
                                  │  START  │
                                  └────┬────┘
                                       │
                                       ▼
                                  ┌─────────┐
                                  │ intake  │
                                  └────┬────┘
                                       │
                                       ▼
                                  ┌──────────┐
                                  │ classify │
                                  └────┬─────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    │                  │                  │
                    ▼                  ▼                  ▼
              ┌─────────┐        ┌─────────┐       ┌──────────┐
              │ simple  │        │  tool   │       │  risky   │
              └────┬────┘        └────┬────┘       └────┬─────┘
                   │                  │                  │
                   │                  ▼                  ▼
                   │            ┌──────────┐      ┌──────────────┐
                   │            │ evaluate │      │ risky_action │
                   │            └────┬─────┘      └──────┬───────┘
                   │                 │                    │
                   │        ┌────────┴────────┐           ▼
                   │        │                 │     ┌──────────┐
                   │        ▼                 ▼     │ approval │
                   │   ┌────────┐       ┌────────┐ └────┬─────┘
                   │   │ retry  │       │success │      │
                   │   └───┬────┘       └───┬────┘      │
                   │       │                │            │
                   │       │◄───────────────┘            │
                   │       │                             │
                   │       ▼                             ▼
                   │  ┌─────────┐                  ┌─────────┐
                   │  │  tool   │◄─────────────────┤ (tool)  │
                   │  └────┬────┘                  └─────────┘
                   │       │
                   │       ▼
                   │  ┌──────────┐
                   │  │ evaluate │
                   │  └────┬─────┘
                   │       │
                   │  ┌────┴────┐
                   │  │         │
                   │  ▼         ▼
                   │ retry   success
                   │  │         │
                   │  └─────────┤
                   │            │
                   ▼            ▼
              ┌─────────┐  ┌─────────┐
              │ answer  │  │ answer  │
              └────┬────┘  └────┬────┘
                   │            │
                   └──────┬─────┘
                          │
                          ▼
                    ┌──────────┐
                    │ finalize │
                    └────┬─────┘
                         │
                         ▼
                    ┌─────────┐
                    │   END   │
                    └─────────┘

╔════════════════════════════════════════════════════════════════════════════╗
║                              Key Features                                   ║
╠════════════════════════════════════════════════════════════════════════════╣
║ • Priority-based routing (risky > tool > missing_info > error > simple)    ║
║ • Bounded retry loop (max_attempts prevents infinite loops)                ║
║ • HITL approval for risky actions (interrupt-based)                        ║
║ • Dead letter queue for unresolvable failures                              ║
║ • All paths terminate at finalize → END                                    ║
╚════════════════════════════════════════════════════════════════════════════╝

╔════════════════════════════════════════════════════════════════════════════╗
║                           Routing Conditions                                ║
╠════════════════════════════════════════════════════════════════════════════╣
║ classify → simple:       Default route (informational queries)             ║
║ classify → tool:         Keywords: status, order, lookup, check, track     ║
║ classify → missing_info: Short queries (<5 words) with vague pronouns      ║
║ classify → risky:        Keywords: refund, delete, send, cancel, remove    ║
║ classify → error:        Keywords: timeout, fail, error, crash             ║
║                                                                             ║
║ evaluate → retry:        Tool result contains "ERROR"                      ║
║ evaluate → answer:       Tool result is satisfactory                       ║
║                                                                             ║
║ retry → tool:            attempt < max_attempts                            ║
║ retry → dead_letter:     attempt >= max_attempts                           ║
║                                                                             ║
║ approval → tool:         approved = true                                   ║
║ approval → clarify:      approved = false                                  ║
╚════════════════════════════════════════════════════════════════════════════╝
"""
    
    # Save to file
    with open("outputs/graph_ascii.txt", "w", encoding="utf-8") as f:
        f.write(ascii_art)
    
    console.print(ascii_art)
    console.print(f"[green]✓ ASCII diagram saved to: outputs/graph_ascii.txt[/green]\n")
    
    return ascii_art


def generate_detailed_flow():
    """Generate detailed flow description."""
    console.print("\n[bold cyan]Generating Detailed Flow Description...[/bold cyan]\n")
    
    flow_doc = """# Detailed Workflow Flow

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
"""
    
    # Save to file
    with open("outputs/detailed_flow.md", "w", encoding="utf-8") as f:
        f.write(flow_doc)
    
    console.print(f"[green]✓ Detailed flow saved to: outputs/detailed_flow.md[/green]\n")
    
    return flow_doc


def generate_png_diagram():
    """Generate PNG diagram using graphviz (if available)."""
    console.print("\n[bold cyan]Attempting to Generate PNG Diagram...[/bold cyan]\n")
    
    try:
        from langgraph_agent_lab.graph import build_graph
        
        graph = build_graph(checkpointer=None)
        
        # Try to generate PNG
        try:
            png_data = graph.get_graph().draw_mermaid_png()
            
            with open("outputs/graph_diagram.png", "wb") as f:
                f.write(png_data)
            
            console.print(f"[green]✓ PNG diagram saved to: outputs/graph_diagram.png[/green]\n")
            return True
            
        except Exception as e:
            console.print(f"[yellow]⚠ PNG generation not available: {e}[/yellow]")
            console.print(f"[yellow]  Install graphviz to enable PNG export[/yellow]\n")
            return False
            
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]\n")
        return False


def main():
    """Generate all diagram formats."""
    console.print(Panel.fit(
        "[bold cyan]LangGraph Diagram Generator[/bold cyan]\n"
        "Generating visual representations of the workflow",
        border_style="cyan"
    ))
    
    # Create outputs directory if it doesn't exist
    import os
    os.makedirs("outputs", exist_ok=True)
    
    # Generate all formats
    results = {}
    
    # 1. Mermaid diagram
    results['mermaid'] = generate_mermaid_diagram()
    
    # 2. ASCII diagram
    results['ascii'] = generate_ascii_diagram()
    
    # 3. Detailed flow
    results['flow'] = generate_detailed_flow()
    
    # 4. PNG diagram (optional)
    results['png'] = generate_png_diagram()
    
    # Summary
    console.print("\n" + "="*80 + "\n")
    console.print(Panel.fit(
        "[bold green]✓ Diagram Generation Complete![/bold green]\n\n"
        "Generated files:\n"
        "  • outputs/graph_diagram.md (Mermaid)\n"
        "  • outputs/graph_ascii.txt (ASCII art)\n"
        "  • outputs/detailed_flow.md (Flow description)\n"
        + ("  • outputs/graph_diagram.png (PNG image)\n" if results['png'] else ""),
        border_style="green"
    ))
    
    console.print("\n[bold cyan]Usage:[/bold cyan]")
    console.print("  • View Mermaid: Open outputs/graph_diagram.md in GitHub/VS Code")
    console.print("  • View ASCII: cat outputs/graph_ascii.txt")
    console.print("  • View Flow: Open outputs/detailed_flow.md")
    if results['png']:
        console.print("  • View PNG: Open outputs/graph_diagram.png")
    
    console.print("\n[bold cyan]Include in Report:[/bold cyan]")
    console.print("  Add to Section 7 (Extension Work) in lab report")
    console.print("  Reference: 'Generated graph diagrams in multiple formats'")


if __name__ == "__main__":
    main()
