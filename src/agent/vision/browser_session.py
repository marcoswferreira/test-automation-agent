"""Browser inspection session using Playwright to extract DOM elements, screenshots, and accessibility metadata."""

import os
from pathlib import Path
from typing import List, Tuple
from playwright.sync_api import sync_playwright

from agent.core.models import UIElement, BoundingBox


class BrowserInspector:
    def __init__(self, headless: bool = True, viewport_width: int = 1280, viewport_height: int = 800):
        self.headless = headless
        self.viewport = {"width": viewport_width, "height": viewport_height}

    def inspect_page(self, url: str, output_dir: Path, filename_prefix: str = "page") -> Tuple[Path, List[UIElement], str]:
        """Navigates to URL, captures full screenshot and extracts interactive elements."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = output_dir / f"{filename_prefix}_screenshot.png"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(viewport=self.viewport)
            page = context.new_page()

            # Navigate to URL
            page.goto(url, wait_until="load", timeout=30000)
            page.wait_for_timeout(1000)  # Allow JS animations / DOM settlement

            page_title = page.title()

            # Capture high-res screenshot
            page.screenshot(path=str(screenshot_path), full_page=True)

            # JavaScript evaluation to find interactive elements and bounding boxes
            raw_elements = page.evaluate("""() => {
                const selectors = [
                    'button', 'a[href]', 'input', 'select', 'textarea',
                    '[role="button"]', '[role="link"]', '[role="checkbox"]', '[role="option"]',
                    '[data-testid]', 'h1', 'h2', 'h3',
                    '.promo-banner', '.status-box', '.product-card', '.modal-overlay'
                ];
                
                const elements = Array.from(document.querySelectorAll(selectors.join(', ')));
                const results = [];
                let markId = 1;

                elements.forEach(el => {
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    
                    // Filter invisible or zero-dimension elements
                    if (rect.width <= 0 || rect.height <= 0 || style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
                        return;
                    }

                    // Extract attributes
                    const tag = el.tagName.toLowerCase();
                    const testId = el.getAttribute('data-testid') || '';
                    const id = el.id || '';
                    const name = el.getAttribute('name') || '';
                    const role = el.getAttribute('role') || '';
                    const text = (el.innerText || el.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 80);
                    const placeholder = el.getAttribute('placeholder') || '';
                    const type = el.getAttribute('type') || '';

                    // Generate candidate locators
                    const candidates = [];
                    if (testId) {
                        candidates.push(`css=[data-testid="${testId}"]`);
                    }
                    if (id) {
                        candidates.push(`id=${id}`);
                    }
                    if (name) {
                        candidates.push(`css=${tag}[name="${name}"]`);
                    }
                    if (['button', 'a'].includes(tag) && text && text.length < 30) {
                        candidates.push(`text="${text}"`);
                    }
                    if (placeholder) {
                        candidates.push(`css=input[placeholder="${placeholder}"]`);
                    }
                    if (candidates.length === 0) {
                        if (el.className && typeof el.className === 'string') {
                            const firstClass = el.className.trim().split(' ')[0];
                            if (firstClass) candidates.push(`css=${tag}.${firstClass}`);
                        }
                        candidates.push(`css=${tag}`);
                    }

                    results.push({
                        mark_id: markId++,
                        tag_name: tag,
                        element_id: id || null,
                        test_id: testId || null,
                        name: name || null,
                        role: role || null,
                        text: text || null,
                        placeholder: placeholder || null,
                        bbox: {
                            x: Math.round(rect.x + window.scrollX),
                            y: Math.round(rect.y + window.scrollY),
                            width: Math.round(rect.width),
                            height: Math.round(rect.height)
                        },
                        selector_candidates: candidates,
                        attributes: {
                            type: type,
                            classes: el.className || ''
                        }
                    });
                });

                return results;
            }""")

            browser.close()

        elements = [UIElement(**item) for item in raw_elements]
        return screenshot_path, elements, page_title

