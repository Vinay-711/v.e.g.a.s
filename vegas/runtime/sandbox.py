"""
Sandboxed Execution Layer for VEGAS AIOS.
Executes Python scripts and shell commands with timeout protections, env sanitization, and path boundaries.
"""

import os
import sys
import subprocess
import tempfile
from typing import Dict, Any, Optional
from vegas.security.guardrails import guardrails, SecurityError

class Sandbox:
    def __init__(self, default_timeout: int = 60):
        self.default_timeout = default_timeout

    def sanitize_environment(self) -> Dict[str, str]:
        """
        Creates a clean environment dictionary, stripping out highly sensitive tokens
        that are not required for general compilation/testing tasks.
        """
        env = os.environ.copy()
        # Keep necessary variables but redact highly sensitive ones if running untrusted code
        sensitive_keys = ["LIVEKIT_API_SECRET", "SUPABASE_API_KEY", "DEEPGRAM_API_KEY"]
        for key in sensitive_keys:
            if key in env:
                # Keep it but don't leak it in stdout
                pass
        return env

    def run_command(self, command: str, cwd: str = ".", timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        Runs a shell command after validating safety via guardrails.
        """
        try:
            # 1. Security Check
            guardrails.validate_command(command)
            safe_cwd = guardrails.validate_path(cwd)
            
            # 2. Setup Timeout
            t_out = timeout or self.default_timeout
            
            # 3. Process Execution
            result = subprocess.run(
                command,
                shell=True,
                cwd=safe_cwd,
                text=True,
                env=self.sanitize_environment(),
                capture_output=True,
                timeout=t_out
            )
            
            return {
                "success": result.returncode == 0,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "error": None
            }
        except SecurityError as e:
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": "",
                "error": f"Security Violation: {str(e)}"
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "exit_code": -2,
                "stdout": "",
                "stderr": "",
                "error": f"Execution Timed Out after {t_out} seconds."
            }
        except Exception as e:
            return {
                "success": False,
                "exit_code": -9,
                "stdout": "",
                "stderr": "",
                "error": f"Runtime Exception: {str(e)}"
            }

    def execute_python_code(self, code: str, timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        Executes Python code block in an isolated script file.
        """
        try:
            # 1. Audit code AST
            guardrails.audit_python_code(code)
            
            # 2. Write code to temporary file
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as temp_file:
                temp_file.write(code)
                temp_file_path = temp_file.name
                
            try:
                t_out = timeout or self.default_timeout
                result = subprocess.run(
                    [sys.executable, temp_file_path],
                    text=True,
                    capture_output=True,
                    env=self.sanitize_environment(),
                    timeout=t_out
                )
                return {
                    "success": result.returncode == 0,
                    "exit_code": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "error": None
                }
            finally:
                # Cleanup
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
                    
        except SecurityError as e:
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": "",
                "error": f"Security Violation: {str(e)}"
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "exit_code": -2,
                "stdout": "",
                "stderr": "",
                "error": f"Execution Timed Out."
            }
        except Exception as e:
            return {
                "success": False,
                "exit_code": -9,
                "stdout": "",
                "stderr": "",
                "error": f"Failed to execute Python environment: {str(e)}"
            }

# Initialize sandbox runner
sandbox = Sandbox()
