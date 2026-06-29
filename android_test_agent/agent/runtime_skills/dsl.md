# Intent DSL Skill

Use this when converting a plan into the project DSL.

Required top-level fields:

- `name`
- `description`
- `steps`

Step rules:

- Each step must use one of the allowed action names.
- `input` requires `target` and `value`.
- `tap`, `wait_visible`, and `assert_visible` require `target`.
- `assert_text` requires `text`.

Intent target format:

```json
{"name": "username_field", "intent": "账号输入框"}
```

Never generate concrete locator fields at this stage. Locator resolution belongs to `ElementNode` and `LocatorResolver`.
