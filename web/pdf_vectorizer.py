"""
PDF Vectorization Module for Document Storage and Retrieval

This module extracts text from PDF files, chunks them, generates embeddings,
and stores them in PostgreSQL with pgvector for efficient semantic search.
"""

import os
import re
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime

import fitz  # PyMuPDF
import psycopg2
from psycopg2.extras import execute_values
import numpy as np

# OCR support for scanned PDFs
try:
    from pdf2image import convert_from_path
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

# Embedding model
try:
    from sentence_transformers import SentenceTransformer
    EMBEDDING_MODEL = None  # Lazy load
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    EMBEDDING_MODEL = None

# Database configuration
DB_CONFIG = {
    'dbname': 'robo_trader',
    'user': 'utpalraina',
    'host': 'localhost',
    'port': 5432
}

# Chunking configuration
CHUNK_SIZE = 1000  # characters per chunk
CHUNK_OVERLAP = 200  # overlap between chunks
MIN_CHUNK_SIZE = 100  # minimum chunk size to store


def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)


def get_embedding_model():
    """Lazy load the embedding model."""
    global EMBEDDING_MODEL
    if EMBEDDING_MODEL is None and EMBEDDINGS_AVAILABLE:
        print("Loading embedding model (all-MiniLM-L6-v2)...")
        EMBEDDING_MODEL = SentenceTransformer('all-MiniLM-L6-v2')
        print("Model loaded successfully.")
    return EMBEDDING_MODEL


def extract_text_from_pdf(pdf_path: str, use_ocr: bool = False) -> List[Dict]:
    """
    Extract text from PDF file, page by page.

    Args:
        pdf_path: Path to the PDF file
        use_ocr: Force OCR extraction (for scanned PDFs)

    Returns:
        List of dicts with 'page', 'text' keys
    """
    pages = []
    try:
        doc = fitz.open(pdf_path)
        total_pages = len(doc)

        # First try normal text extraction
        if not use_ocr:
            for page_num in range(total_pages):
                page = doc[page_num]
                text = page.get_text()
                text = clean_text(text)
                if text.strip():
                    pages.append({
                        'page': page_num + 1,
                        'text': text
                    })
        doc.close()

        # If no text found and OCR is available, try OCR
        if not pages and OCR_AVAILABLE:
            print("  No text found, using OCR...")
            pages = extract_text_with_ocr(pdf_path)
        elif not pages and not OCR_AVAILABLE:
            print("  No text found and OCR not available")

    except Exception as e:
        print(f"Error extracting PDF: {e}")
        raise

    return pages


def extract_text_with_ocr(pdf_path: str) -> List[Dict]:
    """
    Extract text from scanned PDF using OCR.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        List of dicts with 'page', 'text' keys
    """
    if not OCR_AVAILABLE:
        raise RuntimeError("OCR not available - install pdf2image and pytesseract")

    pages = []
    try:
        # Convert PDF to images (process in batches for large PDFs)
        print("  Converting PDF to images...")
        images = convert_from_path(pdf_path, dpi=150)
        total_pages = len(images)
        print(f"  Processing {total_pages} pages with OCR...")

        for i, image in enumerate(images):
            if (i + 1) % 10 == 0 or i == 0:
                print(f"    OCR page {i + 1}/{total_pages}...")

            # Run OCR on the image
            text = pytesseract.image_to_string(image)
            text = clean_text(text)

            if text.strip():
                pages.append({
                    'page': i + 1,
                    'text': text
                })

    except Exception as e:
        print(f"OCR error: {e}")
        raise

    return pages


def clean_text(text: str) -> str:
    """Clean and normalize extracted text."""
    # Replace multiple whitespace with single space
    text = re.sub(r'\s+', ' ', text)
    # Remove control characters except newlines
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
    # Normalize quotes
    text = text.replace('"', '"').replace('"', '"')
    text = text.replace(''', "'").replace(''', "'")
    return text.strip()


def chunk_text(pages: List[Dict], chunk_size: int = CHUNK_SIZE,
               overlap: int = CHUNK_OVERLAP) -> List[Dict]:
    """
    Split extracted pages into overlapping chunks.

    Args:
        pages: List of page dicts from extract_text_from_pdf
        chunk_size: Target size of each chunk in characters
        overlap: Overlap between consecutive chunks

    Returns:
        List of chunk dicts with 'chunk_index', 'page_number', 'content'
    """
    chunks = []
    chunk_index = 0

    for page_data in pages:
        page_num = page_data['page']
        text = page_data['text']

        if len(text) < MIN_CHUNK_SIZE:
            continue

        # Split long pages into chunks
        start = 0
        while start < len(text):
            end = start + chunk_size

            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence end within last 100 chars of chunk
                for sep in ['. ', '.\n', '? ', '?\n', '! ', '!\n']:
                    last_sep = text[max(0, end-100):end].rfind(sep)
                    if last_sep != -1:
                        end = max(0, end-100) + last_sep + len(sep)
                        break

            chunk_text = text[start:end].strip()

            if len(chunk_text) >= MIN_CHUNK_SIZE:
                chunks.append({
                    'chunk_index': chunk_index,
                    'page_number': page_num,
                    'content': chunk_text,
                    'content_length': len(chunk_text)
                })
                chunk_index += 1

            # Move start position with overlap
            start = end - overlap if end < len(text) else len(text)

    return chunks


def generate_embeddings(texts: List[str], batch_size: int = 32) -> np.ndarray:
    """
    Generate embeddings for a list of texts.

    Args:
        texts: List of text strings
        batch_size: Batch size for encoding

    Returns:
        numpy array of embeddings
    """
    model = get_embedding_model()
    if model is None:
        raise RuntimeError("Embedding model not available")

    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=True,
        convert_to_numpy=True
    )

    return embeddings


def store_document(pdf_path: str, chunks: List[Dict], embeddings: np.ndarray) -> int:
    """
    Store document and its chunks in the database.

    Args:
        pdf_path: Path to the PDF file
        chunks: List of chunk dicts
        embeddings: numpy array of embeddings

    Returns:
        document_id of the stored document
    """
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Get file info
        path = Path(pdf_path)
        file_size = path.stat().st_size

        # Extract title from filename
        title = path.stem.replace('-', ' ').replace('_', ' ')

        # Count pages
        doc = fitz.open(pdf_path)
        page_count = len(doc)
        doc.close()

        # Check if document already exists
        cur.execute(
            "SELECT id FROM pdf_documents WHERE filename = %s",
            (path.name,)
        )
        existing = cur.fetchone()

        if existing:
            document_id = existing[0]
            # Delete old chunks
            cur.execute(
                "DELETE FROM document_chunks WHERE document_id = %s",
                (document_id,)
            )
            # Update document record
            cur.execute("""
                UPDATE pdf_documents
                SET file_path = %s, file_size = %s, page_count = %s,
                    processed_at = %s, title = %s
                WHERE id = %s
            """, (str(path.absolute()), file_size, page_count,
                  datetime.now(), title, document_id))
        else:
            # Insert new document
            cur.execute("""
                INSERT INTO pdf_documents (filename, title, file_path, file_size, page_count)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (path.name, title, str(path.absolute()), file_size, page_count))
            document_id = cur.fetchone()[0]

        # Insert chunks with embeddings
        chunk_data = []
        for i, chunk in enumerate(chunks):
            embedding = embeddings[i].tolist()
            chunk_data.append((
                document_id,
                chunk['chunk_index'],
                chunk['page_number'],
                chunk['content'],
                chunk['content_length'],
                embedding
            ))

        execute_values(
            cur,
            """
            INSERT INTO document_chunks
            (document_id, chunk_index, page_number, content, content_length, embedding)
            VALUES %s
            """,
            chunk_data,
            template="(%s, %s, %s, %s, %s, %s::vector)"
        )

        conn.commit()
        print(f"Stored {len(chunks)} chunks for document: {path.name}")
        return document_id

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()


def process_pdf(pdf_path: str) -> Dict:
    """
    Full pipeline: extract, chunk, embed, and store a PDF.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Dict with processing results
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    print(f"\n{'='*60}")
    print(f"Processing: {path.name}")
    print(f"{'='*60}")

    # Extract text
    print("Extracting text from PDF...")
    pages = extract_text_from_pdf(pdf_path)
    print(f"  Extracted {len(pages)} pages")

    # Chunk text
    print("Chunking text...")
    chunks = chunk_text(pages)
    print(f"  Created {len(chunks)} chunks")

    if not chunks:
        return {
            'filename': path.name,
            'status': 'skipped',
            'reason': 'No text content extracted'
        }

    # Generate embeddings
    print("Generating embeddings...")
    texts = [c['content'] for c in chunks]
    embeddings = generate_embeddings(texts)
    print(f"  Generated {len(embeddings)} embeddings")

    # Store in database
    print("Storing in database...")
    document_id = store_document(pdf_path, chunks, embeddings)

    return {
        'filename': path.name,
        'status': 'success',
        'document_id': document_id,
        'pages': len(pages),
        'chunks': len(chunks)
    }


def process_all_pdfs(directory: str = None) -> List[Dict]:
    """
    Process all PDF files in a directory.

    Args:
        directory: Directory path (defaults to project root)

    Returns:
        List of processing results
    """
    if directory is None:
        directory = Path(__file__).parent.parent

    pdf_files = list(Path(directory).glob("*.pdf"))
    print(f"Found {len(pdf_files)} PDF files to process")

    results = []
    for pdf_path in pdf_files:
        try:
            result = process_pdf(str(pdf_path))
            results.append(result)
        except Exception as e:
            results.append({
                'filename': pdf_path.name,
                'status': 'error',
                'error': str(e)
            })
            print(f"Error processing {pdf_path.name}: {e}")

    return results


def search_documents(query: str, limit: int = 10,
                    document_id: Optional[int] = None) -> List[Dict]:
    """
    Search for relevant document chunks using semantic similarity.

    Args:
        query: Search query text
        limit: Maximum number of results
        document_id: Optional - limit search to specific document

    Returns:
        List of matching chunks with similarity scores
    """
    # Generate query embedding
    model = get_embedding_model()
    query_embedding = model.encode([query])[0].tolist()

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        if document_id:
            cur.execute("""
                SELECT
                    dc.id,
                    dc.document_id,
                    pd.filename,
                    pd.title,
                    dc.chunk_index,
                    dc.page_number,
                    dc.content,
                    1 - (dc.embedding <=> %s::vector) as similarity
                FROM document_chunks dc
                JOIN pdf_documents pd ON dc.document_id = pd.id
                WHERE dc.document_id = %s
                ORDER BY dc.embedding <=> %s::vector
                LIMIT %s
            """, (query_embedding, document_id, query_embedding, limit))
        else:
            cur.execute("""
                SELECT
                    dc.id,
                    dc.document_id,
                    pd.filename,
                    pd.title,
                    dc.chunk_index,
                    dc.page_number,
                    dc.content,
                    1 - (dc.embedding <=> %s::vector) as similarity
                FROM document_chunks dc
                JOIN pdf_documents pd ON dc.document_id = pd.id
                ORDER BY dc.embedding <=> %s::vector
                LIMIT %s
            """, (query_embedding, query_embedding, limit))

        results = []
        for row in cur.fetchall():
            results.append({
                'chunk_id': row[0],
                'document_id': row[1],
                'filename': row[2],
                'title': row[3],
                'chunk_index': row[4],
                'page_number': row[5],
                'content': row[6],
                'similarity': float(row[7])
            })

        return results

    finally:
        cur.close()
        conn.close()


def search_by_keyword(keyword: str, limit: int = 20,
                     document_id: Optional[int] = None) -> List[Dict]:
    """
    Search for document chunks using full-text search.

    Args:
        keyword: Keyword to search for
        limit: Maximum number of results
        document_id: Optional - limit search to specific document

    Returns:
        List of matching chunks
    """
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        if document_id:
            cur.execute("""
                SELECT
                    dc.id,
                    dc.document_id,
                    pd.filename,
                    pd.title,
                    dc.chunk_index,
                    dc.page_number,
                    dc.content,
                    ts_rank(to_tsvector('english', dc.content),
                            plainto_tsquery('english', %s)) as rank
                FROM document_chunks dc
                JOIN pdf_documents pd ON dc.document_id = pd.id
                WHERE dc.document_id = %s
                  AND to_tsvector('english', dc.content) @@ plainto_tsquery('english', %s)
                ORDER BY rank DESC
                LIMIT %s
            """, (keyword, document_id, keyword, limit))
        else:
            cur.execute("""
                SELECT
                    dc.id,
                    dc.document_id,
                    pd.filename,
                    pd.title,
                    dc.chunk_index,
                    dc.page_number,
                    dc.content,
                    ts_rank(to_tsvector('english', dc.content),
                            plainto_tsquery('english', %s)) as rank
                FROM document_chunks dc
                JOIN pdf_documents pd ON dc.document_id = pd.id
                WHERE to_tsvector('english', dc.content) @@ plainto_tsquery('english', %s)
                ORDER BY rank DESC
                LIMIT %s
            """, (keyword, keyword, limit))

        results = []
        for row in cur.fetchall():
            results.append({
                'chunk_id': row[0],
                'document_id': row[1],
                'filename': row[2],
                'title': row[3],
                'chunk_index': row[4],
                'page_number': row[5],
                'content': row[6],
                'rank': float(row[7])
            })

        return results

    finally:
        cur.close()
        conn.close()


def get_document_chunks(document_id: int, start_chunk: int = 0,
                       num_chunks: int = 10) -> List[Dict]:
    """
    Get sequential chunks from a document.

    Args:
        document_id: Document ID
        start_chunk: Starting chunk index
        num_chunks: Number of chunks to retrieve

    Returns:
        List of chunks in order
    """
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT
                dc.id,
                dc.chunk_index,
                dc.page_number,
                dc.content,
                dc.content_length
            FROM document_chunks dc
            WHERE dc.document_id = %s
              AND dc.chunk_index >= %s
            ORDER BY dc.chunk_index
            LIMIT %s
        """, (document_id, start_chunk, num_chunks))

        results = []
        for row in cur.fetchall():
            results.append({
                'chunk_id': row[0],
                'chunk_index': row[1],
                'page_number': row[2],
                'content': row[3],
                'content_length': row[4]
            })

        return results

    finally:
        cur.close()
        conn.close()


def list_documents() -> List[Dict]:
    """
    List all processed documents.

    Returns:
        List of document info dicts
    """
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT
                pd.id,
                pd.filename,
                pd.title,
                pd.page_count,
                pd.file_size,
                pd.processed_at,
                COUNT(dc.id) as chunk_count
            FROM pdf_documents pd
            LEFT JOIN document_chunks dc ON pd.id = dc.document_id
            GROUP BY pd.id
            ORDER BY pd.processed_at DESC
        """)

        results = []
        for row in cur.fetchall():
            results.append({
                'id': row[0],
                'filename': row[1],
                'title': row[2],
                'page_count': row[3],
                'file_size': row[4],
                'processed_at': row[5].isoformat() if row[5] else None,
                'chunk_count': row[6]
            })

        return results

    finally:
        cur.close()
        conn.close()


def get_context_for_query(query: str, num_chunks: int = 5,
                         document_id: Optional[int] = None) -> str:
    """
    Get relevant context from documents for a query.
    Useful for RAG (Retrieval Augmented Generation).

    Args:
        query: The question or topic
        num_chunks: Number of chunks to retrieve
        document_id: Optional - limit to specific document

    Returns:
        Combined text from relevant chunks
    """
    results = search_documents(query, limit=num_chunks, document_id=document_id)

    if not results:
        return ""

    context_parts = []
    for r in results:
        source = f"[{r['title']}, Page {r['page_number']}]"
        context_parts.append(f"{source}\n{r['content']}")

    return "\n\n---\n\n".join(context_parts)


# CLI interface
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python pdf_vectorizer.py process [path]  - Process PDF(s)")
        print("  python pdf_vectorizer.py list            - List documents")
        print("  python pdf_vectorizer.py search <query>  - Search documents")
        print("  python pdf_vectorizer.py read <doc_id> [start] [count] - Read chunks")
        sys.exit(1)

    command = sys.argv[1]

    if command == "process":
        if len(sys.argv) > 2:
            # Process specific file
            result = process_pdf(sys.argv[2])
            print(f"\nResult: {json.dumps(result, indent=2)}")
        else:
            # Process all PDFs in project root
            results = process_all_pdfs()
            print("\n" + "="*60)
            print("PROCESSING COMPLETE")
            print("="*60)
            for r in results:
                status = r['status']
                name = r['filename']
                if status == 'success':
                    print(f"✓ {name}: {r['chunks']} chunks")
                else:
                    print(f"✗ {name}: {status} - {r.get('error', r.get('reason', ''))}")

    elif command == "list":
        docs = list_documents()
        print("\nProcessed Documents:")
        print("-" * 80)
        for doc in docs:
            print(f"ID: {doc['id']}")
            print(f"  Title: {doc['title']}")
            print(f"  File: {doc['filename']}")
            print(f"  Pages: {doc['page_count']}, Chunks: {doc['chunk_count']}")
            print(f"  Size: {doc['file_size'] / 1024 / 1024:.1f} MB")
            print()

    elif command == "search":
        if len(sys.argv) < 3:
            print("Usage: python pdf_vectorizer.py search <query>")
            sys.exit(1)
        query = " ".join(sys.argv[2:])
        results = search_documents(query, limit=5)
        print(f"\nSearch results for: '{query}'")
        print("-" * 80)
        for r in results:
            print(f"\n[{r['title']}, Page {r['page_number']}] (similarity: {r['similarity']:.3f})")
            print(f"{r['content'][:300]}...")

    elif command == "read":
        if len(sys.argv) < 3:
            print("Usage: python pdf_vectorizer.py read <doc_id> [start] [count]")
            sys.exit(1)
        doc_id = int(sys.argv[2])
        start = int(sys.argv[3]) if len(sys.argv) > 3 else 0
        count = int(sys.argv[4]) if len(sys.argv) > 4 else 5

        chunks = get_document_chunks(doc_id, start, count)
        print(f"\nChunks {start} to {start + len(chunks) - 1}:")
        print("-" * 80)
        for c in chunks:
            print(f"\n[Chunk {c['chunk_index']}, Page {c['page_number']}]")
            print(c['content'])
            print()

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
