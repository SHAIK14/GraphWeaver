"""
Lexical Graph Builder Service.

This service processes markdown files and creates the lexical graph:
- Splits text into chunks using FixedSizeSplitter
- Creates embeddings for each chunk
- Stores chunks as nodes in Neo4j
- Links chunks with NEXT_CHUNK relationships

The lexical graph enables semantic search over unstructured documents.
"""

from typing import Any, Dict, List
import hashlib
from neo4j_graphrag.experimental.components.text_splitters.fixed_size_splitter import FixedSizeSplitter

from langchain_openai import OpenAIEmbeddings

from app.services.neo4j_client import get_neo4j_client, tool_success, tool_error
from app.core.config import get_settings
import os


async def chunk_text(text: str, chunk_size: int = 500 , chunk_overlap: int = 100) -> List[Dict[str,any]]:
    """
    Split text into chunks using FixedSizeSplitter.

    Args:
        text: The full document text to chunk
        chunk_size: Number of characters per chunk (default 500)
        chunk_overlap: Overlap between chunks for context continuity (default 100)

    Returns:
        List of chunk dictionaries with 'id', 'text', and 'index' keys

    Example:
        chunks = await chunk_text("Long document text here...")
        # Returns: [{"id": "abc123", "text": "Long doc...", "index": 0}, ...]
    """
    splitter = FixedSizeSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    result = await splitter.run(text=text)  # await the async method
    # result is TextChunks object with .chunks attribute containing list of TextChunk
    chunks = []
    for index, chunk in enumerate(result.chunks):
        chunk_content = chunk.text
        chunk_id = hashlib.md5(chunk_content.encode()).hexdigest()[:12]

        chunks.append({
            "id": chunk_id,
            "text": chunk_content,
            "index": index
        })
    return chunks
    
def create_embeddings(chunks: List[Dict[str,any]]) -> List[Dict[str,any]]:
    """
    Generate embeddings for each chunk using OpenAI.
    
    Args:
        chunks: List of chunk dicts from chunk_text()
    
    Returns:
        Same chunks with 'embedding' key added (1536-dim vector)
    
    Example:
        chunks_with_embeddings = create_embeddings(chunks)
        # Each chunk now has: {"id": "...", "text": "...", "index": 0, "embedding": [...]}
    """
    settings = get_settings()
    embedder = OpenAIEmbeddings(api_key=settings.openai_api_key)
    texts = [chunk["text"] for chunk in chunks]
    embeddings = embedder.embed_documents(texts)
    
    for i, chunk in enumerate(chunks):
        chunk["embedding"] = embeddings[i]
        
       
    return chunks

def store_chunks_in_neo4j(chunks: List[Dict[str,Any]], source_file: str) -> Dict[str,Any]:
    """
    Store chunks as nodes in Neo4j and link them with NEXT_CHUNK relationships.
    
    Args:
        chunks: List of chunks with embeddings from create_embeddings()
        source_file: Name of the source file (for tracking origin)
    
    Returns:
        Dict with status and count of chunks stored
    
    What this creates in Neo4j:
        - (:Chunk) nodes with id, text, embedding, index, source properties
        - [:NEXT_CHUNK] relationships preserving reading order
    """
    client = get_neo4j_client()
    #create all chunk nodes
    # We use UNWIND to batch insert
    create_nodes_query = """
    UNWIND $chunks AS chunk
    MERGE (c:Chunk {id: chunk.id})
    SET c.text = chunk.text, 
    c.embedding = chunk.embedding, 
    c.index = chunk.index, 
    c.source = $source_file
    """
    result = client.send_query(create_nodes_query, {"chunks": chunks, "source_file": source_file})
    if result.get("status") == "error":
        return tool_error(f"Failed to create chunk nodes: {result.get('error_message')}")
    
    #create NEXT_CHUNK relationships
    #This links chunk[0] -> chunk[1] -> chunk[2] -> ...
    
    create_realationships_query = """
    MATCH (c1:Chunk)
    WHERE c1.source = $source_file
    MATCH (c2:Chunk)
    WHERE c2.source = $source_file AND c2.index = c1.index + 1
    MERGE (c1)-[:NEXT_CHUNK]->(c2)
    """
    rel_result = client.send_query(create_realationships_query, {"source_file": source_file})
    if rel_result.get("status") == "error":
        
        return tool_error(f"Failed to create relationships: {rel_result.get('error_message')}")
    
    return tool_success("chunks_stored", {
        "message": f"Stored {len(chunks)} chunks from {source_file}",
        "chunk_count": len(chunks),
        "source_file": source_file
    })
    
    
async def build_lexical_graph(file_path: str) -> Dict[str,Any]:
    """
    Main orchestrator: Build lexical graph from a markdown file.

    This is the entry point that chains all steps together:
    1. Read the file content
    2. Chunk the text
    3. Generate embeddings
    4. Store in Neo4j with NEXT_CHUNK relationships

    Args:
        file_path: Path to the markdown file to process

    Returns:
        Dict with status and summary of what was created

    Example:
        result = await build_lexical_graph("/data/reviews/product_review.md")
        # Returns: {"status": "success", "chunks_stored": 15, ...}
    """
    try:
        with open(file_path,"r",encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        return tool_error(f"File not found: {file_path}")
    except Exception as e:
        return tool_error(f"Failed to read file: {str(e)}")

    if not text.strip():
        return tool_error(f"File is empty: {file_path}")

    chunks = await chunk_text(text)  # await the async function
    if not chunks:
        return tool_error(f"No chunks generated from text")

    chunks_with_embeddings = create_embeddings(chunks)

    source_file = os.path.basename(file_path)
    result = store_chunks_in_neo4j(chunks_with_embeddings, source_file)
    return result
    
    

   
  