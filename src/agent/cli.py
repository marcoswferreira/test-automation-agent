"""Command Line Interface for Robot Framework + LLM Test Automation Agent."""

import os
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

from agent.vision.browser_session import BrowserInspector
from agent.vision.annotator import VisualAnnotator
from agent.vision.visual_differ import VisualDiffer
from agent.core.llm_client import LLMClient
from agent.robot.writer import RobotWriter
from agent.robot.runner import RobotRunner
from agent.robot.healer import SelfHealer

app = typer.Typer(help="Agente Inteligente de Automação de Testes (Robot Framework + LLM Multimodal)")
console = Console()


@app.command()
def explore(
    url: str = typer.Argument(..., help="URL da aplicação a ser inspecionada e testada (ex: https://seu-site.com)"),
    intent: str = typer.Option("Testar fluxo principal de ponta a ponta", "--intent", "-i", help="Objetivo do teste em linguagem natural"),
    output_dir: str = typer.Option("./generated_tests", "--output-dir", "-o", help="Diretório de saída dos testes e artefatos"),
    run: bool = typer.Option(True, "--run/--no-run", "-r", help="Executar os testes automaticamente após a geração"),
    heal: bool = typer.Option(True, "--heal/--no-heal", "-h", help="Ativar auto-recuperação (self-healing) em caso de falha"),
    headless: bool = typer.Option(True, "--headless/--headed", help="Executar navegador em segundo plano (headless) ou visível na tela (headed)")
):
    """Inspeciona a interface, analisa os elementos visuais via Set-of-Marks e gera a suíte Robot Framework."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    console.print(Panel(f"[bold cyan]Modo Exploratório / Orientado a Intenção[/bold cyan]\nAlvo: [yellow]{url}[/yellow]\nObjetivo: [green]{intent}[/green]\nModo do Navegador: [magenta]{'Headless (Segundo plano)' if headless else 'Headed (Janela visível)'}[/magenta]"))

    # 1. Inspecionar página e capturar elementos
    inspector = BrowserInspector(headless=headless)
    console.print("[1/4] Inspecionando página e capturando árvore de elementos...", style="blue")
    screenshot_path, elements, title = inspector.inspect_page(url, out_path / "inspection", "explore")
    console.print(f"  -> Título da página: [bold]{title}[/bold]")
    console.print(f"  -> {len(elements)} elementos interativos identificados.")

    # 2. Anotar elementos (Set-of-Marks)
    console.print("[2/4] Aplicando anotações visuais (Set-of-Marks)...", style="blue")
    annotator = VisualAnnotator()
    annotated_img, elements_summary = annotator.annotate(screenshot_path, elements, out_path / "inspection" / "annotated_view.png")
    console.print(f"  -> Visual anotado salvo em: [italic]{annotated_img}[/italic]")

    # 3. Chamar LLM para planejar e gerar a suíte
    console.print("[3/4] Solicitando raciocínio e geração ao LLM Multimodal...", style="blue")
    llm = LLMClient()
    suite_def = llm.generate_suite_for_explore(url, intent, annotated_img, elements, elements_summary)
    if not headless:
        suite_def.variables["${HEADLESS}"] = "False"

    # 4. Escrever arquivos do Robot Framework
    console.print("[4/4] Formatando e gerando arquivos modulares do Robot Framework...", style="blue")
    writer = RobotWriter()
    robot_path, resource_path = writer.write_suite(suite_def, out_path)
    console.print(f"  -> Suíte: [green]{robot_path}[/green]")
    console.print(f"  -> Recursos (Keywords): [green]{resource_path}[/green]")

    # Exibição de Resumo
    table = Table(title="Casos de Teste Gerados")
    table.add_column("Caso de Teste", style="cyan")
    table.add_column("Tags", style="magenta")
    table.add_column("Qtd Passos", justify="right")
    for tc in suite_def.test_cases:
        table.add_row(tc.name, ", ".join(tc.tags), str(len(tc.steps)))
    console.print(table)

    # Execução opcional
    if run:
        console.print("\n[bold green]Iniciando execução com Robot Framework...[/bold green]")
        runner = RobotRunner()
        var_overrides = {"HEADLESS": "False"} if not headless else {}
        if heal:
            healer = SelfHealer(llm, inspector, runner)
            exec_result, retries = healer.run_with_healing(robot_path, url, out_path / "results")
        else:
            exec_result = runner.run_suite(robot_path, out_path / "results", variable_overrides=var_overrides)
            retries = 0

        _display_execution_result(exec_result, retries)


@app.command()
def diff(
    baseline_url: str = typer.Argument(..., help="URL da versão baseline (ex: https://prod.meusite.com)"),
    target_url: str = typer.Argument(..., help="URL da versão modificada (ex: https://staging.meusite.com)"),
    output_dir: str = typer.Option("./generated_tests/diff_suite", "--output-dir", "-o", help="Diretório de saída"),
    run: bool = typer.Option(True, "--run/--no-run", "-r", help="Executar os testes após a geração"),
    heal: bool = typer.Option(True, "--heal/--no-heal", "-h", help="Ativar auto-recuperação"),
    headless: bool = typer.Option(True, "--headless/--headed", help="Executar navegador em segundo plano (headless) ou visível na tela (headed)")
):
    """Detecta alterações visuais e estruturais entre duas versões da aplicação e gera testes de regressão dinâmicos."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    console.print(Panel(f"[bold cyan]Modo Comparação Visual & Estrutural (Diff)[/bold cyan]\nBaseline: [yellow]{baseline_url}[/yellow]\nAtualizada: [green]{target_url}[/green]\nModo do Navegador: [magenta]{'Headless (Segundo plano)' if headless else 'Headed (Janela visível)'}[/magenta]"))

    inspector = BrowserInspector(headless=headless)
    console.print("[1/5] Inspecionando versão Baseline...", style="blue")
    base_shot, base_elements, _ = inspector.inspect_page(baseline_url, out_path / "baseline", "v1")

    console.print("[2/5] Inspecionando versão Atualizada...", style="blue")
    target_shot, target_elements, _ = inspector.inspect_page(target_url, out_path / "target", "v2")

    # Comparação visual e estrutural
    console.print("[3/5] Comparando imagens e árvores de elementos...", style="blue")
    differ = VisualDiffer()
    diff_img, changes, diff_summary = differ.compare(base_shot, target_shot, base_elements, target_elements, out_path / "diff")
    console.print(f"  -> Imagem de heatmap de diferenças: [italic]{diff_img}[/italic]")
    console.print(f"  -> {len(changes)} alterações detectadas.")

    # Anotar elementos da versão atualizada
    annotator = VisualAnnotator()
    annotated_target, elements_summary = annotator.annotate(target_shot, target_elements, out_path / "target" / "annotated_view.png")

    # Geração via LLM
    console.print("[4/5] Solicitando geração de testes focados nas alterações ao LLM...", style="blue")
    llm = LLMClient()
    suite_def = llm.generate_suite_for_diff(baseline_url, target_url, diff_img, target_elements, changes, diff_summary, elements_summary)
    if not headless:
        suite_def.variables["${HEADLESS}"] = "False"

    # Escrever arquivos
    console.print("[5/5] Gerando suíte Robot Framework...", style="blue")
    writer = RobotWriter()
    robot_path, resource_path = writer.write_suite(suite_def, out_path)
    console.print(f"  -> Suíte: [green]{robot_path}[/green]")
    console.print(f"  -> Recursos: [green]{resource_path}[/green]")

    # Tabela de mudanças
    table = Table(title="Alterações Detectadas")
    table.add_column("Tipo", style="yellow")
    table.add_column("Descrição", style="cyan")
    table.add_column("Sugestão de Asserção", style="green")
    for c in changes:
        table.add_row(c.change_type, c.description, c.suggested_assertion or "-")
    console.print(table)

    if run:
        console.print("\n[bold green]Executando testes de regressão gerados...[/bold green]")
        runner = RobotRunner()
        var_overrides = {"HEADLESS": "False"} if not headless else {}
        if heal:
            healer = SelfHealer(llm, inspector, runner)
            exec_result, retries = healer.run_with_healing(robot_path, target_url, out_path / "results")
        else:
            exec_result = runner.run_suite(robot_path, out_path / "results", variable_overrides=var_overrides)
            retries = 0

        _display_execution_result(exec_result, retries)


@app.command()
def run(
    robot_file: str = typer.Argument(..., help="Caminho do arquivo .robot para execução"),
    target_url: Optional[str] = typer.Option(None, "--url", "-u", help="URL alvo para permitir auto-recuperação (self-healing)"),
    heal: bool = typer.Option(True, "--heal/--no-heal", "-h", help="Ativar auto-recuperação em caso de falha"),
    headless: bool = typer.Option(True, "--headless/--headed", help="Executar navegador em segundo plano (headless) ou visível na tela (headed)"),
    output_dir: Optional[str] = typer.Option(None, "--output-dir", "-o", help="Diretório de saída dos logs")
):
    """Executa uma suíte de teste existente com Robot Framework e relatório formatado."""
    file_path = Path(robot_file)
    runner = RobotRunner()
    var_overrides = {"HEADLESS": "False"} if not headless else {}

    if heal and target_url:
        inspector = BrowserInspector(headless=headless)
        llm = LLMClient()
        healer = SelfHealer(llm, inspector, runner)
        exec_result, retries = healer.run_with_healing(file_path, target_url, Path(output_dir) if output_dir else None)
    else:
        exec_result = runner.run_suite(file_path, Path(output_dir) if output_dir else None, variable_overrides=var_overrides)
        retries = 0

    _display_execution_result(exec_result, retries)


@app.command()
def inspect(
    url: str = typer.Argument(..., help="URL da página para inspeção (ex: https://seu-site.com)"),
    headless: bool = typer.Option(True, "--headless/--headed", help="Executar navegador em segundo plano (headless) ou visível na tela (headed)"),
    output_dir: str = typer.Option("./inspection_output", "--output-dir", "-o", help="Diretório de saída da inspeção")
):
    """Apenas inspeciona uma página web, extrai elementos interativos e gera screenshot Set-of-Marks."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    console.print(Panel(f"[bold cyan]Inspeção Visual & Set-of-Marks[/bold cyan]\nAlvo: [yellow]{url}[/yellow]"))

    inspector = BrowserInspector(headless=headless)
    screenshot_path, elements, title = inspector.inspect_page(url, out_path, "inspect")

    annotator = VisualAnnotator()
    annotated_img, summary = annotator.annotate(screenshot_path, elements, out_path / "annotated_view.png")

    console.print(f"[bold green]Inspeção concluída com sucesso![/bold green]")
    console.print(f"  -> Título: [bold]{title}[/bold]")
    console.print(f"  -> Elementos interativos: [bold]{len(elements)}[/bold]")
    console.print(f"  -> Imagem anotada: [italic]{annotated_img}[/italic]")
    console.print("\n[bold]Tabela de Elementos Detectados:[/bold]")
    console.print(Markdown(summary))


def _display_execution_result(result, retries: int = 0):
    status_color = "green" if result.success else "red"
    status_text = "PASS" if result.success else "FAIL"

    panel_content = (
        f"Status Final: [bold {status_color}]{status_text}[/bold {status_color}]\n"
        f"Total de Testes: {result.total_tests} | Passaram: [green]{result.passed_tests}[/green] | Falharam: [red]{result.failed_tests}[/red]\n"
        f"Tentativas de Auto-Recuperação: {retries}\n\n"
        f"Relatório HTML: [cyan]{result.report_html_path}[/cyan]\n"
        f"Log Detalhado: [cyan]{result.log_html_path}[/cyan]"
    )
    if not result.success and result.failure_messages:
        panel_content += "\n\n[bold red]Mensagens de Falha:[/bold red]\n" + "\n".join(result.failure_messages)

    console.print(Panel(panel_content, title="Resultado da Execução do Robot Framework"))
