"""
ingest.py
One-time script to index /patterns/ folder into Cosmos DB.
Run once before launching the app, and again whenever you add new pattern files.
Usage: python ingest.py
"""

import os
from dotenv import load_dotenv
load_dotenv()

from langchain_community.document_loaders import DirectoryLoader, UnstructuredMarkdownLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from cosmos_store import ensure_container_exists, upsert_many

PATTERNS_DIR = "./patterns"


def load_and_chunk_patterns() -> list[dict]:
    loader = DirectoryLoader(
        PATTERNS_DIR,
        glob="**/*.md",
        loader_cls=UnstructuredMarkdownLoader
    )
    raw_docs = loader.load()
    print(f"Loaded {len(raw_docs)} pattern files")

    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
    chunks   = splitter.split_documents(raw_docs)

    # Convert to plain dicts for cosmos_store.upsert_many
    return [
        {
            "text":         chunk.page_content,
            "source_file":  chunk.metadata.get("source", "unknown"),
            "pattern_type": _infer_pattern_type(chunk.metadata.get("source", "")),
        }
        for chunk in chunks
    ]


def _infer_pattern_type(source_file: str) -> str:
    """Infer partition key value from filename."""
    s = source_file.lower()
    if "realtime" in s or "eventhub" in s:
        return "realtime"
    elif "batch" in s or "servicebus" in s:
        return "batch"
    elif "masterdata" in s or "pubsub" in s:
        return "masterdata"
    return "general"


if __name__ == "__main__":
    print("Step 1 — Ensuring Cosmos DB container exists...")
    ensure_container_exists()

    print("Step 2 — Loading and chunking pattern files...")
    chunks = load_and_chunk_patterns()
    print(f"  {len(chunks)} chunks ready to index")

    print("Step 3 — Uploading to Cosmos DB...")
    upsert_many(chunks)

    print("\nDone. Run: streamlit run app.py")