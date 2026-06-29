# DSL Schema Reference

Use this reference only when generating, repairing, or debugging DSL shape.

Top-level object:

```json
{
  "name": "test_name",
  "description": "human readable description",
  "steps": []
}
```

Allowed step forms:

```json
{"action": "launch_app"}
{"action": "tap", "target": {"name": "login_button", "intent": "登录按钮"}}
{"action": "input", "target": {"name": "username_field", "intent": "账号输入框"}, "value": "test_user"}
{"action": "wait_visible", "target": {"name": "home_title", "intent": "首页标题"}}
{"action": "assert_visible", "target": {"name": "home_title", "intent": "首页标题"}}
{"action": "assert_text", "text": "首页"}
{"action": "back"}
```

Invalid at intent stage:

```json
{"locator": {"by": "id", "value": "com.example:id/foo"}}
```

Concrete locators are resolved after intent DSL generation.

Executable DSL locator types:

```json
{"by": "id", "value": "com.example:id/login"}
{"by": "android_uiautomator", "value": "new UiSelector().resourceId(\"com.example:id/login\").text(\"登录\")"}
{"by": "accessibility_id", "value": "login"}
{"by": "text", "value": "首页"}
{"by": "xpath", "value": "//*[@text='首页']"}
```
