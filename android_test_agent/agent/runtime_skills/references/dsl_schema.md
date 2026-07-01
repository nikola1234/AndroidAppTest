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
{"action": "scroll_to_text", "text": "Views"}
{"action": "back"}
{"action": "long_press", "target": {"name": "menu_item", "intent": "菜单项"}, "duration_ms": 1000}
{"action": "swipe", "direction": "up", "percent": 0.75}
{"action": "scroll", "target": {"name": "list", "intent": "列表容器"}, "direction": "down"}
{"action": "drag_and_drop", "source": {"name": "source_item", "intent": "源项目"}, "target": {"name": "destination", "intent": "目标区域"}}
{"action": "clear", "target": {"name": "search_field", "intent": "搜索输入框"}}
{"action": "press_key", "key": "ENTER"}
{"action": "hide_keyboard"}
{"action": "assert_checked", "target": {"name": "checkbox", "intent": "复选框"}}
{"action": "assert_enabled", "target": {"name": "submit_button", "intent": "提交按钮"}}
{"action": "assert_selected", "target": {"name": "tab", "intent": "当前 tab"}}
{"action": "assert_text_equals", "target": {"name": "title", "intent": "标题"}, "text": "首页"}
{"action": "assert_text_contains", "target": {"name": "message", "intent": "提示文案"}, "text": "成功"}
{"action": "wait_gone", "target": {"name": "loading", "intent": "加载中提示"}}
{"action": "assert_not_visible", "target": {"name": "error_message", "intent": "错误提示"}}
{"action": "tap_coordinates", "x": 100, "y": 200}
{"action": "background_app", "seconds": 1}
{"action": "activate_app"}
{"action": "terminate_app"}
{"action": "change_orientation", "orientation": "LANDSCAPE"}
{"action": "accept_permission"}
{"action": "dismiss_dialog"}
{"action": "pinch", "target": {"name": "map", "intent": "地图区域"}, "percent": 0.5}
{"action": "zoom", "area": {"x": 0, "y": 200, "width": 1080, "height": 1200}, "percent": 0.5}
{"action": "w3c_actions", "actions": []}
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
