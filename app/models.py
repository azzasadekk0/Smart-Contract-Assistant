from pydantic import BaseModel, Field


class Citation(BaseModel):
    source: str
    chunk_id: int | None = None
    relevance: float | None = None


class UploadResponse(BaseModel):
    indexed_files: list[str] = Field(default_factory=list)
    indexed_chunks: int = 0
    message: str = ""


class ChatRequest(BaseModel):
    session_id: str = "default"
    question: str


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    blocked: bool = False
    reason: str | None = None
    retrieved_contexts: list[str] = Field(default_factory=list)


class SummaryRequest(BaseModel):
    source: str | None = None


class SummaryResponse(BaseModel):
    source: str
    summary: str


class EvaluationRequest(BaseModel):
    cases_path: str = "data/eval_cases.json"


class EvaluationResponse(BaseModel):
    cases_path: str
    metrics: dict[str, float] = Field(default_factory=dict)
    cases_count: int = 0
