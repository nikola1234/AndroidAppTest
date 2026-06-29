# Locator Selection Skill

Use this only when choosing among provided locator candidates.

Rules:

- Choose one candidate from the provided candidate list.
- Return strict JSON: `{"index": 0}`.
- Do not invent or modify locators.
- Prefer sources in this order when scores are similar:
  1. `manual_mapping`
  2. `element_memory`
  3. `ui_hierarchy`
- Do not use a fixed locator-type order as the main decision rule.
- Score candidates by source trust, current-page uniqueness, match strength, selector specificity, and action fit.
- Prefer plain `id` only when it is unique on the current page or comes from trusted manual mapping/memory.
- Prefer `android_uiautomator` when it combines stable attributes such as `resourceId + text` or `resourceId + description`.
- Use `android_uiautomator` only with valid `new UiSelector()...` expressions from provided element attributes.
- Prefer clickable elements for `tap`.
- Prefer editable text fields for `input`.
- Prefer visible text-like elements for `assert_visible` and `wait_visible`.
