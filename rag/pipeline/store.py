"""ChromaDB persistence for chunks + community summaries.

`build_store(...)` is destructive — it wipes both collections before
recreating them. `open_store(...)` is the read-only path used by retrieval.
Both share the same Ollama-backed embedding function.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import chromadb
import httpx
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

from rag.pipeline.extract import Chunk

CHUNKS_COLLECTION = "graph_rag_chunks"
COMMUNITIES_COLLECTION = "graph_rag_communities"


class OllamaEmbeddingFunction(EmbeddingFunction):
    """ChromaDB-compatible embedding function that calls Ollama's `/api/embed`."""

    def __init__(self, model: str = "nomic-embed-text", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url

    def __call__(self, input: Documents) -> Embeddings:
        embeddings: list[list[float]] = []
        batch_size = 32
        for i in range(0, len(input), batch_size):
            batch = input[i : i + batch_size]
            response = httpx.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": batch},
                timeout=120.0,
            )
            response.raise_for_status()
            embeddings.extend(response.json()["embeddings"])
        return embeddings


@dataclass(slots=True)
class Store:
    client: chromadb.api.ClientAPI
    chunks: chromadb.api.models.Collection.Collection
    communities: chromadb.api.models.Collection.Collection


def build_store(
    chunks: list[Chunk],
    community_summaries: dict[int, dict],
    *,
    persist_dir: Path,
    embed_model: str = "nomic-embed-text",
    ollama_base_url: str = "http://localhost:11434",
    batch_size: int = 50,
    verbose: bool = True,
) -> Store:
    """Wipe + rebuild both collections at `persist_dir`. Returns the open `Store`.

    The chunks collection keys by `Chunk.id`; the community collection keys
    by ``community_<id>``.
    """
    embed_fn = OllamaEmbeddingFunction(model=embed_model, base_url=ollama_base_url)
    client = chromadb.PersistentClient(path=str(persist_dir.resolve()))

    for name in (CHUNKS_COLLECTION, COMMUNITIES_COLLECTION):
        try:
            client.delete_collection(name)
        except (ValueError, chromadb.errors.NotFoundError):
            pass

    chunks_collection = client.create_collection(
        name=CHUNKS_COLLECTION,
        embedding_function=embed_fn,
        metadata={"hnsw:space": "cosine"},
    )

    if verbose:
        print(f"Adding {len(chunks)} chunks...")
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        chunks_collection.add(
            ids=[c.id for c in batch],
            documents=[c.text for c in batch],
            metadatas=[c.as_dict()["metadata"] for c in batch],
        )
        if verbose:
            print(f"  {min(i + batch_size, len(chunks))}/{len(chunks)}", end="\r")

    community_collection = client.create_collection(
        name=COMMUNITIES_COLLECTION,
        embedding_function=embed_fn,
        metadata={"hnsw:space": "cosine"},
    )
    if community_summaries:
        community_collection.add(
            ids=[f"community_{cid}" for cid in community_summaries],
            documents=[cs["summary"] for cs in community_summaries.values()],
            metadatas=[
                {
                    "community_id": cid,
                    "size": cs["size"],
                    "top_entities": ", ".join(cs["top_entities"]),
                }
                for cid, cs in community_summaries.items()
            ],
        )

    if verbose:
        print(f"\nChunks collection: {chunks_collection.count()} documents")
        print(f"Community collection: {community_collection.count()} summaries")

    return Store(client=client, chunks=chunks_collection, communities=community_collection)


def open_store(
    persist_dir: Path,
    *,
    embed_model: str = "nomic-embed-text",
    ollama_base_url: str = "http://localhost:11434",
) -> Store:
    """Open an existing store at `persist_dir`. Raises if either collection is missing."""
    embed_fn = OllamaEmbeddingFunction(model=embed_model, base_url=ollama_base_url)
    client = chromadb.PersistentClient(path=str(persist_dir.resolve()))
    chunks = client.get_collection(name=CHUNKS_COLLECTION, embedding_function=embed_fn)
    communities = client.get_collection(name=COMMUNITIES_COLLECTION, embedding_function=embed_fn)
    return Store(client=client, chunks=chunks, communities=communities)
