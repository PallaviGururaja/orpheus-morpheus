from graph.state import AgentState


def after_plan(state: AgentState) -> str:
    return "handle_error" if state.get("error") else "write_code"


def after_write_code(state: AgentState) -> str:
    return "handle_error" if state.get("error") else "execute_code"


def after_inspect(state: AgentState) -> str:
    if not state.get("exec_error"):
        return "verify"
    if state.get("step", 0) < state.get("max_steps", 6):
        return "write_code"
    return "handle_error"


def after_verify(state: AgentState) -> str:
    if state.get("error"):
        return "handle_error"
    if not state.get("verified") and state.get("step", 0) < state.get("max_steps", 6):
        return "write_code"
    return "finalize"
