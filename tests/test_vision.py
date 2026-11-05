"""Unit tests for visual inspection and Set-of-Marks annotator."""

import pytest
from pathlib import Path
from PIL import Image
from agent.core.models import UIElement, BoundingBox
from agent.vision.annotator import VisualAnnotator
from agent.vision.visual_differ import VisualDiffer


def test_visual_annotator_draws_badges(tmp_path):
    # Create synthetic test image
    img_path = tmp_path / "test_screen.png"
    img = Image.new("RGB", (400, 300), color=(240, 240, 240))
    img.save(img_path)

    elements = [
        UIElement(
            mark_id=1,
            tag_name="button",
            test_id="btn-login",
            text="Entrar",
            bbox=BoundingBox(x=50, y=50, width=100, height=35),
            selector_candidates=['css=[data-testid="btn-login"]']
        ),
        UIElement(
            mark_id=2,
            tag_name="input",
            element_id="username",
            placeholder="Digite seu nome",
            bbox=BoundingBox(x=50, y=100, width=200, height=30),
            selector_candidates=['id=username']
        )
    ]

    annotator = VisualAnnotator()
    out_img, summary = annotator.annotate(img_path, elements, tmp_path / "annotated.png")

    assert out_img.exists()
    assert "[1]" in summary
    assert "btn-login" in summary
    assert "[2]" in summary
    assert "username" in summary


def test_visual_differ_detects_changes(tmp_path):
    # Create two images with a difference
    img1_path = tmp_path / "v1.png"
    img1 = Image.new("RGB", (300, 300), color=(255, 255, 255))
    img1.save(img1_path)

    img2_path = tmp_path / "v2.png"
    img2 = Image.new("RGB", (300, 300), color=(255, 255, 255))
    # Draw a colored square in v2
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img2)
    draw.rectangle([50, 50, 150, 150], fill=(255, 0, 0))
    img2.save(img2_path)

    base_elements = [
        UIElement(
            mark_id=1,
            tag_name="button",
            test_id="btn-confirm",
            text="Confirmar",
            bbox=BoundingBox(x=10, y=10, width=80, height=30)
        )
    ]

    target_elements = [
        UIElement(
            mark_id=1,
            tag_name="button",
            test_id="btn-confirm",
            text="Confirmar Novo",
            bbox=BoundingBox(x=10, y=10, width=80, height=30),
            selector_candidates=['css=[data-testid="btn-confirm"]']
        ),
        UIElement(
            mark_id=2,
            tag_name="input",
            test_id="input-coupon",
            placeholder="Cupom",
            bbox=BoundingBox(x=50, y=50, width=100, height=30),
            selector_candidates=['css=[data-testid="input-coupon"]']
        )
    ]

    differ = VisualDiffer(diff_threshold=20, min_contour_area=50)
    diff_img, changes, summary = differ.compare(img1_path, img2_path, base_elements, target_elements, tmp_path)

    assert diff_img.exists()
    assert len(changes) >= 2
    change_types = [c.change_type for c in changes]
    assert "added" in change_types
    assert "modified" in change_types

