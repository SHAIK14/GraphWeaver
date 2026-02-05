import io
import csv
import json
from typing import Dict, Any, Optional, List
import PyPDF2

from app.core.state import FileData


def parse_csv(content: str) -> Dict[str, Any]:

    try:
        reader = csv.DictReader(io.StringIO(content))
        columns = reader.fieldnames

        if not columns:
            return ValueError("No columns found in CSV file")

        rows = list(reader)
        row_count = len(rows)

        preview_rows = rows[:5]
        preview = "Columns:  " + " , ".join(columns) + "\n\n"
        for row in preview_rows:
            preview += " | ".join(str(row.get(col, '')) for col in columns) + "\n"
        return {
            'parsed': True,
            'parse_error': None,
            'row_count': row_count,
            'columns': list(columns),
            'preview': preview.strip()
        }
    except Exception as e:
        return {
            'parsed': False,
            'parse_error': str(e),
            'row_count': None,
            'columns': None,
            'preview': None
        }


def parse_json(content: str) -> Dict[str, Any]:
    """Parse JSON and extract structure."""
    try:
        data = json.loads(content)

        if isinstance(data, list):
            # Array of objects
            if len(data) > 0 and isinstance(data[0], dict):
                columns = list(data[0].keys())
                row_count = len(data)
                preview = json.dumps(data[:3], indent=2)
            else:
                # Array of primitives [1, 2, 3]
                columns = None
                row_count = len(data)
                preview = json.dumps(data[:5], indent=2)

        elif isinstance(data, dict):
            # Single object
            columns = list(data.keys())
            row_count = 1
            preview = json.dumps(data, indent=2)

        else:
            # Primitive value
            columns = None
            row_count = None
            preview = str(data)

        return {
            'parsed': True,
            'parse_error': None,
            'row_count': row_count,
            'columns': columns,
            'preview': preview
        }
    except Exception as e:
        return {
            'parsed': False,
            'parse_error': str(e),
            'row_count': None,
            'columns': None,
            'preview': None
        }


def parse_pdf(file_bytes: bytes) -> Dict[str, Any]:
    """Extract text from PDF."""
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))

        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"

        if not text.strip():
            raise ValueError("PDF contains no text")

        # Preview: first 500 characters
        preview = text[:500].strip()
        if len(text) > 500:
            preview += "..."

        return {
            'parsed': True,
            'parse_error': None,
            'row_count': None,    # Unstructured
            'columns': None,      # Unstructured
            'preview': preview
        }
    except Exception as e:
        return {
            'parsed': False,
            'parse_error': str(e),
            'row_count': None,
            'columns': None,
            'preview': None
        }


def parse_xlsx(file_bytes: bytes) -> Dict[str, Any]:
    """Parse Excel (.xlsx) file, extract structure, and produce CSV text for graph builder."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
        ws = wb.active

        rows = list(ws.rows)
        if len(rows) < 1:
            raise ValueError("Excel file is empty")

        # First row = headers
        columns = [str(cell.value) if cell.value is not None else f"col_{i}" for i, cell in enumerate(rows[0])]

        # Convert all data rows to string lists
        data_rows = []
        for row in rows[1:]:
            data_rows.append([str(cell.value) if cell.value is not None else "" for cell in row])

        wb.close()

        # Build proper CSV text using csv module (handles commas/quotes in values)
        csv_output = io.StringIO()
        writer = csv.writer(csv_output)
        writer.writerow(columns)
        writer.writerows(data_rows)
        csv_text = csv_output.getvalue()

        # Preview: first 5 data rows
        preview = "Columns:  " + " , ".join(columns) + "\n\n"
        for row in data_rows[:5]:
            preview += " | ".join(row) + "\n"

        return {
            'parsed': True,
            'parse_error': None,
            'row_count': len(data_rows),
            'columns': columns,
            'preview': preview.strip(),
            'csv_text': csv_text,
        }
    except Exception as e:
        return {
            'parsed': False,
            'parse_error': str(e),
            'row_count': None,
            'columns': None,
            'preview': None,
            'csv_text': "",
        }


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """
    Split text into overlapping chunks for embedding.

    Args:
        text: Full text to chunk
        chunk_size: Target size per chunk (characters)
        overlap: Overlap between chunks (characters)

    Returns:
        List of text chunks

    Why overlap? Ensures context isn't lost at chunk boundaries.
    Example: "...end of sentence. Start of next..." won't get split awkwardly.
    """
    if not text or len(text) == 0:
        return []

    chunks = []
    start = 0

    while start < len(text):
        # Extract chunk
        end = start + chunk_size
        chunk = text[start:end]

        # Clean up chunk
        chunk = chunk.strip()
        if chunk:
            chunks.append(chunk)

        # Move start position (with overlap)
        start = end - overlap

    return chunks


def detect_data_in_message(message: str) -> Optional[FileData]:
    """
    Detect if message contains CSV or JSON data pasted by user.
    Returns FileData if detected, None otherwise.
    """
    # CSV detection: multiple lines with commas
    if '\n' in message and ',' in message:
        lines = message.strip().split('\n')
        if len(lines) >= 2:  # At least header + 1 data row
            result = parse_csv(message)
            if result['parsed']:
                return FileData(
                    name="pasted_data.csv",
                    type="csv",
                    source="paste",
                    content=message,  # Raw text, not URL
                    size=len(message),
                    parsed=True,
                    parse_error=None,
                    raw_count=result['row_count'],
                    columns=result['columns'],
                    preview=result['preview']
                )

    # JSON detection: starts with { or [
    if message.strip().startswith(('{', '[')):
        try:
            result = parse_json(message)
            if result['parsed']:
                return FileData(
                    name="pasted_data.json",
                    type="json",
                    source="paste",
                    content=message,
                    size=len(message),
                    parsed=True,
                    parse_error=None,
                    raw_count=result['row_count'],
                    columns=result['columns'],
                    preview=result['preview']
                )
        except:
            pass

    return None
