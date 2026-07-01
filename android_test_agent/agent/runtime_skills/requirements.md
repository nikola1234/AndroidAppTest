# Requirements Extraction Skill

Use this when converting natural-language Android test cases into normalized requirements.

Output fields:

- `name`: short stable test name from the user intent.
- `description`: concise human-readable goal.
- `preconditions`: list of setup assumptions.
- `expected_result`: observable result, not implementation detail.

Rules:

- Preserve test data explicitly provided by the user, such as usernames, passwords, or expected text.
- Do not add UI locator details.
- Do not add Appium actions.
- If the user describes multiple scenarios, keep the primary scenario and mention the rest in `description`.
