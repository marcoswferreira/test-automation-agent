"""Robot Framework test execution engine and result parser."""

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional
from robot.api import ExecutionResult

from agent.core.models import TestExecutionResult


class RobotRunner:
    def __init__(self, python_bin: Optional[str] = None):
        self.python_bin = python_bin or sys.executable

    def run_suite(self, robot_file_path: Path, output_dir: Optional[Path] = None, variable_overrides: Optional[dict] = None) -> TestExecutionResult:
        """Executes a .robot file and returns parsed execution results."""
        robot_file = Path(robot_file_path).resolve()
        if not robot_file.exists():
            raise FileNotFoundError(f"Arquivo de teste não encontrado: {robot_file}")

        out_dir = Path(output_dir or robot_file.parent / "results").resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            self.python_bin, "-m", "robot",
            "--outputdir", str(out_dir),
            "--log", "log.html",
            "--report", "report.html",
            "--output", "output.xml"
        ]

        if variable_overrides:
            for k, v in variable_overrides.items():
                cmd.extend(["--variable", f"{k}:{v}"])

        cmd.append(str(robot_file))

        env = os.environ.copy()
        cache_browsers = Path.home() / ".cache" / "ms-playwright"
        if cache_browsers.exists():
            env["PLAYWRIGHT_BROWSERS_PATH"] = str(cache_browsers)

        process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
        raw_output = process.stdout

        output_xml = out_dir / "output.xml"
        log_html = out_dir / "log.html"
        report_html = out_dir / "report.html"

        if not output_xml.exists():
            return TestExecutionResult(
                success=False,
                total_tests=0,
                passed_tests=0,
                failed_tests=1,
                output_xml_path=str(output_xml),
                log_html_path=str(log_html),
                report_html_path=str(report_html),
                failure_messages=["Falha ao iniciar a execução do Robot Framework: output.xml não gerado."],
                raw_console_output=raw_output
            )

        # Parse output.xml via Robot Framework ExecutionResult
        result = ExecutionResult(str(output_xml))
        stats = result.statistics.total

        failure_messages: List[str] = []
        failed_keyword: Optional[str] = None

        for test in result.suite.all_tests:
            if test.status != "PASS":
                failure_messages.append(f"Teste '{test.name}' falhou: {test.message}")
                for body_item in getattr(test, "body", []):
                    if getattr(body_item, "status", None) == "FAIL":
                        kw_name = getattr(body_item, "name", None) or getattr(body_item, "kwname", "desconhecido")
                        if not failed_keyword:
                            failed_keyword = kw_name
                        msg = getattr(body_item, "message", "")
                        failure_messages.append(f"  -> Keyword '{kw_name}' falhou: {msg}")

        return TestExecutionResult(
            success=(stats.failed == 0),
            total_tests=stats.total,
            passed_tests=stats.passed,
            failed_tests=stats.failed,
            output_xml_path=str(output_xml),
            log_html_path=str(log_html),
            report_html_path=str(report_html),
            failure_messages=failure_messages,
            failed_keyword=failed_keyword,
            raw_console_output=raw_output
        )
