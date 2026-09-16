import logging
from typing import Annotated, Any

import pandas as pd
import tqdm
from langchain.tools import tool
from pydantic import Field

from utils.constants import vector_store

logger = logging.getLogger(__name__)


@tool
def search_nenad_knowledge(
    query: Annotated[str, Field(min_length=1, max_length=2000)],
) -> dict[str, Any]:
    """Search verified information about Nenad's background, work, and interests.

    Use this before making a factual claim about Nenad. The result contains raw
    matching passages and metadata; treat an empty result as unknown information.
    """
    logger.info("Searching Nenad knowledge for query=%r", query)
    try:
        retrieved_docs = vector_store.similarity_search(query, k=10)
    except Exception:
        logger.exception("Knowledge retrieval failed")
        return {
            "status": "error",
            "source": "nenad_knowledge",
            "items": [],
            "message": "Nenad's background information is temporarily unavailable.",
        }

    items = [
        {
            "content": doc.page_content,
            "metadata": _json_safe_metadata(doc.metadata),
        }
        for doc in retrieved_docs
    ]
    return {
        "status": "success" if items else "empty",
        "source": "nenad_knowledge",
        "items": items,
    }


def _json_safe_metadata(metadata: dict) -> dict[str, Any]:
    """Keep metadata useful and serializable for a tool response."""
    safe: dict[str, Any] = {}
    for key, value in metadata.items():
        if value is None or isinstance(value, (str, int, float, bool)):
            safe[str(key)] = value
        elif isinstance(value, (list, tuple)):
            safe[str(key)] = [str(item) for item in value]
        else:
            safe[str(key)] = str(value)
    return safe

def upsert(csv_path: str = "data.csv"):
    """
    Embeds rows from a CSV and upserts them into Pinecone via LangChain's PineconeVectorStore.

    Args:
        csv_path: Path to the CSV file with columns 'title' and 'text'.
    """
    df = pd.read_csv(csv_path)

    print(f"📄 Loaded {len(df)} rows from {csv_path}")

    for i, row in tqdm(df.iterrows(), total=len(df), desc="Embedding & upserting"):
        combined_text = f"{row['title']} {row['text']}"
        metadata = {"title": row["title"], "text": row["text"]}
        vector_store.add_texts([combined_text], metadatas=[metadata])

    print("✅ Data successfully embedded and upserted into Pinecone!")
