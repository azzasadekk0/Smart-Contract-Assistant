from pathlib import Path
import shutil
from typing import Any

from app.config import AppSettings


def build_embeddings(settings: AppSettings) -> Any:
    provider = settings.embedding_provider.lower()

    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(
            model="text-embedding-3-small",
            api_key=settings.openai_api_key,
        )

    from langchain_community.embeddings import FakeEmbeddings, HuggingFaceEmbeddings

    try:
        return HuggingFaceEmbeddings(model_name=settings.embedding_model_name)
    except Exception:
        # Keeps local development functional when large embedding model dependencies are unavailable.
        return FakeEmbeddings(size=384)


class VectorStoreManager:
    def __init__(self, settings: AppSettings):
        self.settings = settings
        self.store_dir = Path(settings.vector_store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.embeddings = build_embeddings(settings)
        self.vectorstore: Any | None = None
        self.backend = settings.vector_backend.lower()
        self._init_store_if_available()

    def _init_store_if_available(self) -> None:
        if self.backend == "chroma":
            from langchain_community.vectorstores import Chroma

            self.vectorstore = Chroma(
                collection_name="smart_contract_assistant",
                persist_directory=str(self.store_dir),
                embedding_function=self.embeddings,
            )
            return

        if self.backend == "faiss":
            index_file = self.store_dir / "index.faiss"
            if index_file.exists():
                from langchain_community.vectorstores import FAISS

                self.vectorstore = FAISS.load_local(
                    str(self.store_dir),
                    self.embeddings,
                    allow_dangerous_deserialization=True,
                )
            return

        raise ValueError("VECTOR_BACKEND must be 'chroma' or 'faiss'.")

    def add_documents(self, documents: list[Any]) -> None:
        if not documents:
            return

        if self.backend == "chroma":
            try:
                self.vectorstore.add_documents(documents)
            except Exception as exc:
                message = str(exc)
                if "InvalidDimensionException" in message or "Embedding dimension" in message:
                    self._reset_chroma_collection()
                    self.vectorstore.add_documents(documents)
                else:
                    raise
            try:
                self.vectorstore.persist()
            except Exception:
                # Newer Chroma versions auto-persist.
                pass
            return

        if self.vectorstore is None:
            from langchain_community.vectorstores import FAISS

            self.vectorstore = FAISS.from_documents(documents, self.embeddings)
        else:
            self.vectorstore.add_documents(documents)
        self.vectorstore.save_local(str(self.store_dir))

    def delete_by_sources(self, sources: list[str]) -> None:
        if self.vectorstore is None or self.backend != "chroma":
            return

        unique_sources = [source for source in dict.fromkeys(sources) if source]
        for source in unique_sources:
            try:
                self.vectorstore.delete(where={"source": source})
            except Exception:
                collection = getattr(self.vectorstore, "_collection", None)
                if collection is not None:
                    try:
                        collection.delete(where={"source": source})
                    except Exception:
                        continue

        try:
            self.vectorstore.persist()
        except Exception:
            pass

    def _reset_chroma_collection(self) -> None:
        if self.backend != "chroma" or self.vectorstore is None:
            return

        collection_name = "smart_contract_assistant"
        try:
            collection_name = getattr(self.vectorstore, "_collection_name", collection_name)
        except Exception:
            pass

        try:
            client = getattr(self.vectorstore, "_client", None)
            if client is not None:
                client.delete_collection(collection_name)
        except Exception:
            pass

        # Fallback cleanup of persisted local DB files if needed.
        try:
            for child in self.store_dir.iterdir():
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                else:
                    child.unlink(missing_ok=True)
        except Exception:
            pass

        from langchain_community.vectorstores import Chroma

        self.vectorstore = Chroma(
            collection_name=collection_name,
            persist_directory=str(self.store_dir),
            embedding_function=self.embeddings,
        )

    def similarity_search_with_scores(self, query: str, k: int) -> list[tuple[Any, float]]:
        if self.vectorstore is None:
            return []

        if self.backend == "chroma":
            results = self.vectorstore.similarity_search_with_relevance_scores(query, k=k)
            return [(doc, float(score)) for doc, score in results]

        if hasattr(self.vectorstore, "similarity_search_with_relevance_scores"):
            results = self.vectorstore.similarity_search_with_relevance_scores(query, k=k)
            return [(doc, float(score)) for doc, score in results]

        distance_results = self.vectorstore.similarity_search_with_score(query, k=k)
        return [(doc, 1.0 / (1.0 + float(distance))) for doc, distance in distance_results]
