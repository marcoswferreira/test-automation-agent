"""Set-of-Marks (SoM) visual annotator for UI elements."""

from pathlib import Path
from typing import List, Tuple
from PIL import Image, ImageDraw, ImageFont

from agent.core.models import UIElement


class VisualAnnotator:
    def __init__(self, badge_color: str = "#ef4444", text_color: str = "#ffffff", outline_color: str = "#ef4444"):
        self.badge_color = badge_color
        self.text_color = text_color
        self.outline_color = outline_color

    def annotate(self, screenshot_path: Path, elements: List[UIElement], output_path: Path) -> Tuple[Path, str]:
        """Draws bounding boxes and numbered marks onto screenshot and produces a Markdown summary."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with Image.open(screenshot_path) as img:
            annotated_img = img.convert("RGBA")
            overlay = Image.new("RGBA", annotated_img.size, (255, 255, 255, 0))
            draw = ImageDraw.Draw(overlay)

            # Try to load default font
            try:
                font = ImageFont.load_default()
            except Exception:
                font = None

            for el in elements:
                bbox = el.bbox
                x0 = bbox.x
                y0 = bbox.y
                x1 = bbox.x + bbox.width
                y1 = bbox.y + bbox.height

                # Draw bounding box outline
                draw.rectangle([x0, y0, x1, y1], outline=self.outline_color, width=2)

                # Draw mark badge
                badge_text = f"[{el.mark_id}]"
                badge_w = len(badge_text) * 7 + 6
                badge_h = 16
                badge_x0 = max(0, x0)
                badge_y0 = max(0, y0 - badge_h)

                draw.rectangle([badge_x0, badge_y0, badge_x0 + badge_w, badge_y0 + badge_h], fill=self.badge_color)
                draw.text((badge_x0 + 3, badge_y0 + 2), badge_text, fill=self.text_color, font=font)

            final_image = Image.alpha_composite(annotated_img, overlay).convert("RGB")
            final_image.save(output_path, "PNG")

        # Generate elements text summary
        summary_lines = [
            "| Mark | Tag | data-testid | id / name | Text / Placeholder | Recommended Locator |",
            "|:----:|:---:|:-----------:|:---------:|:-------------------:|:--------------------|"
        ]

        for el in elements:
            mark = f"[{el.mark_id}]"
            tag = el.tag_name
            testid = el.test_id or "-"
            idname = el.element_id or el.name or "-"
            content = (el.text or el.placeholder or "-")[:35].replace("|", "/")
            rec_selector = el.selector_candidates[0] if el.selector_candidates else f"css={el.tag_name}"
            summary_lines.append(f"| {mark} | `{tag}` | `{testid}` | `{idname}` | {content} | `{rec_selector}` |")

        return output_path, "\n".join(summary_lines)

