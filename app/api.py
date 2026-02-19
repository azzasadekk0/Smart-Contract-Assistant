from pathlib import Path
import sys
from uuid import uuid4
import json

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from langserve import add_routes

from app.config import get_settings
from app.evaluation import evaluate_cases
from app.models import (
    ChatRequest,
    ChatResponse,
    EvaluationRequest,
    EvaluationResponse,
    SummaryRequest,
    SummaryResponse,
    UploadResponse,
)
from app.rag import RAGService

# Ensure Unicode output from LangServe startup logs works on Windows shells.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

settings = get_settings()
service = RAGService(settings)
upload_dir = Path("data/uploads")
upload_dir.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Smart Contract Summary and Q&A Assistant", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/upload", response_model=UploadResponse)
async def upload_documents(files: list[UploadFile] = File(...)) -> UploadResponse:
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    stored_paths: list[Path] = []
    source_name_overrides: dict[str, str] = {}
    for file in files:
        name = file.filename or "uploaded_file"
        suffix = Path(name).suffix.lower()
        if suffix not in {".pdf", ".docx"}:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")

        target_path = upload_dir / f"{uuid4().hex}_{Path(name).name}"
        target_path.write_bytes(await file.read())
        stored_paths.append(target_path)
        source_name_overrides[str(target_path)] = Path(name).name

    indexed_chunks, indexed_sources = service.ingest(stored_paths, source_name_overrides)
    return UploadResponse(
        indexed_files=indexed_sources,
        indexed_chunks=indexed_chunks,
        message=f"Indexed {indexed_chunks} chunks from {len(indexed_sources)} file(s).",
    )


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    return service.answer(request.question, request.session_id)


@app.get("/history/{session_id}")
def history(session_id: str) -> dict[str, list[dict[str, str]]]:
    return {"session_id": session_id, "messages": service.get_history(session_id)}


@app.post("/summarize", response_model=SummaryResponse)
def summarize(request: SummaryRequest) -> SummaryResponse:
    return service.summarize(request.source)


@app.post("/evaluate", response_model=EvaluationResponse)
def evaluate(request: EvaluationRequest) -> EvaluationResponse:
    cases_path = Path(request.cases_path)
    if not cases_path.exists():
        raise HTTPException(status_code=404, detail=f"Evaluation cases file not found: {cases_path}")

    try:
        cases_data = json.loads(cases_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid evaluation JSON: {exc}") from exc

    if not isinstance(cases_data, list):
        raise HTTPException(status_code=400, detail="Evaluation file must be a JSON array of test cases.")

    metrics = evaluate_cases(service, cases_data)
    return EvaluationResponse(
        cases_path=str(cases_path),
        metrics=metrics,
        cases_count=len(cases_data),
    )


add_routes(app, service.qa_runnable(), path="/langserve/qa")
