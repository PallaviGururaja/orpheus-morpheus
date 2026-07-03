from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    session_id: str
    dataset_ids: list[str] = Field(default_factory=list)
    question: str
