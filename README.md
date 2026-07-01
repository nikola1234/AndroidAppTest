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
│   ├── capabilities.py          # Appium capabilities 构建
│   ├── checkpoint.py            # 本地 JSON checkpoint
│   ├── core.py                  # Agent 编排流程
│   ├── config.py                # 环境配置
│   ├── graph.py                 # 状态图流程
│   ├── runtime_resources.py     # 结构化 runtime JSON 资源加载
│   ├── runtime_skills.py        # LLM prompt skill 加载
│   ├── state.py                 # 共享状态定义
│   ├── nodes/                   # Analyzer / Planner / DSL / Element / Codegen / Executor / Validator / FailureKnowledge / Retrier / Debug
│   ├── runtime_skills/           # 运行时 LLM prompt skills
│   └── skills/                  # MCP skill 适配预留层
├── executor/
│   ├── dsl_executor.py          # DSL 解释执行 / pytest 执行
│   ├── appium_executor.py       # Appium 执行封装
│   └── retry_policy.py          # 失败重试策略
├── dsl/
│   ├── generated_registry.py    # 生成文件登记和旧产物清理
│   ├── locator_resolver.py      # intent target -> Appium locator
│   ├── schema.py                # DSL 校验
│   ├── action_runtime.py        # DSL action 运行时
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
│   ├── base.py                  # memory 抽象接口
│   ├── vector_store.py          # 本地 JSON 存储和简单检索
│   ├── case_memory.py           # 历史用例记忆
│   ├── element_memory.py        # 页面元素/locator 记忆
│   ├── failure_memory.py        # 失败模式/修复记忆
│   └── retriever.py             # 多 memory 聚合检索预留
└── main.py                      # python -m android_test_agent.main 入口

artifacts/
├── screenshots/                 # 执行截图
├── ui_dumps/                    # uiautomator XML
├── logcat/                      # Android logcat
├── appium_logs/                 # Appium server/client 日志
├── locator_failures/            # locator 失败现场
├── generated_code/              # 预留生成代码快照目录
└── traces/                      # 执行轨迹

generated/
├── dsl/                         # 生成的结构化测试 DSL
├── tests/                       # 生成的 pytest/Appium 测试代码
└── .generated_cases.json        # 源用例到生成文件的登记表

tests/
├── test_cases_example.yaml      # 示例测试用例输入
├── ApiDemos/*.yaml              # ApiDemos 回归输入用例
├── test_dsl_actions.py          # DSL/codegen 单元测试
└── test_failure_knowledge.py    # 失败知识库单元测试

reports/
├── checkpoints/                 # LangGraph / JSON checkpoint
└── reviews/                     # 人工审核 DSL 文件

knowledge/
├── elements/                    # locator 记忆
├── failures/                    # 失败模式和修复方案
└── cases/                       # 用例记忆预留

clean_runtime_files.py           # 清理 generated/reports/artifacts/cache
PROJECT_STRUCTURE.md             # 更完整的目录和流程说明
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

如果 review 时拒绝了生成结果，可以先修改 `reports/reviews/*_intent_dsl.yaml`，再从 DSL checkpoint 继续：

```bash
python main.py --resume-from-checkpoint reports/checkpoints/<thread-id>/003_dsl.json --approved-intent-dsl reports/reviews/<case>_intent_dsl.yaml
```

每个 LangGraph 节点执行后都会在 `reports/checkpoints/<thread-id>/` 下保存 JSON 快照，包含 `raw_case`、`intent_dsl`、`resolved_dsl`、`generated_files`、执行结果、失败类型和 artifacts 路径等排查信息。

也可以从某个 JSON checkpoint 继续执行：

```bash
python main.py --resume-from-checkpoint reports/checkpoints/login-debug-001/004_element.json
```

恢复时会从该 checkpoint 对应节点的下一步继续，例如 `004_element.json` 会从 `Codegen` 继续，`006_executor.json` 会从 `Validator` 继续。LangGraph 的持久化 checkpoint 会保存到 `reports/checkpoints/langgraph.sqlite`。

`ElementNode` 会并行采集可用元素来源：ADB UI dump、截图、人工元素映射、历史元素记忆；生成的 pytest 在真实执行时还会逐步读取当前 `driver.page_source` 作为运行时兜底。

Locator 当前支持 `id`、`android_uiautomator`、`accessibility_id`、`text` 和 `xpath`。其中 `android_uiautomator` 会映射到 Appium 的 `-android uiautomator`，适合用 `new UiSelector()` 组合 Android 原生属性。

默认 codegen 生成的 pytest 会调用 `android_test_agent/dsl/action_runtime.py`，因此生成 pytest 和直接解释执行 DSL 使用同一套 action 语义。当前 DSL action 覆盖基础交互、手势、状态断言、App 生命周期和高级 W3C actions，例如 `tap`、`input`、`scroll_to_text`、`long_press`、`swipe`、`scroll`、`drag_and_drop`、`clear`、`press_key`、`assert_checked`、`assert_text_contains`、`wait_gone`、`tap_coordinates`、`background_app`、`activate_app`、`terminate_app`、`change_orientation`、`accept_permission`、`dismiss_dialog`、`pinch`、`zoom` 和 `w3c_actions`。完整列表以 `android_test_agent/agent/runtime_skills/resources/supported_actions.json` 为准。

失败后会先由 `ValidatorNode` 提取 `failure_type`、异常类、错误签名、失败 action/target 和稳定 fingerprint，再由 `FailureArtifactsNode` 保存截图、UI dump、logcat、Appium 状态和 trace。随后 `FailureKnowledgeNode` 会把失败模式写入 `knowledge/failures/failure_memory.json`，并把历史相似失败的修复建议合并回本次 `validation_result.suggestions`。如果 retry 后测试通过，对应 failure memory 会标记为 `verified`。

运行时 LLM prompt 约束放在 `android_test_agent/agent/runtime_skills/*.md`。每次调用 DeepSeek 时会按 `system -> common -> 场景 skill -> task` 的顺序拼进 system prompt，用来约束模型不要编造 locator、只输出严格 JSON、遵守 DSL action 列表等。它们不是 Cursor 的 `.cursor/skills/*/SKILL.md`，而是本项目运行时使用的 prompt 资源。

更详细的长规则放在 `android_test_agent/agent/runtime_skills/references/`，按需渐进式加载。例如 Debug 回流时 Planner 会加载 `appium_patterns` 和 `failure_routing`，DSL 重试时加载 `dsl_schema`，locator 候选复杂时加载 `locator_candidate_scoring`。默认路径不会把所有 reference 一次性塞给 LLM。

结构化资源放在 `android_test_agent/agent/runtime_skills/resources/`，包括 `supported_actions.json`、`dsl_schema.json` 和 `locator_sources.json`。这些 JSON 会按需注入 prompt，其中 `supported_actions.json` 也被 DSL 校验代码读取，避免 prompt 规则和代码规则漂移。

执行前需要配置真实包名/Activity 和 Appium 地址；手动启动 Appium 是可选的，`--execute` 会先探测并可托管启动本机 Appium：

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

## 执行和 Appium

`--execute` 会通过 `PytestExecutor` 执行生成的 pytest。执行前会先访问 `APPIUM_SERVER_URL/status`：

- 如果已有 Appium server 可用，直接复用。
- 如果不可用，会尝试托管启动本机 `appium` 命令。
- 托管启动的 Appium 日志会写入 `artifacts/appium_logs/`，并记录在 `execution_result.appium_server`。

也可以先手动启动 Appium：

```powershell
npm install -g appium
appium driver install uiautomator2
appium
```

生成后的 pytest 可以脱离 Agent 单独重跑：

```powershell
python -m pytest generated/tests/test_<name>.py -q
```

如需让 Appium 启动前安装 APK：

```powershell
python main.py --case-file tests/ApiDemos/01_app_launch_home_categories.yaml --execute --reinstall-app
```

或使用环境变量：

```env
ANDROID_REINSTALL_APP=true
ANDROID_APK_PATH=Apps/ApiDemos-debug.apk
```

`ANDROID_APK_PATH` 可以指向单个 APK，也可以指向只包含一个 APK 的目录。

## 测试和回归

`tests/` 有两类文件：

- `tests/test_cases_example.yaml` 和 `tests/ApiDemos/*.yaml` 是 Agent 输入用例。
- `tests/test_dsl_actions.py` 和 `tests/test_failure_knowledge.py` 是框架自身的 pytest 单元测试。

运行框架单元测试：

```powershell
python -m pytest tests/test_dsl_actions.py tests/test_failure_knowledge.py -q
```

批量生成 ApiDemos 用例：

```powershell
Get-ChildItem tests\ApiDemos\*.yaml | ForEach-Object {
  python main.py --case-file $_.FullName
}
```

## 失败排查

失败时主要看这些位置：

- `artifacts/traces/*.json`：执行结果、validation、artifact 路径汇总。
- `artifacts/screenshots/*.png`：失败截图。
- `artifacts/ui_dumps/*.xml`：失败时 UI 层级。
- `artifacts/logcat/*.txt`：Android logcat。
- `artifacts/appium_logs/`：Appium server/status/process 日志。
- `artifacts/locator_failures/`：运行时 locator 解析或元素查找失败现场。
- `reports/checkpoints/<thread-id>/*.json`：每个 LangGraph 节点的状态快照。
- `knowledge/failures/failure_memory.json`：失败 fingerprint、历史建议、verified 解决方案。

`ValidatorNode` 会把堆栈提取成稳定字段，包括 `failure_type`、`exception_class`、`error_signature`、`failing_action`、`failing_target` 和 `fingerprint`。`FailureKnowledgeNode` 会用这些字段检索本地失败知识库，并把历史建议合并回本次 retry/debug。

## 人工审核

`--review-intent-dsl` 会在 intent DSL 生成后暂停。如果在非交互环境中运行，审核无法继续时会抛出 `HumanReviewRejected`，CLI 以 exit code `2` 结束。可以修改 `reports/reviews/*_intent_dsl.yaml` 后用下面命令恢复：

```powershell
python main.py --resume-from-checkpoint reports/checkpoints/<thread-id>/003_dsl.json --approved-intent-dsl reports/reviews/<case>_intent_dsl.yaml
```

## 清理运行时产物

清理 `generated/`、`reports/`、`artifacts/` 和 Python cache：

```powershell
python clean_runtime_files.py
```

只预览不删除：

```powershell
python clean_runtime_files.py --dry-run
```

默认不会删除 `knowledge/*.json`。如果要连本地记忆一起清理：

```powershell
python clean_runtime_files.py --include-knowledge
```

## 当前边界和后续扩展

- `CaseMemory` 和 `KnowledgeRetriever` 已实现接口，但还没有接入 Agent 主流程。
- `artifacts/generated_code/` 是预留目录，当前主流程不会写入。
- 可以接入真实向量库替换当前 JSON memory，实现更强的历史用例、locator、失败修复方案检索。
- 可以继续增加视觉断言、截图 diff、多设备和 CI 执行支持。
- `agent/skills/` 目前是 MCP adapter 预留层，尚不是主流程重点。
