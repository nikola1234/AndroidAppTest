# Appium Test Patterns Reference

Use this reference only for complex planning or replanning.

Stable UI automation patterns:

- Launch the app before interacting with elements.
- Wait for a visible screen marker before tapping elements on a newly opened page.
- Prefer one assertion that proves the user-visible outcome.
- Avoid redundant waits when the next action already waits for its target.
- Do not encode sleep durations in DSL unless no visible readiness marker exists.
- Prefer business-visible target names:
  - `username_field`
  - `password_field`
  - `login_button`
  - `home_page_title`

Keep the DSL short enough for a human reviewer to understand.
