# Intent DSL Skill

Use this when converting a plan into the project DSL.

Required top-level fields:

- `name`
- `description`
- `steps`

Step rules:

- Each step must use one of the allowed action names.
- `input` requires `target` and `value`.
- Element actions require intent-level target objects: `tap`, `wait_visible`, `assert_visible`, `long_press`, `clear`, `assert_checked`, `assert_enabled`, `assert_selected`, `assert_text_equals`, `assert_text_contains`, `wait_gone`, and `assert_not_visible`.
- `assert_text`, `scroll_to_text`, `assert_text_equals`, and `assert_text_contains` require `text`.
- `swipe` and `scroll` require either `direction` (`up`, `down`, `left`, `right`) or `start`/`end` coordinates. They may include an optional `target` container.
- `drag_and_drop` requires either `source` and `target` intent targets, or `start`/`end` coordinates.
- `tap_coordinates` requires `x` and `y`.
- `press_key` requires `key`, for example `ENTER`, `HOME`, `BACK`, or a numeric keycode.
- `change_orientation` requires `orientation` (`PORTRAIT` or `LANDSCAPE`).
- `pinch` and `zoom` require either `target` or `area`.
- `w3c_actions` requires an `actions` array using the W3C actions payload shape.

Intent target format:

```json
{"name": "username_field", "intent": "账号输入框"}
```

Never generate concrete locator fields at this stage. Locator resolution belongs to `ElementNode` and `LocatorResolver`.
