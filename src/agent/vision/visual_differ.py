"""Visual and structural difference analyzer for web interfaces."""

from pathlib import Path
from typing import List, Tuple, Dict, Any
import cv2
import numpy as np
from PIL import Image

from agent.core.models import UIElement, VisualChange


class VisualDiffer:
    def __init__(self, diff_threshold: int = 25, min_contour_area: int = 150):
        self.diff_threshold = diff_threshold
        self.min_contour_area = min_contour_area

    def compare(
        self,
        baseline_screenshot: Path,
        target_screenshot: Path,
        baseline_elements: List[UIElement],
        target_elements: List[UIElement],
        output_dir: Path
    ) -> Tuple[Path, List[VisualChange], str]:
        """Compares two screenshots and element trees, returns diff image and structured changes."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        diff_image_path = output_dir / "visual_diff_result.png"

        # 1. Image-based perceptual diff
        img1 = cv2.imread(str(baseline_screenshot))
        img2 = cv2.imread(str(target_screenshot))

        # Adjust dimensions if needed
        h1, w1 = img1.shape[:2]
        h2, w2 = img2.shape[:2]
        max_h = max(h1, h2)
        max_w = max(w1, w2)

        canvas1 = np.zeros((max_h, max_w, 3), dtype=np.uint8)
        canvas2 = np.zeros((max_h, max_w, 3), dtype=np.uint8)
        canvas1[:h1, :w1] = img1
        canvas2[:h2, :w2] = img2

        gray1 = cv2.cvtColor(canvas1, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(canvas2, cv2.COLOR_BGR2GRAY)

        abs_diff = cv2.absdiff(gray1, gray2)
        _, thresh = cv2.threshold(abs_diff, self.diff_threshold, 255, cv2.THRESH_BINARY)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
        dilated = cv2.dilate(thresh, kernel, iterations=2)

        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Highlight differences on target image
        result_img = canvas2.copy()
        diff_boxes = []
        for c in contours:
            if cv2.contourArea(c) >= self.min_contour_area:
                x, y, w, h = cv2.boundingRect(c)
                diff_boxes.append((x, y, w, h))
                # Red bounding box with translucent fill
                cv2.rectangle(result_img, (x, y), (x + w, y + h), (0, 0, 235), 2)

        cv2.imwrite(str(diff_image_path), result_img)

        # 2. Structural DOM & element comparison
        changes: List[VisualChange] = []

        baseline_map = {self._element_key(el): el for el in baseline_elements}
        target_map = {self._element_key(el): el for el in target_elements}

        # Check for added elements in target
        for key, target_el in target_map.items():
            if key not in baseline_map:
                desc = f"Novo elemento adicionado: <{target_el.tag_name}> '{target_el.text or target_el.placeholder or target_el.test_id or target_el.element_id}'"
                suggested_assertion = f"Wait For Elements State    {target_el.selector_candidates[0]}    visible"
                changes.append(VisualChange(
                    change_type="added",
                    description=desc,
                    affected_element_ids=[target_el.test_id or target_el.element_id or str(target_el.mark_id)],
                    confidence=0.95,
                    suggested_assertion=suggested_assertion
                ))
            else:
                base_el = baseline_map[key]
                # Check text or role modifications
                if (base_el.text or "") != (target_el.text or ""):
                    desc = f"Texto modificado em <{target_el.tag_name}>: de '{base_el.text}' para '{target_el.text}'"
                    changes.append(VisualChange(
                        change_type="modified",
                        description=desc,
                        affected_element_ids=[target_el.test_id or target_el.element_id or str(target_el.mark_id)],
                        confidence=0.9,
                        suggested_assertion=f"Get Text    {target_el.selector_candidates[0]}    ==    {target_el.text}"
                    ))

        # Check for removed elements
        for key, base_el in baseline_map.items():
            if key not in target_map:
                desc = f"Elemento removido ou substituído: <{base_el.tag_name}> '{base_el.text or base_el.test_id or base_el.element_id}'"
                changes.append(VisualChange(
                    change_type="removed",
                    description=desc,
                    affected_element_ids=[base_el.test_id or base_el.element_id or str(base_el.mark_id)],
                    confidence=0.9
                ))

        # Check for visual shifts if pixel diff found regions
        if diff_boxes and not changes:
            changes.append(VisualChange(
                change_type="layout_shift",
                description=f"Detectada alteração de estilo ou layout em {len(diff_boxes)} regiões visuais.",
                confidence=0.8
            ))

        # Format summary report in Markdown
        summary_lines = [
            f"### Resumo da Comparação Visual e Estrutural",
            f"- **Regiões Visuais Alteradas**: {len(diff_boxes)} blocos destacados na imagem de diff.",
            f"- **Mudanças Estruturais Detectadas**: {len(changes)} itens.",
            "",
            "| Tipo | Descrição | Sugestão de Validação |",
            "|:----:|:----------|:----------------------|"
        ]

        for c in changes:
            assertion = f"`{c.suggested_assertion}`" if c.suggested_assertion else "-"
            summary_lines.append(f"| `{c.change_type}` | {c.description} | {assertion} |")

        return diff_image_path, changes, "\n".join(summary_lines)

    def _element_key(self, el: UIElement) -> str:
        if el.test_id:
            return f"testid:{el.test_id}"
        if el.element_id:
            return f"id:{el.element_id}"
        if el.name:
            return f"name:{el.name}"
        if el.text and len(el.text) < 40:
            return f"tag_text:{el.tag_name}:{el.text}"
        return f"loc:{el.tag_name}@{int(el.bbox.x // 50)}_{int(el.bbox.y // 50)}"

