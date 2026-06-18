"""
cosmos_store.py
Centralised Cosmos DB NoSQL vector store operations.
Replaces FAISS entirely. All 4 files (ingest, knowledge_loader,
chain, doc_chain) call this instead of FAISS directly.

Responsibilities:
  1. connect()        → get Cosmos DB client
  2. upsert()         → store a document + its vector embedding
  3. search()         → find top-k similar documents by vector
  4. delete()         → remove a document by id
"""

import os
import uuid
import json
from dotenv import load_dotenv
load_dotenv()
from azure.cosmos import CosmosClient, PartitionKey, exceptions
from openai import AzureOpenAI

# ── Config — all from environment variables ────────────────────────────────
VECTOR_DIMENSIONS   = 1536
TOP_K_DEFAULT       = 3

# ══════════════════════════════════════════════════════════════════════════
# 1. CONNECTION
# ══════════════════════════════════════════════════════════════════════════

def get_client() -> CosmosClient:
    """Return authenticated Cosmos DB client — reads env at call time."""
    return CosmosClient(
        url=os.environ["COSMOS_ENDPOINT"],
        credential=os.environ["COSMOS_KEY"]
    )


def get_container():
    """Return the Cosmos DB container client."""
    client    = get_client()
    database  = client.get_database_client(os.environ.get("COSMOS_DATABASE", "integration-advisor"))
    container = database.get_container_client(os.environ.get("COSMOS_CONTAINER", "cis-patterns"))
    return container


def ensure_container_exists():
    """
    Create database and container if they don't exist.
    Sets up vector embedding policy for cosine similarity search.
    Run once during setup / ingest.
    """
    client = get_client()

    # Create database if not exists
    database = client.create_database_if_not_exists(
        id=os.environ.get("COSMOS_DATABASE", "integration-advisor")
    )

    # Vector embedding policy — tells Cosmos how to index the embedding field
    vector_embedding_policy = {
        "vectorEmbeddings": [
            {
                "path":       "/embedding",         # field name in our documents
                "dataType":   "float32",
                "dimensions": VECTOR_DIMENSIONS,    # 1536 for ada-002
                "distanceFunction": "cosine"        # cosine similarity
            }
        ]
    }

    # Indexing policy — enables efficient vector search using DiskANN
    indexing_policy = {
        "indexingMode": "consistent",
        "includedPaths": [{"path": "/*"}],
        "excludedPaths": [{"path": "/embedding/*"}],  # exclude raw vector from standard index
        "vectorIndexes": [
            {
                "path": "/embedding",
                "type": "diskANN"           # best algorithm for high-dimensional vector search
            }
        ]
    }

    container_name = os.environ.get("COSMOS_CONTAINER", "cis-patterns")
    database.create_container_if_not_exists(
        id=container_name,
        partition_key=PartitionKey(path="/pattern_type"),
        indexing_policy=indexing_policy,
        vector_embedding_policy=vector_embedding_policy,
    )
    print(f"Container '{container_name}' ready.")


# ══════════════════════════════════════════════════════════════════════════
# 2. EMBEDDING — convert text → vector
# ══════════════════════════════════════════════════════════════════════════

def embed_text(text: str) -> list[float]:
    """Convert text to vector using Foundry endpoint."""
    from openai import OpenAI
    client = OpenAI(
        base_url=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
    )
    response = client.embeddings.create(
        input=text,
        model=os.environ.get("AZURE_EMBED_DEPLOYMENT", "text-embedding-ada-002-1"),
    )
    return response.data[0].embedding


# ══════════════════════════════════════════════════════════════════════════
# 3. UPSERT — store a document with its vector
# ══════════════════════════════════════════════════════════════════════════

def upsert_document(
    text: str,
    source_file: str,
    pattern_type: str = "general",
    extra_metadata: dict = None,
):
    container = get_container()

    # Step 1 — embed
    try:
        embedding = embed_text(text)
    except Exception as e:
        raise RuntimeError(f"embed_text() FAILED: {e}") from e

    # Step 2 — upsert
    try:
        document = {
            "id":           str(uuid.uuid4()),
            "pattern_type": pattern_type,
            "source_file":  source_file,
            "text":         text,
            "embedding":    embedding,
            "metadata":     extra_metadata or {},
        }
        container.upsert_item(document)
    except Exception as e:
        raise RuntimeError(f"upsert_item() FAILED: {e}") from e

    return document["id"]


def upsert_many(chunks: list[dict]):
    """
    Batch upsert multiple chunks.
    Each chunk dict must have: text, source_file, pattern_type (optional).
    Returns count of documents upserted.
    """
    count = 0
    for chunk in chunks:
        upsert_document(
            text=chunk["text"],
            source_file=chunk.get("source_file", "unknown"),
            pattern_type=chunk.get("pattern_type", "general"),
            extra_metadata=chunk.get("metadata", {}),
        )
        count += 1
    print(f"Upserted {count} documents to Cosmos DB.")
    return count


# ══════════════════════════════════════════════════════════════════════════
# 4. SEARCH — find top-k similar documents by vector
# ══════════════════════════════════════════════════════════════════════════

def search(query: str, k: int = TOP_K_DEFAULT) -> list[dict]:
    """
    Find the top-k most semantically similar CIS pattern chunks for a query.

    Steps:
    1. Embed the query text → query vector
    2. Run VectorDistance search in Cosmos DB
    3. Return list of {text, source_file, score} dicts

    This replaces FAISS.similarity_search() entirely.
    """
    container     = get_container()
    query_vector  = embed_text(query)

    # Cosmos DB vector search query using VectorDistance function
    # Lower score = more similar (cosine distance)
    cosmos_query = """
        SELECT TOP @k
            c.text,
            c.source_file,
            c.pattern_type,
            c.metadata,
            VectorDistance(c.embedding, @queryVector) AS score
        FROM c
        ORDER BY VectorDistance(c.embedding, @queryVector)
    """

    parameters = [
        {"name": "@k",           "value": k},
        {"name": "@queryVector", "value": query_vector},
    ]

    results = list(container.query_items(
        query=cosmos_query,
        parameters=parameters,
        enable_cross_partition_query=True,
    ))

    # Format to match what chain.py and doc_chain.py expect
    return [
        {
            "text":         r["text"],
            "source_file":  r.get("source_file", "CIS pattern"),
            "pattern_type": r.get("pattern_type", "general"),
            "score":        r.get("score", 0.0),
        }
        for r in results
    ]


def format_context(search_results: list[dict]) -> str:
    """
    Format search results into a context string for the system prompt.
    Replaces the FAISS join logic in chain.py and doc_chain.py.
    """
    return "\n\n---\n\n".join(
        f"[Source: {r['source_file']}]\n{r['text']}"
        for r in search_results
    )


# ══════════════════════════════════════════════════════════════════════════
# 5. DELETE — remove documents by source file
# ══════════════════════════════════════════════════════════════════════════

def delete_by_source(source_file: str):
    """
    Remove all chunks from a specific source file.
    Useful when a CIS pattern document is updated and needs re-indexing.
    """
    container = get_container()

    query = "SELECT c.id, c.pattern_type FROM c WHERE c.source_file = @source"
    params = [{"name": "@source", "value": source_file}]
    items = list(container.query_items(
        query=query,
        parameters=params,
        enable_cross_partition_query=True,
    ))

    for item in items:
        container.delete_item(item=item["id"], partition_key=item["pattern_type"])

    print(f"Deleted {len(items)} chunks for source: {source_file}")
    return len(items)