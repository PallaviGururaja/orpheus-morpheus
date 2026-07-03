from typing import TypedDict


class AgentState(TypedDict, total=False):
    # Identity
    run_id: str
    session_id: str
    dataset_ids: list[str]

    # Input
    question: str
    profile: dict           # (legacy) first dataset's profile
    profiles: dict          # Phase 2: table_name -> profile, all in-scope datasets
    messages: list          # prior chat turns [{role, content}]

    # Pipeline data (populated progressively)
    plan: str
    code: str
    exec_stdout: str
    exec_error: str | None
    result_repr: str
    result_table: list[dict]
    step: int
    max_steps: int

    # Output
    answer_text: str
    chart_spec: dict | None
    verified: bool
    followups: list[str]

    # Token / timing accounting
    prompt_tokens: int
    completion_tokens: int

    # Control
    error: str | None
    status: str
