"""Unit tests for BrowserInspector with Playwright."""

from pathlib import Path
import pytest
from agent.vision.browser_session import BrowserInspector


def test_browser_inspector_inspect_page(tmp_path):
    repo_root = Path(__file__).parent.parent
    demo_file = repo_root / "demo_app" / "v1" / "index.html"
    file_url = f"file://{demo_file.resolve()}"

    inspector = BrowserInspector(headless=True)
    screenshot_path, elements, title = inspector.inspect_page(file_url, tmp_path, "test_v1")

    assert screenshot_path.exists()
    assert title == "Portal de Demonstração - v1"
    assert len(elements) >= 5

    # Check extracted attributes
    test_ids = [e.test_id for e in elements if e.test_id]
    assert "input-username" in test_ids
    assert "btn-submit-order" in test_ids

    # Check bounding box
    first_el = elements[0]
    assert first_el.bbox.width > 0
    assert first_el.bbox.height > 0
    assert len(first_el.selector_candidates) > 0
