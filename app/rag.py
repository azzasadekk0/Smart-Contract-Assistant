from collections import defaultdict
import re
from typing import Any

from langchain_core.runnables import RunnableLambda

from app.config import AppSettings
from app.guardrails import check_query_safety, grounding_ratio
from app.ingestion import ingest_files
from app.models import ChatResponse, Citation, SummaryResponse
from app.vector_store import VectorStoreManager


class _FallbackLLM:
    def invoke(self, prompt: str) -> str:
        marker = "Context:\n"
        if marker in prompt:
            context = prompt.split(marker, maxsplit=1)[-1]
            first_block = context.split("\n\n", maxsplit=1)[0]
            return f"Fallback response (no local LLM available): {first_block[:400]}"
        return "Fallback response (no local LLM available)."


class RAGService:
    def __init__(self, settings: AppSettings):
        self.settings = settings
        self.vector_store = VectorStoreManager(settings)
        self._llm: Any | None = None
        self.history: dict[str, list[dict[str, str]]] = defaultdict(list)
        self.source_chunks: dict[str, list[str]] = defaultdict(list)

    @property
    def llm(self) -> Any:
        if self._llm is not None:
            return self._llm

        provider = self.settings.llm_provider.lower()
        if provider == "openai":
            try:
                from langchain_openai import ChatOpenAI

                self._llm = ChatOpenAI(
                    model=self.settings.openai_chat_model,
                    temperature=0,
                    api_key=self.settings.openai_api_key,
                )
            except Exception:
                self._llm = _FallbackLLM()
            return self._llm

        try:
            from langchain_community.llms import HuggingFacePipeline
            from transformers import pipeline

            generator = pipeline(
                task="text2text-generation",
                model=self.settings.hf_model_name,
                max_new_tokens=384,
                do_sample=False,
            )
            self._llm = HuggingFacePipeline(pipeline=generator)
        except Exception:
            self._llm = _FallbackLLM()
        return self._llm

    @staticmethod
    def _render_llm_output(output: Any) -> str:
        return output.content if hasattr(output, "content") else str(output)

    @staticmethod
    def _normalize_source_name(source: str) -> str:
        return re.sub(r"^[0-9a-fA-F]{32}_", "", source)

    def ingest(
        self,
        paths: list[Any],
        source_name_overrides: dict[str, str] | None = None,
    ) -> tuple[int, list[str]]:
        documents = ingest_files(paths, self.settings, source_name_overrides)
        indexed_sources = sorted({
            self._normalize_source_name(str(doc.metadata.get("source", "unknown")))
            for doc in documents
        })

        # For Chroma, replace previously indexed chunks for same source names.
        self.vector_store.delete_by_sources(indexed_sources)

        for source in indexed_sources:
            self.source_chunks[source] = []

        for doc in documents:
            source = self._normalize_source_name(str(doc.metadata.get("source", "unknown")))
            doc.metadata["source"] = source

        self.vector_store.add_documents(documents)

        for doc in documents:
            source = str(doc.metadata.get("source", "unknown"))
            self.source_chunks[source].append(doc.page_content)

        return len(documents), indexed_sources

    def answer(self, question: str, session_id: str) -> ChatResponse:
        is_safe, reason = check_query_safety(question, self.settings.max_query_chars)
        if not is_safe:
            return ChatResponse(
                session_id=session_id,
                answer="I cannot process that request.",
                blocked=True,
                reason=reason,
            )

        retrieved = self.vector_store.similarity_search_with_scores(question, self.settings.top_k)
        if not retrieved:
            return ChatResponse(
                session_id=session_id,
                answer="I do not have indexed documents yet. Upload a contract first.",
                blocked=False,
                reason="No indexed data.",
            )

        top_score = max(score for _, score in retrieved)
        if top_score < self.settings.guardrail_min_relevance:
            return ChatResponse(
                session_id=session_id,
                answer="I do not have enough evidence in the uploaded documents to answer that.",
                blocked=False,
                reason="Low retrieval relevance.",
            )

        unique_retrieved: list[tuple[Any, float]] = []
        seen_doc_keys: set[tuple[str, int | None, int]] = set()
        for doc, score in retrieved:
            source = self._normalize_source_name(str(doc.metadata.get("source", "unknown")))
            chunk_id = int(doc.metadata.get("chunk_id", 0)) or None
            key = (source, chunk_id, hash(doc.page_content))
            if key in seen_doc_keys:
                continue
            seen_doc_keys.add(key)
            doc.metadata["source"] = source
            unique_retrieved.append((doc, score))

        contexts: list[str] = []
        citations: list[Citation] = []
        context_blocks: list[str] = []
        for idx, (doc, score) in enumerate(unique_retrieved, start=1):
            contexts.append(doc.page_content)
            context_blocks.append(f"[{idx}] {doc.page_content}")
            citations.append(
                Citation(
                    source=str(doc.metadata.get("source", "unknown")),
                    chunk_id=int(doc.metadata.get("chunk_id", 0)) or None,
                    relevance=round(float(score), 4),
                )
            )

        citations = citations[:10]

        prompt = (
            "You are a smart contract assistant. "
            "Answer strictly using the provided context. "
            "If the answer is not present, say you do not have enough information.\n\n"
            f"Question: {question}\n\n"
            "Context:\n"
            + "\n\n".join(context_blocks)
            + "\n\n"
            "Return a concise answer with inline citations like [1], [2]."
        )

        llm_output = self.llm.invoke(prompt)
        answer_text = self._render_llm_output(llm_output)

        if grounding_ratio(answer_text, contexts) < 0.2:
            answer_text += "\n\nNote: confidence is low because evidence overlap is limited."

        self.history[session_id].append({"role": "user", "content": question})
        self.history[session_id].append({"role": "assistant", "content": answer_text})

        return ChatResponse(
            session_id=session_id,
            answer=answer_text,
            citations=citations,
            blocked=False,
            reason=None,
            retrieved_contexts=contexts,
        )

    def summarize(self, source: str | None = None) -> SummaryResponse:
        if source:
            chunks = self.source_chunks.get(source, [])
            if not chunks:
                matches = [
                    key for key in self.source_chunks
                    if key.endswith(source) or key.endswith(f"_{source}")
                ]
                if len(matches) == 1:
                    chunks = self.source_chunks[matches[0]]
            if not chunks:
                return SummaryResponse(source=source, summary="No chunks found for this source.")
            source_name = source
        else:
            if not self.source_chunks:
                return SummaryResponse(source="all", summary="No indexed documents to summarize.")
            source_name = "all"
            chunks = [chunk for source_chunks in self.source_chunks.values() for chunk in source_chunks]

        text = "\n\n".join(chunks[:8])
        prompt = (
            "Summarize the following contract content in bullet points. "
            "Include key obligations, durations, payment terms, and termination clauses if present.\n\n"
            f"Content:\n{text}"
        )
        llm_output = self.llm.invoke(prompt)
        summary_text = self._render_llm_output(llm_output)
        return SummaryResponse(source=source_name, summary=summary_text)

    def get_history(self, session_id: str) -> list[dict[str, str]]:
        return self.history.get(session_id, [])

    def qa_runnable(self) -> RunnableLambda:
        def _run(payload: dict[str, Any]) -> dict[str, Any]:
            question = str(payload.get("question", "")).strip()
            session_id = str(payload.get("session_id", "langserve"))
            response = self.answer(question, session_id)
            return response.model_dump()

        return RunnableLambda(_run)
