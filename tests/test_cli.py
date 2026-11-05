"""Unit tests for agent-rf CLI commands."""

from pathlib import Path
from typer.testing import CliRunner
import pytest

from agent.cli import app

runner = CliRunner()


@pytest.fixture
def repo_urls():
    root = Path(__file__).parent.parent
    v1 = root / "demo_app" / "v1" / "index.html"
    v2 = root / "demo_app" / "v2" / "index.html"
    return f"file://{v1.resolve()}", f"file://{v2.resolve()}"


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Agente Inteligente de Automação de Testes" in result.output
    assert "explore" in result.output
    assert "diff" in result.output
    assert "run" in result.output
    assert "inspect" in result.output


def test_cli_inspect(repo_urls, tmp_path):
    url_v1, _ = repo_urls
    out_dir = tmp_path / "inspect_out"
    result = runner.invoke(app, ["inspect", url_v1, "--output-dir", str(out_dir)])
    assert result.exit_code == 0
    assert "Inspeção concluída com sucesso!" in result.output
    assert (out_dir / "annotated_view.png").exists()


def test_cli_explore_no_run(repo_urls, tmp_path):
    url_v1, _ = repo_urls
    out_dir = tmp_path / "explore_out"
    result = runner.invoke(app, [
        "explore", url_v1,
        "--intent", "Testar fluxo",
        "--output-dir", str(out_dir),
        "--no-run"
    ])
    assert result.exit_code == 0
    assert "Formatando e gerando arquivos modulares" in result.output
    assert (out_dir / "suite_exploratoria_dinamica.robot").exists()


def test_cli_diff_no_run(repo_urls, tmp_path):
    url_v1, url_v2 = repo_urls
    out_dir = tmp_path / "diff_out"
    result = runner.invoke(app, [
        "diff", url_v1, url_v2,
        "--output-dir", str(out_dir),
        "--no-run"
    ])
    assert result.exit_code == 0
    assert "Gerando suíte Robot Framework" in result.output
    assert (out_dir / "suite_regressao_visual_diff.robot").exists()


def test_cli_run_minimal(tmp_path):
    test_robot = tmp_path / "simple.robot"
    test_robot.write_text("""*** Test Cases ***
Pass Test
    Should Be True    True
""", encoding="utf-8")

    result = runner.invoke(app, ["run", str(test_robot), "--output-dir", str(tmp_path / "results"), "--no-heal"])
    assert result.exit_code == 0
    assert "PASS" in result.output

