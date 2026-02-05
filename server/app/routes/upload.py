import uuid
import logging
import io
from datetime import datetime
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Header
import PyPDF2

from app.core.auth import get_current_user
from app.models.user import User
from app.core.state import FileData
from app.services.state_store import state_store
from app.services.supabase_client import supabase_client
from app.services.file_parser import parse_csv, parse_json, parse_pdf, parse_xlsx, chunk_text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["upload"])

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    session_id: str = Header(..., alias="x-session-id"),
    user: User = Depends(get_current_user),
):
    """Upload file → Supabase Storage → Parse → Add to session"""
    
   
    ALLOWED = {
        "text/csv": "csv",
        "application/json": "json",
        "application/pdf": "pdf",
        "text/plain": "txt",
        "text/markdown": "md",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    }

    if file.content_type not in ALLOWED:
        raise HTTPException(400, f"Unsupported: {file.content_type}. Allowed: CSV, JSON, PDF, TXT, MD, XLSX")
    
    file_type = ALLOWED[file.content_type]
    
   
    content = await file.read()
    file_size = len(content)
    
    if file_size > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(400, "File too large (max 10MB)")
    

    storage_path = f"{user.id}/{session_id}/{file.filename}"

    try:
        # Try to remove existing file first (if reuploading same filename)
        try:
            supabase_client.client.storage.from_("user-files").remove([storage_path])
        except:
            pass  # File doesn't exist, that's fine

        # Upload new file
        supabase_client.client.storage.from_("user-files").upload(
            path=storage_path,
            file=content,
            file_options={"content-type": file.content_type}
        )
        storage_url = supabase_client.client.storage.from_("user-files").get_public_url(storage_path)
    except Exception as e:
        raise HTTPException(500, f"Storage upload failed: {e}")
    

    # Decode content for parsing
    if file_type == "csv":
        decoded_content = content.decode('utf-8')
        result = parse_csv(decoded_content)
        text_chunks = None  # CSVs don't get chunked
    elif file_type == "json":
        decoded_content = content.decode('utf-8')
        result = parse_json(decoded_content)
        text_chunks = None  # JSONs don't get chunked
    elif file_type in ["txt", "md"]:
        # Text/Markdown files - treat as unstructured text
        decoded_content = content.decode('utf-8')
        result = {
            'parsed': True,
            'parse_error': None,
            'row_count': None,  # Unstructured
            'columns': None,    # Unstructured
            'preview': decoded_content[:500] + "..." if len(decoded_content) > 500 else decoded_content
        }
        # Chunk the text for GraphRAG
        text_chunks = chunk_text(decoded_content, chunk_size=500, overlap=50)
        logger.info(f"[UPLOAD] {file_type.upper()} chunked into {len(text_chunks)} chunks")
    elif file_type == "xlsx":
        result = parse_xlsx(content)
        decoded_content = result.get('csv_text', '')  # Store as CSV text — graph builder reads CSV format
        text_chunks = None  # Tabular, like CSV
    else:  # PDF
        result = parse_pdf(content)
        decoded_content = ""
        # Extract full text from parse_pdf result (it's in preview for now)
        # TODO: parse_pdf should return full text separately
        reader = PyPDF2.PdfReader(io.BytesIO(content))
        for page in reader.pages:
            decoded_content += page.extract_text() + "\n"

        # Chunk the PDF text for GraphRAG
        text_chunks = chunk_text(decoded_content, chunk_size=500, overlap=50)
        logger.info(f"[UPLOAD] PDF chunked into {len(text_chunks)} chunks")


    file_data = FileData(
        name=file.filename,
        type=file_type,
        source="upload",
        content=decoded_content,  # ✓ Store actual file content, not URL
        storage_url=storage_url,  # ✓ Store Supabase URL separately
        size=file_size,
        parsed=result['parsed'],
        parse_error=result.get('parse_error'),
        raw_count=result.get('row_count'),
        columns=result.get('columns'),
        preview=result.get('preview'),
        chunks=text_chunks,  # ✓ Store chunks for PDFs
    )
    

    logger.info(f"[UPLOAD] File: {file.filename}, Type: {file_type}, Size: {file_size} bytes")
    logger.info(f"[UPLOAD] Parsed: {result['parsed']}, Rows: {result.get('row_count')}, Columns: {result.get('columns')}")
    logger.info(f"[UPLOAD] Storage URL: {storage_url}")
    logger.info(f"[UPLOAD] Content length: {len(decoded_content)} chars, Preview: {decoded_content[:100] if decoded_content else 'EMPTY'}...")

    # Load or create session (files can be uploaded before first message)
    session = await state_store.load(session_id)
    if not session:
        # Create new session in BUILD mode (uploading files = building graph)
        session = await state_store.create(session_id, user.id, "build")

    session.files.append(file_data)
    await state_store.save(session)

    logger.info(f"[UPLOAD] ✓ File added to session {session_id}. Total files: {len(session.files)}")

    return {
        "file_id": file_data.id,
        "name": file_data.name,
        "type": file_type,
        "parsed": file_data.parsed,
        "preview": file_data.preview,
    }


@router.delete("/upload/{file_name}")
async def remove_file(
    file_name: str,
    session_id: str = Header(..., alias="x-session-id"),
    user: User = Depends(get_current_user),
):
    """Remove a file from the session by name."""
    session = await state_store.load(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    before = len(session.files)
    session.files = [f for f in session.files if f.name != file_name]

    if len(session.files) == before:
        raise HTTPException(404, f"File '{file_name}' not found in session")

    await state_store.save(session)
    logger.info(f"[UPLOAD] ✓ Removed '{file_name}' from session {session_id}. Remaining: {len(session.files)}")

    return {"status": "ok", "removed": file_name, "remaining": len(session.files)}
