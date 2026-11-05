"""Unit tests for Robot Framework writer."""

import pytest
from pathlib import Path
from agent.core.models import TestSuiteDefinition, KeywordDefinition, TestCaseDefinition
from agent.robot.writer import RobotWriter


def test_robot_writer_creates_valid_files(tmp_path):
    writer = RobotWriter()
    suite = TestSuiteDefinition(
        suite_name="Suite_Exemplo",
        documentation="Suite de teste de exemplo",
        target_url="http://localhost:8000",
        resource_name="resources/app.resource",
        variables={"${URL}": "http://localhost:8000", "${BROWSER}": "chromium"},
        keywords=[
            KeywordDefinition(
                name="Abrir Portal",
                documentation="Abre o portal",
                steps=["New Browser    chromium    headless=True", "New Page    ${URL}"]
            )
        ],
        test_cases=[
            TestCaseDefinition(
                name="Validar Abertura",
                documentation="Valida se a pagina abriu",
                tags=["smoke"],
                steps=["Abrir Portal"]
            )
        ]
    )

    robot_file, resource_file = writer.write_suite(suite, tmp_path)

    assert robot_file.exists()
    assert resource_file.exists()

    robot_text = robot_file.read_text(encoding="utf-8")
    resource_text = resource_file.read_text(encoding="utf-8")

    assert "*** Settings ***" in robot_text
    assert "Resource          resources/suite_exemplo.resource" in robot_text
    assert "Validar Abertura" in robot_text
    assert "Abrir Portal" in robot_text

    assert "*** Settings ***" in resource_text
    assert "Library          Browser" in resource_text
    assert "*** Variables ***" in resource_text
    assert "${URL}" in resource_text
    assert "New Browser    chromium    headless=True" in resource_text

