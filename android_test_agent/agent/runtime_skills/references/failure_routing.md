# Failure Routing Reference

Use this reference only when replanning after a failed run.

Failure routes:

- `locator_not_found`: refresh element context and resolve targets again.
- `timeout`: add conservative `wait_visible` before fragile interactions.
- `assertion`: revisit expected result and user intent before changing steps.
- `environment`: do not rewrite the test; Appium, ADB, app package, Activity, or device setup needs human attention.
- `unknown`: collect artifacts and make the smallest reasonable plan adjustment.

Do not respond to environment failures by changing DSL logic.
