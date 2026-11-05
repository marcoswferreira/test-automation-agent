"""Self-healing loop for broken Robot Framework tests and selectors."""

import re
from pathlib import Path
from typing import Optional, Tuple

from agent.core.llm_client import LLMClient
from agent.vision.browser_session import BrowserInspector
from agent.robot.runner import RobotRunner
from agent.core.models import TestExecutionResult


class SelfHealer:
    def __init__(self, llm_client: LLMClient, browser_inspector: BrowserInspector, robot_runner: RobotRunner, max_retries: int = 2):
        self.llm_client = llm_client
        self.browser_inspector = browser_inspector
        self.robot_runner = robot_runner
        self.max_retries = max_retries

    def run_with_healing(self, robot_file_path: Path, target_url: str, output_dir: Optional[Path] = None) -> Tuple[TestExecutionResult, int]:
        """Runs the suite and attempts self-healing if failures occur."""
        robot_file = Path(robot_file_path)
        out_dir = Path(output_dir or robot_file.parent / "results")
        
        # Initial run
        result = self.robot_runner.run_suite(robot_file, out_dir)
        if result.success:
            return result, 0

        retry_count = 0
        while not result.success and retry_count < self.max_retries:
            retry_count += 1
            print(f"\n[Self-Healing] Tentativa {retry_count}/{self.max_retries}: Analisando causa da falha...")

            # 1. Inspect live page to see current elements
            heal_dir = out_dir / f"heal_attempt_{retry_count}"
            screenshot_path, current_elements, _ = self.browser_inspector.inspect_page(target_url, heal_dir, f"heal_{retry_count}")

            # 2. Extract error info
            error_msg = "\n".join(result.failure_messages)
            failed_kw = result.failed_keyword or "Desconhecido"

            # 3. Request healing patch from LLM
            patch = self.llm_client.generate_healing_fix(
                test_name=robot_file.stem,
                error_message=error_msg,
                failed_step=failed_kw,
                current_elements=current_elements,
                current_screenshot=screenshot_path
            )

            print(f"[Self-Healing] Diagnóstico: {patch.get('explanation')}")
            repaired_steps = patch.get("repaired_steps", [])

            # 4. Patch .resource file
            resource_file = robot_file.parent / "resources" / f"{robot_file.stem}.resource"
            if resource_file.exists() and repaired_steps:
                self._apply_patch_to_resource(resource_file, failed_kw, repaired_steps)
            else:
                print(f"[Self-Healing] Arquivo .resource não encontrado ou patch vazio.")
                break

            # 5. Re-run test
            print(f"[Self-Healing] Reexecutando suíte com as correções aplicadas...")
            result = self.robot_runner.run_suite(robot_file, out_dir)
            if result.success:
                print(f"[Self-Healing] Sucesso! O teste foi corrigido automaticamente e passou na tentativa {retry_count}.")
                return result, retry_count

        return result, retry_count

    def _apply_patch_to_resource(self, resource_path: Path, failed_kw_name: str, new_steps: list):
        content = resource_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        new_lines = []
        inside_failed_kw = False
        replaced = False

        for line in lines:
            if line and not line.startswith(" ") and not line.startswith("\t") and not line.startswith("***"):
                # New keyword header
                if failed_kw_name and failed_kw_name.lower() in line.lower():
                    inside_failed_kw = True
                    new_lines.append(line)
                    continue
                else:
                    inside_failed_kw = False

            if inside_failed_kw and not replaced:
                # If this was an interaction line, replace with repaired steps
                if any(action in line for action in ["Click", "Fill Text", "Get Text", "Wait For"]):
                    for step in new_steps:
                        new_lines.append(f"    {step}")
                    replaced = True
                    continue

            new_lines.append(line)

        # If not matched inside keyword, append general replacement or fallback
        resource_path.write_text("\n".join(new_lines), encoding="utf-8")

