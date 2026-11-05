"""Unit tests for SelfHealer loop and resource file patching."""

from pathlib import Path
from unittest.mock import MagicMock
import pytest

from agent.robot.healer import SelfHealer
from agent.core.models import TestExecutionResult, UIElement, BoundingBox


def test_apply_patch_to_resource(tmp_path):
    resource_file = tmp_path / "app.resource"
    original_content = """*** Settings ***
Library    Browser

*** Keywords ***
Preencher Dados
    [Documentation]    Preenche
    Click    css=[data-testid="broken-selector"]
    Take Screenshot
"""
    resource_file.write_text(original_content, encoding="utf-8")

    healer = SelfHealer(
        llm_client=MagicMock(),
        browser_inspector=MagicMock(),
        robot_runner=MagicMock()
    )

    healer._apply_patch_to_resource(
        resource_path=resource_file,
        failed_kw_name="Preencher Dados",
        new_steps=["Click    css=[data-testid='fixed-selector']"]
    )

    updated = resource_file.read_text(encoding="utf-8")
    assert "fixed-selector" in updated
    assert "broken-selector" not in updated


def test_run_with_healing_success_on_first_try():
    mock_runner = MagicMock()
    mock_runner.run_suite.return_value = TestExecutionResult(
        success=True,
        total_tests=1,
        passed_tests=1,
        failed_tests=0,
        output_xml_path="/path/out.xml",
        log_html_path="/path/log.html",
        report_html_path="/path/report.html"
    )

    healer = SelfHealer(
        llm_client=MagicMock(),
        browser_inspector=MagicMock(),
        robot_runner=mock_runner
    )

    res, retries = healer.run_with_healing(Path("some_test.robot"), "http://localhost")
    assert res.success is True
    assert retries == 0


def test_run_with_healing_recovers_after_retry(tmp_path):
    robot_file = tmp_path / "test.robot"
    robot_file.write_text("*** Settings ***", encoding="utf-8")
    res_dir = tmp_path / "resources"
    res_dir.mkdir()
    res_file = res_dir / "test.resource"
    res_file.write_text("""*** Keywords ***
Click Element
    Click    id=wrong
""", encoding="utf-8")

    mock_runner = MagicMock()
    fail_res = TestExecutionResult(
        success=False,
        total_tests=1,
        passed_tests=0,
        failed_tests=1,
        output_xml_path=str(tmp_path / "out.xml"),
        log_html_path=str(tmp_path / "log.html"),
        report_html_path=str(tmp_path / "report.html"),
        failure_messages=["Element id=wrong not found"],
        failed_keyword="Click Element"
    )
    pass_res = TestExecutionResult(
        success=True,
        total_tests=1,
        passed_tests=1,
        failed_tests=0,
        output_xml_path=str(tmp_path / "out.xml"),
        log_html_path=str(tmp_path / "log.html"),
        report_html_path=str(tmp_path / "report.html")
    )
    mock_runner.run_suite.side_effect = [fail_res, pass_res]

    mock_inspector = MagicMock()
    mock_inspector.inspect_page.return_value = (
        tmp_path / "shot.png",
        [UIElement(mark_id=1, tag_name="button", element_id="correct", bbox=BoundingBox(x=0,y=0,width=10,height=10))],
        "Title"
    )

    mock_llm = MagicMock()
    mock_llm.generate_healing_fix.return_value = {
        "explanation": "Fixed selector",
        "repaired_steps": ["Click    id=correct"]
    }

    healer = SelfHealer(
        llm_client=mock_llm,
        browser_inspector=mock_inspector,
        robot_runner=mock_runner,
        max_retries=2
    )

    final_res, retries = healer.run_with_healing(robot_file, "http://localhost", tmp_path)
    assert final_res.success is True
    assert retries == 1
    assert "id=correct" in res_file.read_text(encoding="utf-8")
