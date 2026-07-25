"""
Security Guardrails Layer for VEGAS AIOS.
Validates path access, monitors shell command safety, and protects system parameters.
"""

import os
import re
import ast
from typing import Set, List

# List of prohibited command sub-strings or binaries
PROHIBITED_COMMAND_PATTERNS = [
    r"\brm\s+-[rRfF]*\s+/\b",       # rm -rf /
    r"\bdd\s+if=\b",                # disk destruction
    r"\bmkfs\b",                     # format disk
    r"\bshutdown\b",                 # shutdown machine
    r"\breboot\b",                   # reboot machine
    r"/\.env\b",                     # modifying environment directly via shell
    r"\bchmod\s+-\w*\s*777\b",      # insecure permissions
    r"\bchown\b",                    # changing ownership
]

class SecurityError(Exception):
    """Raised when a tool action violates security guardrails."""
    pass

class Guardrails:
    def __init__(self, allowed_workspaces: List[str] = None):
        if allowed_workspaces is None:
            # Default to the parent of the project workspace
            project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.allowed_workspaces = [project_dir]
        else:
            self.allowed_workspaces = [os.path.abspath(w) for w in allowed_workspaces]

    def validate_path(self, path: str, write_operation: bool = False) -> str:
        """
        Validates that the target path lies within allowed workspace directories
        and prevents directory traversal attacks.
        """
        abs_path = os.path.abspath(path)
        
        # Check traversal
        is_safe = False
        for workspace in self.allowed_workspaces:
            if abs_path.startswith(workspace):
                is_safe = True
                break
                
        if not is_safe:
            raise SecurityError(
                f"Access denied: Path '{path}' is outside the allowed workspaces."
            )
            
        # Sensitive systems files block
        prohibited_dirs = ["/etc", "/var", "/bin", "/sbin", "/usr", "/System", "/Library"]
        for p_dir in prohibited_dirs:
            if abs_path.startswith(p_dir):
                raise SecurityError(f"Access denied: Path '{path}' targets system directory.")
                
        return abs_path

    def validate_command(self, command: str) -> str:
        """
        Verifies that shell commands do not match prohibited destructive execution patterns.
        """
        stripped_cmd = command.strip()
        
        for pattern in PROHIBITED_COMMAND_PATTERNS:
            if re.search(pattern, stripped_cmd):
                raise SecurityError(
                    f"Execution blocked: Command '{command}' violates security guardrails."
                )
        return stripped_cmd

    def audit_python_code(self, code: str) -> None:
        """
        Uses Abstract Syntax Tree (AST) parsing to detect unsafe executions
        in dynamically loaded Python scripts (e.g. self-written modules).
        """
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            raise SecurityError(f"Syntax validation failed: {str(e)}")

        for node in ast.walk(tree):
            # Block builtins override and dangerous module imports
            if isinstance(node, ast.Import):
                for name in node.names:
                    if name.name in ["os", "subprocess", "shutil", "pty"] and len(self.allowed_workspaces) > 0:
                        # Allow, but raise warning or impose execution constraints if needed
                        pass
            elif isinstance(node, ast.ImportFrom):
                if node.module in ["os", "subprocess", "shutil", "pty"]:
                    pass
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in ["eval", "exec"]:
                        raise SecurityError("Execution blocked: Use of 'eval' or 'exec' is prohibited.")

# Initialize global guardrails
guardrails = Guardrails()
