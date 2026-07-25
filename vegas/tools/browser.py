"""
Browser automation tools for VEGAS AIOS — powered by Playwright.

Provides two intentionally narrow tools:
  1. browse_and_extract  — headless page text extraction
  2. fill_web_form       — fill form fields, screenshot, optionally submit
                           (submit path is confirmation-gated via vegas.safety)

General "click anything, anywhere" autonomy is NOT exposed here on purpose.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict

from playwright.sync_api import sync_playwright, Page, TimeoutError as PwTimeout

from vegas.safety import requires_confirmation

_SCREENSHOTS_DIR = Path.home() / ".vegas" / "screenshots"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _launch_and_navigate(pw, url: str, timeout_ms: int = 15000) -> tuple:
    """
    Launches headless Chromium, opens a page, navigates to *url*, and waits
    for the network to settle.  Returns (browser, page).
    """
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
    # Give JS-heavy pages a moment to render
    try:
        page.wait_for_load_state("networkidle", timeout=5000)
    except PwTimeout:
        pass  # best-effort; proceed with whatever has loaded
    return browser, page


def _fill_fields(page: Page, field_values: Dict[str, str]) -> list[str]:
    """
    Fills form fields using label / name / placeholder heuristics.
    Returns a list of human-readable descriptions of what was filled.
    """
    filled: list[str] = []

    for key, value in field_values.items():
        locator = None

        # Strategy 1: label text (most user-friendly)
        try:
            candidate = page.get_by_label(key, exact=False)
            if candidate.count() > 0:
                locator = candidate.first
        except Exception:
            pass

        # Strategy 2: placeholder text
        if locator is None:
            try:
                candidate = page.get_by_placeholder(key, exact=False)
                if candidate.count() > 0:
                    locator = candidate.first
            except Exception:
                pass

        # Strategy 3: input[name=...] attribute
        if locator is None:
            try:
                candidate = page.locator(f'input[name="{key}"], textarea[name="{key}"], select[name="{key}"]')
                if candidate.count() > 0:
                    locator = candidate.first
            except Exception:
                pass

        # Strategy 4: input[id=...] attribute
        if locator is None:
            try:
                candidate = page.locator(f'#{key}')
                if candidate.count() > 0:
                    locator = candidate.first
            except Exception:
                pass

        if locator is not None:
            try:
                tag = locator.evaluate("el => el.tagName.toLowerCase()")
                if tag == "select":
                    locator.select_option(label=value)
                else:
                    locator.fill(value)
                filled.append(f"  ✓ '{key}' = '{value}'")
            except Exception as exc:
                filled.append(f"  ✗ '{key}' — fill failed: {exc}")
        else:
            filled.append(f"  ✗ '{key}' — no matching field found")

    return filled


def _take_screenshot(page: Page, label: str) -> str:
    """Takes a full-page screenshot and returns the saved path."""
    _SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = _SCREENSHOTS_DIR / f"{label}_{ts}.png"
    page.screenshot(path=str(path), full_page=True)
    return str(path)


# ---------------------------------------------------------------------------
# Tool 1: browse_and_extract
# ---------------------------------------------------------------------------

def browse_and_extract(url: str, instruction: str = "") -> str:
    """
    Launches headless Chromium, navigates to the given URL, and returns the
    page's visible text content truncated to 4000 characters.

    Args:
        url: The web page URL to visit.
        instruction: Optional context about what to look for (for the caller's
                     benefit — the tool itself returns the full visible text).
    """
    try:
        with sync_playwright() as pw:
            browser, page = _launch_and_navigate(pw, url)
            text = page.inner_text("body")
            browser.close()
    except Exception as exc:
        err_msg = str(exc)
        if "Executable doesn't exist" in err_msg or "playwright install" in err_msg:
            return "VEGAS Browser Error: Playwright Chromium browser binary is missing. Run 'playwright install chromium' to enable browser extraction."
        return f"VEGAS Browser Error: {err_msg}"

    # Truncate to 4000 chars
    if len(text) > 4000:
        text = text[:4000] + "\n\n[…truncated to 4000 chars]"

    header = f"Extracted text from {url}"
    if instruction:
        header += f" (instruction: {instruction})"
    return f"{header}\n\n{text}"


# ---------------------------------------------------------------------------
# Tool 2: fill_web_form
# ---------------------------------------------------------------------------

# The actual submit action is separated into its own confirmation-gated
# function so that fill-without-submit runs immediately while
# fill-and-submit requires explicit user approval.

@requires_confirmation
def _confirmed_fill_and_submit(url: str, field_values_json: str) -> str:
    """
    Confirmation-gated: fills a web form AND clicks submit.

    Args:
        url: Target form URL.
        field_values_json: JSON-encoded dict of field names to values.
    """
    fv: Dict[str, str] = json.loads(field_values_json)

    try:
        with sync_playwright() as pw:
            browser, page = _launch_and_navigate(pw, url)
            filled = _fill_fields(page, fv)
            screenshot_path = _take_screenshot(page, "form_submitted")

            # Click the first visible submit-like button
            submit_btn = page.locator(
                'button[type="submit"], input[type="submit"], '
                'button:has-text("Submit"), button:has-text("Send"), '
                'button:has-text("Save"), button:has-text("Sign in"), '
                'button:has-text("Log in")'
            ).first
            submit_btn.click(timeout=5000)

            # Wait briefly for navigation / response
            try:
                page.wait_for_load_state("networkidle", timeout=5000)
            except PwTimeout:
                pass

            after_screenshot = _take_screenshot(page, "form_after_submit")
            browser.close()

    except Exception as exc:
        return f"VEGAS Browser Error during submit: {exc}"

    lines = [
        f"Form submitted on {url}.",
        "Fields filled:",
        *filled,
        f"Pre-submit screenshot: {screenshot_path}",
        f"Post-submit screenshot: {after_screenshot}",
    ]
    return "\n".join(lines)


def fill_web_form(url: str, field_values: dict, submit: bool = False) -> str:
    """
    Navigates to a URL, fills form fields using label/name/placeholder
    heuristics, and takes a screenshot of the filled form.

    When submit=False (default): fills fields and screenshots only — safe,
    no confirmation needed.

    When submit=True: routes through the confirmation gate. The form will
    only be submitted after explicit user approval via confirm_task.

    Args:
        url: The web page URL containing the form.
        field_values: A dict mapping field labels/names/placeholders to values.
        submit: If True, submit the form (requires user confirmation first).
    """
    if submit:
        # Delegate to the confirmation-gated path.  Serialize field_values
        # to JSON so the deferred callable can replay it later.
        return _confirmed_fill_and_submit(url, json.dumps(field_values))

    # --- submit=False: fill + screenshot only (no gate) ---
    try:
        with sync_playwright() as pw:
            browser, page = _launch_and_navigate(pw, url)
            filled = _fill_fields(page, field_values)
            screenshot_path = _take_screenshot(page, "form_filled")
            browser.close()
    except Exception as exc:
        return f"VEGAS Browser Error: {exc}"

    lines = [
        f"Form on {url} filled (not submitted).",
        "Fields filled:",
        *filled,
        f"Screenshot saved: {screenshot_path}",
        "Say 'fill_web_form with submit=True' when ready to submit.",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register(mcp) -> None:
    """Registers browser automation tools with FastMCP."""
    mcp.tool()(browse_and_extract)
    mcp.tool()(fill_web_form)
