"""
File system automation tools for VEGAS AIOS.

Restricts all operations (read, list, write, delete) to a configurable
VEGAS_SANDBOX_ROOT directory. Write and delete operations are gated
by @requires_confirmation.
"""

import os
from pathlib import Path
from vegas.config import config
from vegas.safety import requires_confirmation

def _verify_sandbox_path(path_str: str) -> Path:
    """
    Validates that the given path resolves within the configured sandbox root.
    Raises PermissionError if the path escapes the sandbox.
    """
    sandbox_root = Path(config.VEGAS_SANDBOX_ROOT).expanduser().resolve()
    
    # Ensure the sandbox root directory exists so path verification is reliable
    sandbox_root.mkdir(parents=True, exist_ok=True)
    
    target_path = Path(path_str).expanduser()
    if not target_path.is_absolute():
        target_path = sandbox_root / target_path
        
    # Resolve the path to resolve symlinks and '..' components
    try:
        resolved_path = target_path.resolve(strict=False)
    except Exception as e:
        raise PermissionError(f"Access Denied: Failed to resolve path '{path_str}' — {e}")
        
    # Verify the resolved path is inside the sandbox root using commonpath
    try:
        common = os.path.commonpath([str(sandbox_root), str(resolved_path)])
        if common != str(sandbox_root):
            raise PermissionError(f"Access Denied: Path '{path_str}' is outside the sandbox root '{config.VEGAS_SANDBOX_ROOT}'.")
    except ValueError:
        raise PermissionError(f"Access Denied: Path '{path_str}' is outside the sandbox root '{config.VEGAS_SANDBOX_ROOT}'.")
        
    return resolved_path

def read_file(path: str) -> str:
    """
    Reads the content of a file within the sandbox root.

    Args:
        path: Path to the file, relative to the sandbox root or absolute within it.
    """
    try:
        resolved = _verify_sandbox_path(path)
        if not resolved.exists():
            return f"Error: File '{path}' does not exist."
        if not resolved.is_file():
            return f"Error: '{path}' is not a file."
        return resolved.read_text(encoding="utf-8")
    except PermissionError as pe:
        return str(pe)
    except Exception as e:
        return f"Error reading file '{path}': {e}"

def list_directory(path: str = ".") -> str:
    """
    Lists the contents of a directory within the sandbox root.

    Args:
        path: Path to the directory, relative to the sandbox root (defaults to ".").
    """
    try:
        resolved = _verify_sandbox_path(path)
        if not resolved.exists():
            return f"Error: Directory '{path}' does not exist."
        if not resolved.is_dir():
            return f"Error: '{path}' is not a directory."
            
        items = sorted(resolved.iterdir())
        if not items:
            return f"Directory '{path}' is empty."
            
        lines = []
        for item in items:
            prefix = "[DIR] " if item.is_dir() else "[FILE]"
            lines.append(f"{prefix} {item.name}")
        return "\n".join(lines)
    except PermissionError as pe:
        return str(pe)
    except Exception as e:
        return f"Error listing directory '{path}': {e}"

@requires_confirmation
def write_file(path: str, content: str) -> str:
    """
    Writes content to a file within the sandbox root. Creates parent directories if missing.
    Gated by @requires_confirmation.

    Args:
        path: Path to the destination file.
        content: Text content to write.
    """
    try:
        resolved = _verify_sandbox_path(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        return f"Successfully wrote to file '{path}' (size: {len(content)} characters)."
    except PermissionError as pe:
        return str(pe)
    except Exception as e:
        return f"Error writing to file '{path}': {e}"

@requires_confirmation
def delete_file(path: str) -> str:
    """
    Deletes a file within the sandbox root.
    Gated by @requires_confirmation.

    Args:
        path: Path to the file to delete.
    """
    try:
        resolved = _verify_sandbox_path(path)
        if not resolved.exists():
            return f"Error: File '{path}' does not exist."
        if resolved.is_dir():
            return f"Error: '{path}' is a directory, not a file."
        resolved.unlink()
        return f"Successfully deleted file '{path}'."
    except PermissionError as pe:
        return str(pe)
    except Exception as e:
        return f"Error deleting file '{path}': {e}"

def register(mcp) -> None:
    """Registers sandboxed file system tools with FastMCP."""
    mcp.tool(name="read_file")(read_file)
    mcp.tool(name="sandboxed_list_directory")(list_directory)
    mcp.tool(name="sandboxed_write_file")(write_file)
    mcp.tool(name="delete_file")(delete_file)
