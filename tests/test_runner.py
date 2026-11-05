"""Unit tests for Robot Framework execution runner."""

import pytest
from pathlib import Path
from agent.robot.runner import RobotRunner


def test_robot_runner_executes_suite(tmp_path):
    robot_code = """*** Settings ***
Documentation    Suite de teste unitario minimo

*** Test Cases ***
Cenario Minimo Bem Sucedido
    [Documentation]    Teste simples de asserção
    Should Be Equal As Strings    robot    robot
"""
    test_file = tmp_path / "minimal.robot"
    test_file.write_text(robot_code, encoding="utf-8")

    runner = RobotRunner()
    result = runner.run_suite(test_file, tmp_path / "results")

    assert result.success is True
    assert result.total_tests == 1
    assert result.passed_tests == 1
    assert result.failed_tests == 0
    assert Path(result.output_xml_path).exists()
    assert Path(result.log_html_path).exists()


def test_robot_runner_captures_failure(tmp_path):
    robot_code = """*** Settings ***
Documentation    Suite com falha proposital

*** Test Cases ***
Cenario Com Falha
    [Documentation]    Teste que falha intencionalmente
    Should Be Equal As Strings    valor_esperado    valor_incorreto
"""
    test_file = tmp_path / "failing.robot"
    test_file.write_text(robot_code, encoding="utf-8")

    runner = RobotRunner()
    result = runner.run_suite(test_file, tmp_path / "results")

    assert result.success is False
    assert result.total_tests == 1
    assert result.failed_tests == 1
    assert len(result.failure_messages) > 0
    assert "valor_esperado" in result.failure_messages[0]

