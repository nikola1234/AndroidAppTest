# Locator Candidate Scoring Reference

Use this reference only when choosing among multiple locator candidates.

Preferred source order when candidate scores are close:

1. `manual_mapping`: human-maintained and most trusted.
2. `element_memory`: previously successful locator.
3. `ui_hierarchy`: current screen XML or page source.

Candidate scoring dimensions:

1. Source trust: `manual_mapping` and verified `element_memory` usually beat raw `ui_hierarchy`.
2. Current-page uniqueness: a locator that matches exactly one node beats a locator type that is normally stable but duplicated now.
3. Match strength: names, labels, text, content-desc, resource names, and action role should all support the same target.
4. Selector specificity: combined selectors are stronger than single-attribute selectors when the combined attributes are stable.
5. Action fit: tap targets should be clickable/button-like; input targets should be editable; assertions should use stable visible markers.

Locator type guidance:

- `id`: strong when unique, weaker when repeated on the current screen.
- `android_uiautomator`: strong when combining stable native attributes, for example `resourceId + text`.
- `accessibility_id`: strong when content-desc is unique and semantically meaningful.
- `text`: acceptable for stable visible labels, weaker for dynamic or repeated text.
- `xpath`: fallback unless it targets stable attributes; avoid position-only hierarchy paths.

`android_uiautomator` examples:

```text
new UiSelector().resourceId("com.example:id/login").text("登录")
new UiSelector().className("android.widget.Button").textContains("登录")
```

Action-specific hints:

- `tap`: prefer clickable buttons or elements with button-like class/name.
- `long_press`: prefer clickable or long-clickable elements with matching label.
- `input` and `clear`: prefer editable text fields.
- `wait_visible`: prefer stable screen markers.
- `assert_visible`: prefer expected result text or stable title elements.
- `assert_checked` and `assert_selected`: prefer checkbox, radio, switch, tab, or selectable classes.
- `assert_enabled`: prefer interactive controls with stable id or label.
- `assert_text_equals` and `assert_text_contains`: prefer text-bearing elements with stable id, text, or content-desc.
- `wait_gone` and `assert_not_visible`: prefer stable transient markers such as loading indicators, dialogs, or error messages.
- `swipe`, `scroll`, `pinch`, and `zoom`: only resolve a `target` when the gesture is scoped to a specific container or zoomable area.
- `drag_and_drop`: resolve both `source` and `target` when the step uses element targets.

Never choose a locator outside the provided candidate list.
