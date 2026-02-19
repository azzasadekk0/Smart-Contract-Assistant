# Smart Contract Summary and Q&A Assistant

This project implements the specification in `Smart_Contract_Assistant_Spec.docx (1).pdf`.

## Implemented Requirements

- Upload and ingestion of PDF/DOCX contract documents.
- Chunking, embedding, and vector storage (`Chroma` default, `FAISS` optional).
- Retrieval-augmented question answering with source citations.
- Conversation state tracking by `session_id`.
- Optional contract summarization endpoint.
- Guardrails for query safety and low-relevance fallback behavior.
- Evaluation pipeline with retrieval and answer quality metrics.
- FastAPI + LangServe backend microservice.
- Streamlit interface with chatbot + workspace layout.

## Project Structure

- `app/config.py`: Runtime settings via environment variables.
- `app/ingestion.py`: PDF/DOCX parsing and chunking.
- `app/vector_store.py`: Embedding model and vector DB integration.
- `app/rag.py`: Core retrieval, QA, citations, summarization, history.
- `app/api.py`: FastAPI endpoints and LangServe route.
- `app/evaluation.py`: Offline evaluation metrics runner.
- `ui/app.py`: Streamlit application.
- `tests/test_guardrails.py`: Basic tests.
- `docs/evaluation_report.md`: Evaluation report template.
- `docs/system_flow.md`: Mermaid system flow diagram.

## Setup

1. Create and activate a Python virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy env template and adjust values:

```bash
cp .env.example .env
# Windows PowerShell alternative:
# Copy-Item .env.example .env
```

## Run Backend

```bash
uvicorn app.api:app --host 127.0.0.1 --port 8000 --reload
```

### API Endpoints

- `GET /health`
- `POST /upload`
- `POST /chat`
- `GET /history/{session_id}`
- `POST /summarize`
- `POST /langserve/qa/invoke` (LangServe)

## Run Streamlit UI

```bash
streamlit run ui/app.py --server.address 127.0.0.1 --server.port 7860
```

UI will be served at `http://127.0.0.1:7860`.

## One-Command Startup (Windows)

Run:

```powershell
.\run_project.bat
```

This starts both backend and UI in the background.

## Evaluation

1. Ensure contracts are indexed first.
2. Run:

```bash
python -m app.evaluation --cases data/eval_cases.json
```

Metrics returned:
- `answer_overlap`
- `answer_f1`
- `retrieval_hit_rate`
- `source_recall`
- `source_precision`
- `groundedness`
- `required_term_coverage`
- `forbidden_term_violation_rate`
- `valid_case_rate`
- `success_rate`

Evaluation case fields (JSON):
- `question` (required)
- `expected_answer` (optional)
- `expected_sources` (optional list of filenames)
- `required_terms` (optional list of phrases expected in the answer)
- `forbidden_terms` (optional list of phrases that should not appear)

## Notes
- Default configuration uses local HuggingFace LLM + sentence-transformer embeddings.
- For OpenAI, set `LLM_PROVIDER=openai`, `EMBEDDING_PROVIDER=openai`, and `OPENAI_API_KEY` in `.env`.
- Security requirement is handled by local processing and storage only.
