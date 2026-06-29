# Android Test Agent

一个 Android App 自动化测试 AI Agent 框架。核心思路是：

```text
测试用例/自然语言需求 -> Analyzer -> Planner -> DSL -> Element -> Codegen -> pytest/Appium -> Validator -> 按失败类型路由
```

LLM 不直接自由生成完整 Appium 脚本，而是先生成结构化 DSL，再由稳定的代码生成器输出 pytest/Appium 测试代码。

## 目录结构

```text
android_test_agent/
├── agent/
│   ├── core.py                  # Agent 编排流程
│   ├── config.py                # 环境配置
│   ├── graph.py                 # 状态图流程
│   ├── state.py                 # 共享状态定义
│   ├── nodes/                   # Analyzer / Planner / DSL / Element / Codegen / Executor / Validator / Retrier / WaitStrategy / Debug
│   ├── runtime_skills/           # 运行时 LLM prompt skills
│   └── skills/                  # MCP skill 适配预留层
├── executor/
│   ├── dsl_executor.py          # DSL 解释执行 / pytest 执行
│   ├── appium_executor.py       # Appium 执行封装
│   └── retry_policy.py          # 失败重试策略
├── dsl/
│   ├── schema.py                # DSL 校验
│   └── codegen.py               # DSL -> pytest/Appium 代码
├── llm/
│   ├── base.py                  # LLM 抽象接口
│   └── deepseek_client.py       # DeepSeek 客户端
├── tools/
│   ├── adb_tool.py              # ADB 命令
│   ├── appium_tool.py           # Appium server 检查
│   ├── ui_dump_tool.py          # uiautomator dump
│   ├── screenshot_tool.py       # 截图
│   └── logcat_tool.py           # logcat 采集
├── memory/
│   ├── case_memory.py           # 历史用例记忆
│   ├── element_memory.py        # 页面元素/locator 记忆
│   └── failure_memory.py        # 失败模式/修复记忆
└── main.py                      # python -m android_test_agent.main 入口

artifacts/
├── screenshots/                 # 执行截图
├── ui_dumps/                    # uiautomator XML
├── logcat/                      # Android logcat
├── appium_logs/                 # Appium server/client 日志
├── generated_code/              # 生成代码快照
└── traces/                      # 执行轨迹

generated/
├── dsl/                         # 生成的结构化测试 DSL
└── tests/                       # 生成的 pytest/Appium 测试代码

tests/
└── test_cases_example.yaml      # 示例测试用例输入
```

## 快速开始

安装依赖：

```bash
pip install -r requirements.txt
```

只生成测试代码，不执行设备测试：

```bash
python main.py
```

使用自定义测试用例：

```bash
python main.py --case-file tests/test_cases_example.yaml
```

默认使用模板代码生成器把 DSL 编译成 pytest/Appium 文件。如果要实验 LLM 直接生成 pytest 代码，可以打开可选 LLM Codegen：

```bash
python main.py --case-file tests/test_cases_example.yaml --llm-codegen
```

也可以通过环境变量打开：

```env
ATA_LLM_CODEGEN_ENABLED=true
```

LLM Codegen 生成后会先做 Python `compile()` 校验；校验失败时会把错误反馈给 LLM 修复一次。该模式需要配置 `DEEPSEEK_API_KEY`。

执行生成的 Appium 测试：

```bash
python main.py --case-file tests/test_cases_example.yaml --execute
```

按固定 checkpoint thread id 运行，便于把一次慢测试的中间状态归档到同一目录：

```bash
python main.py --case-file tests/test_cases_example.yaml --thread-id login-debug-001
```

如果希望在意图 DSL 生成后人工确认，再继续元素解析和代码生成：

```bash
python main.py --case-file tests/test_cases_example.yaml --review-intent-dsl
```

每个 LangGraph 节点执行后都会在 `reports/checkpoints/<thread-id>/` 下保存 JSON 快照，包含 `raw_case`、`intent_dsl`、`resolved_dsl`、`generated_files`、执行结果、失败类型和 artifacts 路径等排查信息。

也可以从某个 JSON checkpoint 继续执行：

```bash
python main.py --resume-from-checkpoint reports/checkpoints/login-debug-001/004_element.json
```

恢复时会从该 checkpoint 对应节点的下一步继续，例如 `004_element.json` 会从 `Codegen` 继续，`006_executor.json` 会从 `Validator` 继续。LangGraph 的持久化 checkpoint 会保存到 `reports/checkpoints/langgraph.sqlite`。

`ElementNode` 会并行采集可用元素来源：ADB UI dump、截图、人工元素映射、历史元素记忆；生成的 pytest 在真实执行时还会逐步读取当前 `driver.page_source` 作为运行时兜底。

Locator 当前支持 `id`、`android_uiautomator`、`accessibility_id`、`text` 和 `xpath`。其中 `android_uiautomator` 会映射到 Appium 的 `-android uiautomator`，适合用 `new UiSelector()` 组合 Android 原生属性。

运行时 LLM prompt 约束放在 `android_test_agent/agent/runtime_skills/*.md`。每次调用 DeepSeek 时会按 `system -> common -> 场景 skill -> task` 的顺序拼进 system prompt，用来约束模型不要编造 locator、只输出严格 JSON、遵守 DSL action 列表等。它们不是 Cursor 的 `.cursor/skills/*/SKILL.md`，而是本项目运行时使用的 prompt 资源。

更详细的长规则放在 `android_test_agent/agent/runtime_skills/references/`，按需渐进式加载。例如 Debug 回流时 Planner 会加载 `appium_patterns` 和 `failure_routing`，DSL 重试时加载 `dsl_schema`，locator 候选复杂时加载 `locator_candidate_scoring`。默认路径不会把所有 reference 一次性塞给 LLM。

结构化资源放在 `android_test_agent/agent/runtime_skills/resources/`，包括 `supported_actions.json`、`dsl_schema.json` 和 `locator_sources.json`。这些 JSON 会按需注入 prompt，其中 `supported_actions.json` 也被 DSL 校验代码读取，避免 prompt 规则和代码规则漂移。

执行前需要启动 Appium server，并配置真实包名/Activity：

```env
ANDROID_APP_PACKAGE=com.example
ANDROID_APP_ACTIVITY=.MainActivity
APPIUM_SERVER_URL=http://127.0.0.1:4723
```

如果要使用 DeepSeek：

```env
DEEPSEEK_API_KEY=your_api_key
DEEPSEEK_MODEL=deepseek-chat
```

默认会在 stderr 打印 DeepSeek 调用开始、结束、调用位置和耗时，便于排查卡顿。需要关闭时：

```env
ATA_LLM_LOG_CALLS=false
```

## DSL 示例

```yaml
name: login_success_example
steps:
  - action: launch_app
  - action: input
    target:
      name: username_field
      locator:
        by: id
        value: com.example:id/username
    value: test_user
  - action: tap
    target:
      name: login_button
      locator:
        by: android_uiautomator
        value: new UiSelector().resourceId("com.example:id/login").text("登录")
  - action: assert_visible
    target:
      name: home_page_title
      locator:
        by: text
        value: 首页
```

## 后续扩展

- 接入真实向量库保存历史用例、locator、失败修复方案。
- 在失败时自动采集 screenshot、UI XML、logcat 并写入 artifacts。
- 增加视觉断言和截图 diff。
- 将 `tools/` 暴露为 MCP skills。
- 增加多设备和 CI 执行支持。
# Xiaomi Android App Test Framework

这是一套可以直接拿来学习和扩展的 Android UI 自动化测试骨架，技术栈是：

- `Python`
- `pytest`
- `Appium 2`
- `UiAutomator2`

我把它按“小米真机先跑通，再替换成你的业务 App”的思路搭好了。当前默认示例使用 `ApiDemos`，因为它是 Appium 官方常用演示 App，选择器稳定，适合学习 Page Object、驱动封装、失败截图和可维护的用例结构。

## 项目结构

```text
.
|-- config/
|   `-- demo_example.yaml
|-- framework/
|   |-- core/
|   |   |-- base_page.py
|   |   |-- config.py
|   |   |-- driver_factory.py
|   |   `-- locators.py
|   `-- pages/
|       |-- api_demos_home_page_example.py
|       |-- controls_page.py
|       |-- light_theme_page.py
|       `-- views_page.py
|-- tests/
|   |-- conftest.py
|   `-- test_api_demos_smoke_example.py
|-- pytest.ini
`-- requirements.txt
```

## 你能学到什么

这套代码包含了实际项目里最常见的几块：

- 配置文件加载：把设备、包名、Activity、超时放进 YAML
- 驱动工厂：统一生成 Appium Driver
- BasePage：统一封装点击、输入、显式等待、滚动查找
- Page Object：页面对象拆分，测试不直接写底层定位
- pytest fixture：启动和关闭 Driver
- 失败自动留痕：测试失败后自动保存截图和 `page_source.xml`

## 环境准备

### 1. Python 环境

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. 安装 Appium 2 和 UiAutomator2 驱动

```powershell
npm install -g appium
appium driver install uiautomator2
appium
```

默认配置里 Appium Server 地址是：

```text
http://127.0.0.1:4723
```

### 3. 安卓 SDK / ADB

确保本机已经能执行：

```powershell
adb devices
```

### 4. 小米真机准备

小米/MIUI 真机通常要额外注意这些设置：

1. 打开“开发者选项”
2. 打开“USB 调试”
3. 如果系统里有“USB 调试（安全设置）”或“通过 USB 安装”，也一起打开
4. 首次连接电脑时，同意设备上的调试授权弹窗
5. 建议关闭被测 App 的电池优化，避免后台被系统杀掉
6. 测试时尽量保持屏幕常亮，避免锁屏影响会话

## 准备示例 App

默认示例使用 `ApiDemos`：

- `appPackage`: `io.appium.android.apis`
- `appActivity`: `io.appium.android.apis.ApiDemos`

你有两种方式：

1. 默认手动把 `ApiDemos-debug.apk` 安装到手机上，测试只通过 `appPackage/appActivity` 启动已安装 App
2. 如需让 Appium 启动前安装 APK，设置 `ANDROID_REINSTALL_APP=true`，并把 `ANDROID_APK_PATH` 指向本地 APK 或 `Apps` 目录

如果你已经有自己的业务 App，也可以直接把 `app_package`、`app_activity`、`app_path` 改成自己的。

## 配置文件说明

配置文件在 `config/demo_example.yaml`：

```yaml
appium:
  server_url: "http://127.0.0.1:4723"

android:
  platform_name: "Android"
  automation_name: "UiAutomator2"
  device_name: "Xiaomi Android"
  udid: ""
  app_package: "io.appium.android.apis"
  app_activity: "io.appium.android.apis.ApiDemos"
  app_path: ""
  no_reset: false
  full_reset: false
  auto_grant_permissions: true
  dont_stop_app_on_reset: true
  new_command_timeout: 180
  wait_activity: "*"
  ignore_hidden_api_policy_error: true
```

说明：

- `udid` 留空时，如果你只连了一台设备，Appium 一般可以自动选中
- `ANDROID_REINSTALL_APP=false` 时，表示启动已安装 App，不向 Appium 传 `app`
- `ANDROID_REINSTALL_APP=true` 时，才使用 `ANDROID_APK_PATH` 安装 APK
- `auto_grant_permissions: true` 对第一次安装测试 App 很有帮助
- `dont_stop_app_on_reset: true` 对一些小米机型更稳一些

你也可以用环境变量覆盖关键字段：

```powershell
$env:ANDROID_UDID="your-device-id"
$env:ANDROID_APP_PACKAGE="com.example.demo"
$env:ANDROID_APP_ACTIVITY=".MainActivity"
```

## 运行测试

### 直接运行全部 smoke 用例

```powershell
pytest -m smoke -s
```

### 指定配置文件运行

```powershell
pytest -m smoke -s --config config/demo_example.yaml
```

### 只跑单条用例

```powershell
pytest tests/test_api_demos_smoke_example.py::test_can_fill_light_theme_form -s
```

## 当前示例流程

示例用例走的是这条路径：

1. 打开 `ApiDemos`
2. 点击 `Views`
3. 打开 `Controls`
4. 点击 `1. Light Theme`
5. 输入文本
6. 勾选复选框
7. 选择单选按钮

这样可以让你看到：

- 如何写页面对象
- 如何做页面跳转
- 如何断言输入、勾选和选择状态

## 测试失败后看哪里

如果用例失败，框架会自动在 `artifacts/` 下保存：

- `screen.png`
- `page_source.xml`

排查定位问题时，这两个文件非常有用，特别适合处理小米手机上偶发弹窗、权限框、系统浮层等问题。

## 怎么改成你的业务 App

你只需要按这个顺序改：

1. 修改 `config/demo_example.yaml` 里的 `app_package`、`app_activity` 或 `app_path`
2. 在 `framework/pages/` 下新建你自己的页面对象
3. 优先用 `resource-id` 做定位，其次再考虑文本定位
4. 在 `tests/` 下新增业务测试用例

建议你开始时先做 3 个最小场景：

1. App 能正常启动
2. 登录页能输入账号密码并点击登录
3. 首页某个关键按钮或列表能正常打开

## 小米设备上的经验建议

- 文本定位在多语言环境下容易变，业务项目里优先用 `resource-id`
- MIUI 的权限弹窗、悬浮窗、系统优化经常影响稳定性，第一次跑时建议手动完整走一遍
- 如果会话经常断开，可以先确认 USB 线、ADB 连接和电源管理设置
- 某些小米机型首次装包慢，适当加大 `new_command_timeout`

## 下一步怎么继续学

如果你愿意，我下一步可以直接继续帮你做两件事中的任意一种：

1. 把这套框架改成“登录页 / 首页 / 个人中心”的业务化 Page Object 模板
2. 按你手上的某个真实 App，帮你把第一条自动化用例直接写出来
