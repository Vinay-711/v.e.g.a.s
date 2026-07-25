"""
Dynamic Skill and Evolution Engine for VEGAS AIOS.
Allows the kernel to dynamically generate, lint, compile, and inject
new custom Python tools into its own execution loop at runtime.
"""

import os
import sys
import importlib.util
from typing import Dict, Any, Callable, List, Optional
from vegas.security.guardrails import guardrails, SecurityError

SKILLS_DIR = os.path.dirname(os.path.abspath(__file__))

class SkillManager:
    def __init__(self, mcp_server: Optional[Any] = None):
        self.mcp_server = mcp_server
        self.registered_skills: Dict[str, Callable] = {}
        # Ensure directory structure
        os.makedirs(SKILLS_DIR, exist_ok=True)
        # Create an empty __init__.py if not exists
        init_path = os.path.join(SKILLS_DIR, "__init__.py")
        if not os.path.exists(init_path):
            with open(init_path, "w") as f:
                f.write("# Dynamic skills registry\n")

    def create_skill(self, name: str, code: str, docstring: str) -> Dict[str, Any]:
        """
        Validates, saves, and compiles a dynamically written Python tool.
        """
        try:
            # 1. Validate name to avoid injection
            if not name.isidentifier():
                return {"success": False, "error": f"Invalid tool name format: {name}"}
                
            # 2. Audit AST for safety
            guardrails.audit_python_code(code)
            
            # 3. Create target file path
            filename = f"{name}.py"
            filepath = os.path.join(SKILLS_DIR, filename)
            
            # Format module code securely
            module_code = (
                f'"""\nDynamically compiled tool {name}.\n"""\n\n'
                f"{code}\n"
            )
            
            # 4. Save to disk
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(module_code)
                
            # 5. Test compile/import
            module_name = f"vegas.skills.{name}"
            spec = importlib.util.spec_from_file_location(module_name, filepath)
            if spec is None or spec.loader is None:
                raise ImportError("Failed to build specification loading model.")
                
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            
            # 6. Retrieve callable reference
            if not hasattr(module, name):
                # Clean up invalid file
                os.remove(filepath)
                return {"success": False, "error": f"Module does not define matching callable function '{name}'"}
                
            func = getattr(module, name)
            self.registered_skills[name] = func
            
            # 7. Hot-register onto running FastMCP server
            if self.mcp_server is not None:
                # Register tool decorator onto FastMCP instance
                self.mcp_server.tool()(func)
                print(f"SkillManager: Successfully injected new tool '{name}' into FastMCP registry.", flush=True)

            return {
                "success": True,
                "name": name,
                "path": filepath,
                "error": None
            }
            
        except SecurityError as e:
            return {"success": False, "error": f"Security Exception: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": f"Compilation Failure: {str(e)}"}

    def load_existing_skills(self) -> List[str]:
        """
        Iterates over files in the skills folder and loads them at startup.
        """
        loaded = []
        for file in os.listdir(SKILLS_DIR):
            if file.endswith(".py") and not file.startswith("__"):
                name = file[:-3]
                filepath = os.path.join(SKILLS_DIR, file)
                try:
                    module_name = f"vegas.skills.{name}"
                    spec = importlib.util.spec_from_file_location(module_name, filepath)
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        sys.modules[module_name] = module
                        spec.loader.exec_module(module)
                        if hasattr(module, name):
                            func = getattr(module, name)
                            self.registered_skills[name] = func
                            if self.mcp_server is not None:
                                self.mcp_server.tool()(func)
                            loaded.append(name)
                except Exception as e:
                    print(f"SkillManager Warning: Failed to pre-load skill {name}: {e}", flush=True)
        return loaded

# Global Skill Manager
skill_manager = SkillManager()
