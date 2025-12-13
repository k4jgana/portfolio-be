from langchain.tools import tool
from utils.constants import vector_store
import pandas as pd
import tqdm

@tool
def retrieve_context(query: str) -> str:
    """
    Retrieve information about Nenad Kajgana from the knowledge base.

    Args:
        query: The search query

    Returns:
        Retrieved context as a formatted string
    """
    retrieved_docs = vector_store.similarity_search(query, k=10)

    serialized = "\n\n".join(
        f"Source: {doc.metadata.get('source', 'Unknown')}\nContent: {doc.page_content}"
        for doc in retrieved_docs
    )

    return serialized if serialized else "No relevant information found."




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