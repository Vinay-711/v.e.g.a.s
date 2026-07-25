"""
API Client tools for VEGAS AIOS.

Allows making HTTP requests.
Gated by @requires_confirmation for mutation methods (POST, PUT, DELETE, PATCH).
"""

import json
import requests
from vegas.safety import requires_confirmation
from vegas.memory import log_event

def _is_mutation_method(method: str) -> bool:
    """Returns True if the HTTP method modifies external state."""
    return method.strip().upper() in ["POST", "PUT", "DELETE", "PATCH"]

@requires_confirmation
def _confirmed_http_request(method: str, url: str, headers_json: str = None, data: str = None) -> str:
    """Confirmation-gated HTTP request executor."""
    headers = json.loads(headers_json) if headers_json else None
    return _send_request(method, url, headers, data)

def _send_request(method: str, url: str, headers: dict = None, data: str = None) -> str:
    """Internal HTTP request sender."""
    method_upper = method.strip().upper()
    try:
        # Load string data as JSON if possible to send clean payload
        payload = data
        if data:
            try:
                payload = json.loads(data)
            except ValueError:
                pass
                
        # Fire request
        if method_upper == "GET":
            res = requests.get(url, headers=headers, timeout=15)
        elif method_upper == "POST":
            res = requests.post(url, headers=headers, json=payload if isinstance(payload, dict) else None, data=payload if not isinstance(payload, dict) else None, timeout=15)
        elif method_upper == "PUT":
            res = requests.put(url, headers=headers, json=payload if isinstance(payload, dict) else None, data=payload if not isinstance(payload, dict) else None, timeout=15)
        elif method_upper == "DELETE":
            res = requests.delete(url, headers=headers, timeout=15)
        elif method_upper == "PATCH":
            res = requests.patch(url, headers=headers, json=payload if isinstance(payload, dict) else None, data=payload if not isinstance(payload, dict) else None, timeout=15)
        else:
            return f"Error: Unsupported HTTP method '{method}'."
            
        return f"HTTP {res.status_code} Response:\n{res.text[:4000]}"
    except Exception as e:
        return f"HTTP request failed: {e}"

def make_http_request(method: str, url: str, headers: dict = None, data: str = None) -> str:
    """
    Makes an HTTP request to any external web service or API.
    Automatically gates and requires user confirmation for state-modifying requests
    (POST, PUT, DELETE, PATCH).

    Args:
        method: The HTTP method (GET, POST, PUT, DELETE, PATCH).
        url: The full endpoint URL.
        headers: Optional dictionary of HTTP headers.
        data: Optional body string or JSON string payload.
    """
    log_event("api_client", f"HTTP {method} request to {url}", f"Headers: {headers}, Data: {data}")
    
    method_upper = method.strip().upper()
    if _is_mutation_method(method_upper):
        headers_str = json.dumps(headers) if headers else None
        return _confirmed_http_request(method_upper, url, headers_str, data)
        
    return _send_request(method_upper, url, headers, data)

def register(mcp) -> None:
    """Registers API client tools with FastMCP."""
    mcp.tool()(make_http_request)
