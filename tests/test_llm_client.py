"""Unit tests for LLMClient multimodal reasoning and heuristic fallbacks."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from agent.core.llm_client import LLMClient
from agent.core.models import UIElement, BoundingBox, VisualChange, TestSuiteDefinition


@pytest.fixture
def sample_elements():
    return [
        UIElement(
            mark_id=1,
            tag_name="input",
            test_id="input-username",
            element_id="username",
            bbox=BoundingBox(x=10, y=10, width=100, height=30),
            selector_candidates=['css=[data-testid="input-username"]']
        ),
        UIElement(
            mark_id=2,
            tag_name="input",
            test_id="input-email",
            element_id="user-email",
            bbox=BoundingBox(x=10, y=50, width=100, height=30),
            selector_candidates=['css=[data-testid="input-email"]']
        ),
        UIElement(
            mark_id=3,
            tag_name="input",
            test_id="input-coupon",
            element_id="coupon",
            bbox=BoundingBox(x=10, y=90, width=100, height=30),
            selector_candidates=['css=[data-testid="input-coupon"]']
        ),
        UIElement(
            mark_id=4,
            tag_name="button",
            test_id="btn-select-plan",
            text="Selecionar",
            bbox=BoundingBox(x=10, y=130, width=80, height=30),
            selector_candidates=['css=[data-testid="btn-select-plan"]']
        ),
        UIElement(
            mark_id=5,
            tag_name="button",
            test_id="btn-submit-order",
            text="Confirmar Pedido",
            bbox=BoundingBox(x=10, y=170, width=100, height=35),
            selector_candidates=['css=[data-testid="btn-submit-order"]']
        ),
        UIElement(
            mark_id=6,
            tag_name="div",
            test_id="modal-confirm",
            text="Confirmar Agora",
            bbox=BoundingBox(x=50, y=50, width=200, height=100),
            selector_candidates=['css=[data-testid="modal-confirm"]']
        ),
        UIElement(
            mark_id=7,
            tag_name="div",
            test_id="status-message",
            element_id="feedback",
            text="sucesso",
            bbox=BoundingBox(x=10, y=210, width=200, height=40),
            selector_candidates=['css=[data-testid="status-message"]']
        )
    ]


def test_extract_json():
    client = LLMClient()

    # Raw json
    raw = '{"key": "value"}'
    assert client._extract_json(raw) == {"key": "value"}

    # Markdown block
    md = '```json\n{"suite_name": "Test1"}\n```'
    assert client._extract_json(md) == {"suite_name": "Test1"}

    # Without json language tag
    md2 = '```\n{"suite_name": "Test2"}\n```'
    assert client._extract_json(md2) == {"suite_name": "Test2"}


def test_heuristic_explore_generation(sample_elements):
    client = LLMClient()
    suite = client._heuristic_explore_generation(
        target_url="http://localhost:8000/v1",
        intent="Preencher dados e confirmar",
        elements=sample_elements
    )

    assert isinstance(suite, TestSuiteDefinition)
    assert suite.suite_name == "Suite_Exploratoria_Dinamica"
    assert len(suite.keywords) >= 3
    assert len(suite.test_cases) == 1
    assert "Preencher Dados Do Cliente" in [k.name for k in suite.keywords]
    assert "Selecionar Plano" in [k.name for k in suite.keywords]
    assert "Finalizar E Validar Pedido" in [k.name for k in suite.keywords]


def test_heuristic_diff_generation(sample_elements):
    client = LLMClient()
    changes = [
        VisualChange(
            change_type="added",
            description="Novo cupom",
            suggested_assertion="Wait For Elements State    css=[data-testid='input-coupon']    visible"
        ),
        VisualChange(
            change_type="modified",
            description="Botao renomeado",
            suggested_assertion="Get Text    id=portal-title    ==    Novo Titulo"
        )
    ]

    suite = client._heuristic_diff_generation(
        target_url="http://localhost:8000/v2",
        changes=changes,
        target_elements=sample_elements
    )

    assert isinstance(suite, TestSuiteDefinition)
    assert suite.suite_name == "Suite_Regressao_Visual_Diff"
    assert len(suite.test_cases) == 2
    tc_names = [tc.name for tc in suite.test_cases]
    assert "Validar Elementos E Alteracoes Visuais V2" in tc_names
    assert "Validar Fluxo De Regressao Da Versao Atualizada" in tc_names


def test_generate_healing_fix_heuristic(sample_elements, tmp_path):
    client = LLMClient()
    fake_img = tmp_path / "fake.png"
    fake_img.write_bytes(b"")

    # When error matches broken selector
    fix = client.generate_healing_fix(
        test_name="broken_test",
        error_message="Element with locator css=[data-testid='wrong-btn'] not found",
        failed_step="Click    css=[data-testid='wrong-btn']",
        current_elements=sample_elements,
        current_screenshot=fake_img
    )

    assert "repaired_steps" in fix
    assert "explanation" in fix
    assert len(fix["repaired_steps"]) > 0

    # Fallback when no interactive elements match
    fix_empty = client.generate_healing_fix(
        test_name="broken_test",
        error_message="timeout",
        failed_step="Wait For Elements State",
        current_elements=[],
        current_screenshot=fake_img
    )
    assert fix_empty["repaired_steps"] == ["Sleep    1s"]


def test_gemini_multimodal_call(tmp_path):
    client = LLMClient(api_key="fake-key")
    mock_genai = MagicMock()
    client._genai_client = mock_genai

    # Mock response
    mock_resp = MagicMock()
    mock_resp.text = json.dumps({
        "suite_name": "Suite_Mock",
        "documentation": "Doc",
        "target_url": "http://localhost",
        "resource_name": "res.resource",
        "variables": {},
        "keywords": [],
        "test_cases": []
    })
    mock_genai.models.generate_content.return_value = mock_resp

    fake_img = tmp_path / "screen.png"
    from PIL import Image
    Image.new("RGB", (100, 100)).save(fake_img)

    result_text = client._call_gemini_multimodal("prompt", fake_img)
    assert "Suite_Mock" in result_text

    suite = client.generate_suite_for_explore("http://localhost", "intent", fake_img, [], "summary")
    assert suite.suite_name == "Suite_Mock"

    suite_diff = client.generate_suite_for_diff("http://v1", "http://v2", fake_img, [], [], "diff", "elements")
    assert suite_diff.suite_name == "Suite_Mock"

    mock_resp.text = json.dumps({"explanation": "Mock fix", "repaired_steps": ["Click    id=ok"]})
    heal_fix = client.generate_healing_fix("test", "err", "step", [], fake_img)
    assert heal_fix["explanation"] == "Mock fix"
