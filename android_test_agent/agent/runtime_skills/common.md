# Common Android Test Agent Rules

- Return strict JSON when the caller asks for JSON. Do not wrap JSON in markdown.
- Do not invent Android resource ids, XPath, accessibility ids, package names, or Activity names.
- Treat user test cases as intent, not executable Appium code.
- Keep generated outputs deterministic and minimal.
- Prefer explicit missing information over hallucinated details.
- If a concrete locator is not present in the supplied context, use an intent-level target with `name` and `intent`.
