# Test Planning Skill

Use this when turning requirements into an Android test plan.

Allowed actions:

- `launch_app`
- `tap`
- `input`
- `wait_visible`
- `assert_visible`
- `assert_text`
- `back`

Target rules:

- For element interactions, use intent-level target objects:
  `{"name": "login_button", "intent": "登录按钮"}`
- Do not output `locator`, `by`, `value`, `resource-id`, `xpath`, or `accessibility_id` unless supplied explicitly by context.
- Prefer `assert_text` for broad text assertions when no specific element target is known.

Planning rules:

- Keep steps in user-visible order.
- Add waits only when they express user-visible readiness.
- Avoid low-level Appium details.
