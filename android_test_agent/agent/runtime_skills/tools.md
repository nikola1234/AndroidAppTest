# Runtime Tool Context

The model cannot directly call tools unless the caller explicitly provides a tool-calling loop.

Available runtime sources in this project:

- `config/elements.yaml`: human-maintained element mappings.
- `knowledge/elements/element_memory.json`: successful historical locator memory.
- ADB `uiautomator dump`: current UI hierarchy XML, collected by `ElementNode`.
- screenshot capture: visual artifact for debugging and future OCR/VLM work.
- Appium `driver.page_source`: runtime fallback inside generated pytest tests.

When no concrete source provides a locator, keep the target intent-level and let runtime resolution or human review handle it.
