from sentence_transformers import SentenceTransformer
from rag.ingest import initialize_chroma, EMBED_MODEL

_embedder = None


def _get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        print(f"[RAG Retriever] Loading embedding model: {EMBED_MODEL}")
        _embedder = SentenceTransformer(EMBED_MODEL)
        print("[RAG Retriever] Embedding model ready")
    return _embedder


def retrieve_context(query: str, n_results: int = 3) -> str:
    print(f"[RAG Retriever] Querying for: '{query}' (top {n_results})")
    try:
        collection = initialize_chroma()

        if collection.count() == 0:
            print("[RAG Retriever] Collection is empty — returning empty context")
            return ""

        embedder = _get_embedder()
        query_embedding = embedder.encode([query]).tolist()

        actual_n = min(n_results, collection.count())
        results = collection.query(
            query_embeddings=query_embedding,
            n_results=actual_n,
            include=["documents", "metadatas", "distances"],
        )

        documents = results.get("documents", [[]])[0]
        if not documents:
            print("[RAG Retriever] No matching documents found")
            return ""

        context = "\n\n---\n\n".join(documents)
        print(f"[RAG Retriever] Retrieved {len(documents)} chunks")
        return context
    except Exception as e:
        error_msg = f"[RAG Retriever] Failed to retrieve context: {str(e)}"
        print(error_msg)
        return ""
