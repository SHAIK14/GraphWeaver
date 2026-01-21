from pathlib import Path
from itertools import islice
from typing import Dict, Any, List
from langchain_core.tools import tool

from app.core.config import get_settings

# Constants for state keys
ALL_AVAILABLE_FILES = "all_available_files"
SUGGESTED_FILES = "suggested_files"
APPROVED_FILES = "approved_files"


@tool
def get_approved_user_goal() -> Dict[str, Any]:
    """Returns the user's approved goal from the previous agent.
    
    Returns:
        dict: Contains 'kind_of_graph' and 'graph_description'
    """
   
    return {"status": "success", "message": "Goal retrieved from state"}


@tool
def list_available_files() -> Dict[str, Any]:
    """Lists all files available in the import directory.
    
    Returns:
        dict: Contains list of file names available for import
    """
    settings = get_settings()
    import_dir = Path(settings.data_import_dir)
    
    if not import_dir.exists():
        return {"status": "error", "error_message": f"Import directory does not exist: {import_dir}"}
    
    # Get all files (not directories)
    file_names = [str(f.relative_to(import_dir)) for f in import_dir.rglob("*") if f.is_file()]
    
    return {"status": "success", ALL_AVAILABLE_FILES: file_names}


@tool
def sample_file(file_path: str) -> Dict[str, Any]:
    """Samples a file by reading up to 100 lines.
    
    Use this to understand file contents before suggesting it.
    
    Args:
        file_path: Path to file, relative to import directory
        
    Returns:
        dict: Contains file content sample or error message
    """
    # Security: reject absolute paths
    if Path(file_path).is_absolute():
        return {"status": "error", "error_message": "File path must be relative to import directory"}
    
    settings = get_settings()
    import_dir = Path(settings.data_import_dir)
    full_path = import_dir / file_path
    
    if not full_path.exists():
        return {"status": "error", "error_message": f"File not found: {file_path}"}
    
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            lines = list(islice(f, 100))
            content = ''.join(lines)
            return {"status": "success", "content": content}
    except Exception as e:
        return {"status": "error", "error_message": f"Error reading file: {e}"}


@tool
def set_suggested_files(file_list: List[str]) -> Dict[str, Any]:
    """Sets the list of suggested files for import.
    
    Args:
        file_list: List of file paths to suggest
        
    Returns:
        dict: Confirmation of suggested files
    """
    # Actual state update happens in execute_tools_node
    return {"status": "success", SUGGESTED_FILES: file_list}


@tool
def get_suggested_files() -> Dict[str, Any]:
    """Gets the current list of suggested files.

    Use this to review what files have been suggested before asking for approval.

    Returns:
        dict: List of suggested files
    """
    # Actual state reading happens in execute_tools_node
    return {"status": "success", "message": "Suggested files retrieved from state"}


@tool
def approve_suggested_files() -> Dict[str, Any]:
    """Approves the suggested files for import.

    Only call this after user explicitly approves the suggestions.

    Returns:
        dict: Confirmation of approved files
    """
    # Actual state update happens in execute_tools_node
    return {"status": "success", "message": "Files approved"}
