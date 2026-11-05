"""Multimodal LLM client interface for Gemini and offline heuristic fallback."""

import os
import json
import re
from pathlib import Path
from typing import Optional, Dict, Any, List
from PIL import Image

from agent.core.models import TestSuiteDefinition, KeywordDefinition, TestCaseDefinition, UIElement, VisualChange
from agent.core.prompts import ROBOT_SYSTEM_INSTRUCTIONS, EXPLORE_PROMPT_TEMPLATE, DIFF_PROMPT_TEMPLATE, HEALING_PROMPT_TEMPLATE


class LLMClient:
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name
        self._genai_client = None

        if self.api_key:
            try:
                from google import genai
                self._genai_client = genai.Client(api_key=self.api_key)
            except Exception as e:
                # Log or fallback
                pass

    def generate_suite_for_explore(
        self,
        target_url: str,
        user_intent: str,
        annotated_image_path: Path,
        elements: List[UIElement],
        elements_summary: str
    ) -> TestSuiteDefinition:
        """Generates a test suite based on user intent and visual Set-of-Marks."""
        prompt = EXPLORE_PROMPT_TEMPLATE.format(
            user_intent=user_intent,
            target_url=target_url,
            elements_summary=elements_summary
        )

        if self._genai_client:
            try:
                response = self._call_gemini_multimodal(prompt, annotated_image_path)
                data = self._extract_json(response)
                return TestSuiteDefinition(**data)
            except Exception as e:
                # Fallback to heuristic generation if API call fails
                print(f"[Aviso] Falha na chamada da API Gemini ({e}). Utilizando gerador inteligente local.")

        return self._heuristic_explore_generation(target_url, user_intent, elements)

    def generate_suite_for_diff(
        self,
        baseline_url: str,
        target_url: str,
        diff_image_path: Path,
        target_elements: List[UIElement],
        changes: List[VisualChange],
        diff_summary: str,
        elements_summary: str
    ) -> TestSuiteDefinition:
        """Generates a test suite covering visual & structural changes."""
        prompt = DIFF_PROMPT_TEMPLATE.format(
            diff_summary=diff_summary,
            elements_summary=elements_summary,
            baseline_url=baseline_url,
            target_url=target_url
        )

        if self._genai_client:
            try:
                response = self._call_gemini_multimodal(prompt, diff_image_path)
                data = self._extract_json(response)
                return TestSuiteDefinition(**data)
            except Exception as e:
                print(f"[Aviso] Falha na chamada da API Gemini ({e}). Utilizando gerador inteligente local.")

        return self._heuristic_diff_generation(target_url, changes, target_elements)

    def generate_healing_fix(
        self,
        test_name: str,
        error_message: str,
        failed_step: str,
        current_elements: List[UIElement],
        current_screenshot: Path
    ) -> Dict[str, Any]:
        """Generates a self-healing patch for a broken keyword or selector."""
        elements_summary = "\n".join([
            f"[{e.mark_id}] <{e.tag_name}> id='{e.element_id}' testid='{e.test_id}' text='{e.text}' locator='{e.selector_candidates[0] if e.selector_candidates else ''}'"
            for e in current_elements
        ])

        prompt = HEALING_PROMPT_TEMPLATE.format(
            test_name=test_name,
            error_message=error_message,
            failed_keyword_or_step=failed_step,
            current_elements=elements_summary
        )

        if self._genai_client:
            try:
                response = self._call_gemini_multimodal(prompt, current_screenshot)
                return self._extract_json(response)
            except Exception:
                pass

        # Heuristic healing: inspect error and find best match in current elements
        for el in current_elements:
            if el.test_id and el.test_id in failed_step:
                continue
            # Look for button or input with similar text
            if el.tag_name in ["button", "input", "a"] and el.selector_candidates:
                return {
                    "explanation": f"Seletor substituído pelo locator atualizado do elemento <{el.tag_name}> '{el.text or el.test_id}'.",
                    "repaired_keyword_name": "Keyword Corrigida",
                    "repaired_steps": [f"Click    {el.selector_candidates[0]}"]
                }

        return {
            "explanation": "Correção padrão com espera de estabilização do DOM.",
            "repaired_keyword_name": "Keyword Corrigida",
            "repaired_steps": ["Sleep    1s"]
        }

    def _call_gemini_multimodal(self, prompt: str, image_path: Path) -> str:
        """Helper to invoke Gemini API with image and prompt."""
        pil_img = Image.open(image_path)
        response = self._genai_client.models.generate_content(
            model=self.model_name,
            contents=[ROBOT_SYSTEM_INSTRUCTIONS, pil_img, prompt]
        )
        return response.text

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extracts JSON block from LLM response."""
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        clean_text = match.group(1) if match else text.strip()
        return json.loads(clean_text)

    def _heuristic_explore_generation(self, target_url: str, intent: str, elements: List[UIElement]) -> TestSuiteDefinition:
        """Constructs an idiomatic Robot Framework test suite from UI elements and intent."""
        # Detect key fields
        username_el = next((e for e in elements if e.test_id == "input-username" or "username" in (e.element_id or "")), None)
        email_el = next((e for e in elements if e.test_id == "input-email" or "email" in (e.element_id or "")), None)
        coupon_el = next((e for e in elements if "coupon" in (e.test_id or "")), None)
        select_btn = next((e for e in elements if "select" in (e.test_id or "") or (e.text and "Selecionar" in e.text)), None)
        submit_btn = next((e for e in elements if "submit" in (e.test_id or "") or "finalize" in (e.test_id or "") or (e.text and ("Confirmar" in e.text or "Finalizar" in e.text))), None)
        modal_confirm = next((e for e in elements if "modal-confirm" in (e.test_id or "") or (e.text and "Confirmar Agora" in e.text)), None)
        feedback_el = next((e for e in elements if e.test_id == "status-message" or "feedback" in (e.element_id or "")), None)

        variables = {
            "${URL}": target_url,
            "${BROWSER}": "chromium",
            "${HEADLESS}": "True",
            "${DEFAULT_TIMEOUT}": "10s"
        }

        keywords: List[KeywordDefinition] = [
            KeywordDefinition(
                name="Acessar A Aplicacao",
                documentation="Inicializa o navegador e carrega a pagina alvo",
                steps=[
                    "New Browser    browser=${BROWSER}    headless=${HEADLESS}",
                    "New Context    viewport={'width': 1280, 'height': 800}",
                    "New Page    ${URL}",
                    "Wait For Elements State    id=portal-title    visible    timeout=${DEFAULT_TIMEOUT}"
                ]
            )
        ]

        # Login / Preenchimento keyword
        fill_steps = []
        if username_el:
            fill_steps.append(f"Fill Text    {username_el.selector_candidates[0]}    ${{usuario}}")
        if email_el:
            fill_steps.append(f"Fill Text    {email_el.selector_candidates[0]}    ${{email}}")
        if coupon_el:
            fill_steps.append(f"Fill Text    {coupon_el.selector_candidates[0]}    ${{cupom}}")

        if fill_steps:
            args = ["${usuario}", "${email}"]
            if coupon_el:
                args.append("${cupom}=${EMPTY}")
            keywords.append(KeywordDefinition(
                name="Preencher Dados Do Cliente",
                arguments=args,
                documentation="Preenche o formulario de cadastro do cliente",
                steps=fill_steps
            ))

        # Selecao de plano
        if select_btn:
            keywords.append(KeywordDefinition(
                name="Selecionar Plano",
                documentation="Clica no botao de selecao do plano desejado",
                steps=[
                    f"Click    {select_btn.selector_candidates[0]}",
                    "Wait For Elements State    css=[data-testid='input-selected-plan']    visible"
                ]
            ))

        # Finalizacao
        final_steps = []
        if submit_btn:
            final_steps.append(f"Click    {submit_btn.selector_candidates[0]}")
        if modal_confirm:
            final_steps.append("Wait For Elements State    css=[data-testid='modal-confirm']    visible    timeout=3s")
            final_steps.append(f"Click    {modal_confirm.selector_candidates[0]}")
        if feedback_el:
            final_steps.append(f"Wait For Elements State    {feedback_el.selector_candidates[0]}    visible    timeout=5s")
            final_steps.append(f"Get Text    {feedback_el.selector_candidates[0]}    contains    sucesso")
        final_steps.append("Take Screenshot    filename=evidencia_sucesso")

        keywords.append(KeywordDefinition(
            name="Finalizar E Validar Pedido",
            documentation="Submete o pedido e valida a mensagem de confirmacao",
            steps=final_steps
        ))

        # Test case
        test_steps = [
            "Acessar A Aplicacao",
            "Preencher Dados Do Cliente    usuario=Carlos Silva    email=carlos@empresa.com",
            "Selecionar Plano",
            "Finalizar E Validar Pedido"
        ]

        test_case = TestCaseDefinition(
            name=f"Cenario: {intent or 'Fluxo Principal de Contratacao'}",
            documentation="Valida o fluxo ponta a ponta gerado dinamicamente pelo agente",
            tags=["smoke", "e2e"],
            steps=test_steps
        )

        return TestSuiteDefinition(
            suite_name="Suite_Exploratoria_Dinamica",
            documentation=f"Suite gerada dinamicamente pelo agente para o objetivo: {intent}",
            target_url=target_url,
            resource_name="resources/app_keywords.resource",
            variables=variables,
            keywords=keywords,
            test_cases=[test_case]
        )

    def _heuristic_diff_generation(
        self,
        target_url: str,
        changes: List[VisualChange],
        target_elements: List[UIElement]
    ) -> TestSuiteDefinition:
        """Constructs an idiomatic Robot Framework test suite covering visual & DOM differences."""
        variables = {
            "${URL}": target_url,
            "${BROWSER}": "chromium",
            "${HEADLESS}": "True",
            "${DEFAULT_TIMEOUT}": "10s"
        }

        keywords: List[KeywordDefinition] = [
            KeywordDefinition(
                name="Acessar Pagina Atualizada",
                documentation="Abre a aplicacao na versao atualizada",
                steps=[
                    "New Browser    browser=${BROWSER}    headless=${HEADLESS}",
                    "New Context    viewport={'width': 1280, 'height': 800}",
                    "New Page    ${URL}",
                    "Wait For Elements State    id=portal-title    visible    timeout=${DEFAULT_TIMEOUT}"
                ]
            )
        ]

        # Build verification steps based on detected changes
        diff_verify_steps = []
        for change in changes:
            if change.suggested_assertion:
                diff_verify_steps.append(change.suggested_assertion)

        if not diff_verify_steps:
            diff_verify_steps = ["Get Title    ==    Portal de Demonstração - v2 Atualizado"]
        diff_verify_steps.append("Take Screenshot    filename=evidencia_mudancas_visuais")

        keywords.append(KeywordDefinition(
            name="Validar Alteracoes Visuais E Estruturais Detectadas",
            documentation="Verifica os elementos e textos novos ou modificados na versao",
            steps=diff_verify_steps
        ))

        # Also add full regression flow for new components (e.g. modal and coupon)
        coupon_el = next((e for e in target_elements if "coupon" in (e.test_id or "")), None)
        enterprise_btn = next((e for e in target_elements if "enterprise" in (e.test_id or "")), None)
        finalize_btn = next((e for e in target_elements if "finalize" in (e.test_id or "")), None)
        modal_btn = next((e for e in target_elements if "modal-confirm" in (e.test_id or "")), None)
        status_box = next((e for e in target_elements if "status-message" in (e.test_id or "")), None)

        regression_steps = [
            "Fill Text    css=[data-testid='input-username']    Usuario V2",
            "Fill Text    css=[data-testid='input-email']    v2@empresa.com"
        ]
        if coupon_el:
            regression_steps.append(f"Fill Text    {coupon_el.selector_candidates[0]}    TESTE20")
        if enterprise_btn:
            regression_steps.append(f"Click    {enterprise_btn.selector_candidates[0]}")
        if finalize_btn:
            regression_steps.append(f"Click    {finalize_btn.selector_candidates[0]}")
        if modal_btn:
            regression_steps.append("Wait For Elements State    css=[data-testid='modal-confirm']    visible")
            regression_steps.append(f"Click    {modal_btn.selector_candidates[0]}")
        if status_box:
            regression_steps.append(f"Wait For Elements State    {status_box.selector_candidates[0]}    visible")
            regression_steps.append(f"Get Text    {status_box.selector_candidates[0]}    contains    V2 finalizada")
        regression_steps.append("Take Screenshot    filename=evidencia_fluxo_v2")

        keywords.append(KeywordDefinition(
            name="Executar Fluxo Completo Com Novos Componentes",
            documentation="Executa o fluxo completo incluindo novos campos e modal",
            steps=regression_steps
        ))

        test_cases = [
            TestCaseDefinition(
                name="Validar Elementos E Alteracoes Visuais V2",
                documentation="Garante que os novos elementos de UI e modificacoes visuais estao visiveis e corretos",
                tags=["visual_diff", "ui_check"],
                steps=[
                    "Acessar Pagina Atualizada",
                    "Validar Alteracoes Visuais E Estruturais Detectadas"
                ]
            ),
            TestCaseDefinition(
                name="Validar Fluxo De Regressao Da Versao Atualizada",
                documentation="Garante que a interacao com novos campos e modais funciona de ponta a ponta",
                tags=["regression", "v2_features"],
                steps=[
                    "Acessar Pagina Atualizada",
                    "Executar Fluxo Completo Com Novos Componentes"
                ]
            )
        ]

        return TestSuiteDefinition(
            suite_name="Suite_Regressao_Visual_Diff",
            documentation=f"Suite gerada para cobrir diferencas visuais e funcionais entre versoes",
            target_url=target_url,
            resource_name="resources/diff_keywords.resource",
            variables=variables,
            keywords=keywords,
            test_cases=test_cases
        )

