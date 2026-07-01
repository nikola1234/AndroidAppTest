# LLM Pytest Codegen Skill

Use this only when generating pytest/Appium Python code from a resolved DSL.

Rules:

- Generate a complete Python pytest file.
- Return only Python code, or a JSON object with a single `code` string. Do not explain.
- Preserve the supplied DSL as `TEST_DSL`.
- Do not invent locators, package names, activities, credentials, or test steps.
- Use the supplied `CAPABILITIES`, Appium server URL, wait settings, and DSL.
- Use `LocatorResolver` at runtime so generated tests can resolve intent targets with current `driver.page_source`.
- Preserve locator candidate fallback behavior when `locator_candidates` is present.
- Save useful failure artifacts when locator resolution or element lookup fails.
- Support these locator types: `id`, `android_uiautomator`, `accessibility_id`, `text`, `xpath`.
- Support every action listed in the supplied `supported_actions` resource. Prefer the project `AndroidDslActionRuntime` helper when available so generated code stays consistent with deterministic codegen.
- Keep generated code deterministic and readable.
- The code must pass Python `compile()` before it can be executed.

Required generated structure:

- Imports for `pytest`, Appium `webdriver`, `UiAutomator2Options`, Selenium `By`, and `WebDriverWait`.
- `TEST_DSL`, `APPIUM_SERVER_URL`, `CAPABILITIES`, `EXPLICIT_WAIT_SECONDS`, and `IMPLICIT_WAIT_SECONDS` constants.
- A pytest `driver` fixture.
- Helper functions to resolve locators and wait for elements.
- A `run_step(driver, step)` function.
- One pytest test function named from the DSL test name.
