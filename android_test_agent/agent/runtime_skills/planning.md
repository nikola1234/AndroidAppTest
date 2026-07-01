# Test Planning Skill

Use this when turning requirements into an Android test plan.

Allowed actions:

- `launch_app`
- `tap`
- `input`
- `wait_visible`
- `assert_visible`
- `assert_text`
- `scroll_to_text`
- `back`
- `long_press`
- `swipe`
- `scroll`
- `drag_and_drop`
- `clear`
- `press_key`
- `hide_keyboard`
- `assert_checked`
- `assert_enabled`
- `assert_selected`
- `assert_text_equals`
- `assert_text_contains`
- `wait_gone`
- `assert_not_visible`
- `tap_coordinates`
- `background_app`
- `activate_app`
- `terminate_app`
- `change_orientation`
- `accept_permission`
- `dismiss_dialog`
- `pinch`
- `zoom`
- `w3c_actions`

Target rules:

- For element interactions, use intent-level target objects:
  `{"name": "login_button", "intent": "登录按钮"}`
- For drag and drop, use `source` and `target` intent-level objects when the source and destination are UI elements.
- For generic gestures, prefer `direction` and `percent` over raw coordinates unless the test case explicitly requires coordinates.
- Do not output `locator`, `by`, `value`, `resource-id`, `xpath`, or `accessibility_id` unless supplied explicitly by context.
- Prefer `assert_text` for broad text assertions when no specific element target is known.
- Prefer specific assertions (`assert_checked`, `assert_enabled`, `assert_selected`, `assert_text_equals`, `assert_text_contains`) when the expected result names a concrete element state.

Planning rules:

- Keep steps in user-visible order.
- Add waits only when they express user-visible readiness.
- Avoid low-level Appium details. Use `w3c_actions` only for multi-finger or advanced gestures that cannot be expressed with `swipe`, `scroll`, `drag_and_drop`, `pinch`, or `zoom`.
