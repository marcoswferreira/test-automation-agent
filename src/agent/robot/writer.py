"""Robot Framework code writer and file generator."""

from pathlib import Path
from typing import Tuple
from agent.core.models import TestSuiteDefinition


class RobotWriter:
    def __init__(self, indent: str = "    "):
        self.indent = indent

    def write_suite(self, suite_def: TestSuiteDefinition, output_dir: Path) -> Tuple[Path, Path]:
        """Generates companion .resource and .robot files in output_dir."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        resource_dir = output_dir / "resources"
        resource_dir.mkdir(parents=True, exist_ok=True)

        # File names
        base_name = suite_def.suite_name.lower().replace(" ", "_")
        resource_path = resource_dir / f"{base_name}.resource"
        robot_path = output_dir / f"{base_name}.robot"

        # 1. Generate .resource file
        resource_content = self._render_resource(suite_def)
        resource_path.write_text(resource_content, encoding="utf-8")

        # 2. Generate .robot file
        relative_resource_path = f"resources/{resource_path.name}"
        robot_content = self._render_robot(suite_def, relative_resource_path)
        robot_path.write_text(robot_content, encoding="utf-8")

        return robot_path, resource_path

    def _render_resource(self, suite_def: TestSuiteDefinition) -> str:
        lines = [
            "*** Settings ***",
            "Documentation    Arquivo de recursos e keywords gerado dinamicamente pelo Agente de Automação.",
            "Library          Browser",
            "",
            "*** Variables ***"
        ]

        for var_name, var_value in suite_def.variables.items():
            lines.append(f"{var_name:<20}{self.indent}{var_value}")

        lines.append("")
        lines.append("*** Keywords ***")

        for kw in suite_def.keywords:
            lines.append(kw.name)
            if kw.documentation:
                lines.append(f"{self.indent}[Documentation]{self.indent}{kw.documentation}")
            if kw.arguments:
                args_str = f"{self.indent}".join(kw.arguments)
                lines.append(f"{self.indent}[Arguments]{self.indent}{args_str}")
            for step in kw.steps:
                # Format step parts with 4-space delimiter
                parts = step.split("    ")
                formatted_step = f"{self.indent}".join(parts)
                lines.append(f"{self.indent}{formatted_step}")
            lines.append("")

        return "\n".join(lines)

    def _render_robot(self, suite_def: TestSuiteDefinition, relative_resource_path: str) -> str:
        lines = [
            "*** Settings ***",
            f"Documentation     {suite_def.documentation}",
            f"Resource          {relative_resource_path}",
            "Suite Teardown    Close Browser",
            "",
            "*** Test Cases ***"
        ]

        for tc in suite_def.test_cases:
            lines.append(tc.name)
            if tc.documentation:
                lines.append(f"{self.indent}[Documentation]{self.indent}{tc.documentation}")
            if tc.tags:
                tags_str = f"{self.indent}".join(tc.tags)
                lines.append(f"{self.indent}[Tags]{self.indent}{tags_str}")
            for step in tc.steps:
                parts = step.split("    ")
                formatted_step = f"{self.indent}".join(parts)
                lines.append(f"{self.indent}{formatted_step}")
            lines.append("")

        return "\n".join(lines)

