from langgraph.graph import StateGraph, END

from graph.state import AgentState
from graph.nodes import (
    plan,
    write_code,
    execute_code,
    inspect,
    verify,
    finalize,
    handle_error,
)
from graph.edges import after_plan, after_write_code, after_inspect, after_verify


def _build_graph():
    g = StateGraph(AgentState)

    g.add_node("plan", plan)
    g.add_node("write_code", write_code)
    g.add_node("execute_code", execute_code)
    g.add_node("inspect", inspect)
    g.add_node("verify", verify)
    g.add_node("finalize", finalize)
    g.add_node("handle_error", handle_error)

    g.set_entry_point("plan")

    g.add_conditional_edges(
        "plan", after_plan,
        {"write_code": "write_code", "handle_error": "handle_error"},
    )
    g.add_conditional_edges(
        "write_code", after_write_code,
        {"execute_code": "execute_code", "handle_error": "handle_error"},
    )
    g.add_edge("execute_code", "inspect")
    g.add_conditional_edges(
        "inspect", after_inspect,
        {"verify": "verify", "write_code": "write_code", "handle_error": "handle_error"},
    )
    g.add_conditional_edges(
        "verify", after_verify,
        {"write_code": "write_code", "finalize": "finalize", "handle_error": "handle_error"},
    )
    g.add_edge("finalize", END)
    g.add_edge("handle_error", END)

    return g.compile()


agentic_ai = _build_graph()
