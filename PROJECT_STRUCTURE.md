# Android Test Agent 项目结构说明

这份文档用来解释当前工程里每个目录和关键文件的作用。你可以先把这个项目理解成一个“Android UI 自动化测试生成与执行 Agent”：

```text
自然语言测试用例
  -> Analyzer 分析需求
  -> Planner 生成测试计划
  -> DslNode 生成意图级 DSL
  -> ElementNode 解析页面元素和 locator
  -> CodegenNode 生成 pytest/Appium 代码
  -> Executor 执行或 dry-run
  -> Validator 判断结果
  -> FailureArtifacts/FailureKnowledge 留痕和查历史方案
  -> 按失败类型路由
```

核心原则是：LLM 不直接自由生成完整 Appium 脚本，而是先生成结构化 DSL，再由固定的代码生成器产出 pytest/Appium 代码。这样可以减少 LLM 乱写 locator、乱写脚本的问题。

## 顶层目录

### `android_test_agent/`

核心 Python 包。Agent 编排、LangGraph 流程、DSL、locator 解析、代码生成、执行器、工具、记忆和 LLM 客户端都在这里。

这是当前项目最重要的目录。

### `config/`

人工配置目录。

目前主要有：

- `elements_example.yaml`：页面元素映射示例。

实际运行时，如果你想手动提供页面元素映射，需要复制一份：

```text
config/elements_example.yaml -> config/elements.yaml
```

`LocatorResolver` 默认读取的是 `config/elements.yaml`，不是 example 文件。

### `tests/`

这里有两类文件。

Agent 输入用例：

- `test_cases_example.yaml`：自然语言测试用例示例。
- `ApiDemos/*.yaml`：ApiDemos 回归输入用例集，部分用例会在文本里声明 `appPackage` / `appActivity`。

框架单元测试：

- `test_dsl_actions.py`：DSL action、schema 和 codegen 编译测试。
- `test_failure_knowledge.py`：失败 fingerprint、FailureMemory 和 FailureKnowledgeNode 测试。

注意：Agent 输入 YAML 不是最终要执行的 pytest；最终 pytest 会生成到 `generated/tests/`。

### `generated/`

Agent 生成产物目录。

通常会包含：

- `generated/dsl/`：生成出来的 DSL YAML。
- `generated/tests/`：生成出来的 pytest/Appium 测试代码。
- `generated/.generated_cases.json`：源用例和生成文件的登记表。

这些文件是由 Agent 生成的，可以删除后重新生成。

### `artifacts/`

设备执行和排查问题时产生的留痕目录。

常见内容包括：

- `screenshots/`：截图。
- `ui_dumps/`：ADB `uiautomator dump` 生成的 XML。
- `logcat/`：Android logcat。
- `locator_failures/`：locator 解析或执行失败时保存的 XML、JSON、PNG。
- `appium_logs/`：Appium server/status/process 日志。
- `traces/`：失败 trace JSON。
- `generated_code/`：预留目录，当前主流程不会主动写入。

### `reports/`

Agent 运行报告和 checkpoint 目录。

常见内容包括：

- `reports/checkpoints/<thread-id>/`：每个 LangGraph 节点执行后的 JSON 状态快照。
- `reports/checkpoints/langgraph.sqlite`：LangGraph 持久化 checkpoint 数据库。
- `reports/reviews/`：开启 human-in-the-loop 后，给人审核的 intent DSL 文件。

### `knowledge/`

运行时知识库目录。

这里保存 Agent 在执行中积累的经验，例如：

- `knowledge/elements/element_memory.json`：成功使用过的元素 locator。
- `knowledge/cases/case_memory.json`：历史用例记忆。
- `knowledge/failures/failure_memory.json`：失败模式和修复经验。

当前实现用本地 JSON 存储，后续可以替换成真正的向量数据库。

### `main.py`

项目根入口。它通常只是薄封装，最终调用 `android_test_agent/main.py`。

### `requirements.txt`

Python 依赖列表，包括 Appium、pytest、LangGraph、DeepSeek 客户端相关依赖等。

### `clean_runtime_files.py`

运行时产物清理脚本。

默认清理：

- `generated/`
- `reports/`
- `artifacts/`
- Python cache，例如 `__pycache__` 和 `.pytest_cache`

常用命令：

```bash
python clean_runtime_files.py --dry-run
python clean_runtime_files.py
python clean_runtime_files.py --include-knowledge
```

默认不会删除 `knowledge/*.json`，只有加 `--include-knowledge` 才会清理本地记忆。

### `.env`

环境变量配置文件。DeepSeek API Key、App 包名、Activity、Appium server 地址等放这里。

常见配置：

```env
DEEPSEEK_API_KEY=your_key
DEEPSEEK_MODEL=deepseek-chat
ANDROID_APP_PACKAGE=com.example
ANDROID_APP_ACTIVITY=.MainActivity
APPIUM_SERVER_URL=http://127.0.0.1:4723
```

## `android_test_agent/` 目录

### `android_test_agent/main.py`

CLI 入口。

它负责：

- 读取命令行参数。
- 加载 `.env`。
- 创建 `AndroidTestConfig`。
- 创建 `AndroidTestAgent`。
- 读取自然语言测试用例。
- 执行 Agent。
- 输出最终 JSON 摘要。

常用命令：

```bash
python main.py
python main.py --case-file tests/test_cases_example.yaml
python main.py --case-file tests/test_cases_example.yaml --execute
python main.py --review-intent-dsl
python main.py --resume-from-checkpoint reports/checkpoints/<thread-id>/004_element.json
```

默认情况下，如果不加 `--execute`，只生成测试代码，不真正跑 Appium 测试。

### `android_test_agent/agent/`

Agent 编排核心目录。

这里负责“流程怎么走”，也就是哪些节点先执行，失败后回到哪里，checkpoint 怎么保存。

#### `agent/core.py`

`AndroidTestAgent` 的组装入口。

它会创建：

- AnalyzerNode
- PlannerNode
- DslNode
- HumanReviewNode
- ElementNode
- CodegenNode
- ExecutorNode
- ValidatorNode
- FailureArtifactsNode
- FailureKnowledgeNode
- RetrierNode
- WaitStrategyNode
- DebugNode
- LlmCodegenNode（开启 LLM codegen 时替代默认 CodegenNode）
- AgentGraph

你可以把它理解成“把所有零件装成一台机器”的地方。

#### `agent/config.py`

配置对象 `AndroidTestConfig`。

它管理：

- 项目根目录。
- `generated/`、`artifacts/`、`reports/`、`knowledge/` 路径。
- DeepSeek 配置。
- Appium 配置。
- 等待时间。
- 最大重试次数。
- 是否执行生成测试。
- 是否开启 human review。
- checkpoint 路径。

常用环境变量：

```env
ATA_GENERATED_DIR=generated
ATA_ARTIFACTS_DIR=artifacts
ATA_REPORTS_DIR=reports
ATA_KNOWLEDGE_DIR=knowledge
ATA_CHECKPOINT_DIR=reports/checkpoints
ATA_CHECKPOINT_DB_PATH=reports/checkpoints/langgraph.sqlite
ATA_MAX_RETRIES=1
ATA_EXECUTE_GENERATED_TESTS=false
ATA_REVIEW_INTENT_DSL=false
ATA_LLM_CODEGEN_ENABLED=false
ATA_LLM_TEMPERATURE=0.2
ATA_LLM_LOG_CALLS=true
DEEPSEEK_API_KEY=your_key
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com
ANDROID_PLATFORM_NAME=Android
ANDROID_DEVICE_NAME=Android Emulator
ANDROID_APP_PACKAGE=com.example
ANDROID_APP_ACTIVITY=.MainActivity
ANDROID_APK_PATH=Apps/app.apk
ANDROID_REINSTALL_APP=false
APPIUM_SERVER_URL=http://127.0.0.1:4723
```

#### `agent/capabilities.py`

Appium capabilities 构建逻辑。

职责：

- 从 `AndroidTestConfig` 读取平台、设备、包名、Activity、APK 路径。
- 从 DSL 的 `name`、`description`、`app_package`、`app_activity` 中解析 App 信息，允许单条用例覆盖默认包名/Activity。
- `ANDROID_REINSTALL_APP=true` 时把 `ANDROID_APK_PATH` 写入 `appium:app`，并设置 `appium:enforceAppInstall`。
- `ANDROID_APK_PATH` 可以是单个 APK，也可以是只包含一个 APK 的目录。
- 会过滤明显的 placeholder，例如 `your_`、`你的`、`/path/to/`。

#### `agent/graph.py`

LangGraph 流程图。

这是当前 Agent 的主流程控制文件。

主流程是：

```text
analyzer
  -> planner
  -> dsl
  -> human_review
  -> element
  -> codegen
  -> executor
  -> validator
  -> failure_artifacts
  -> failure_knowledge
```

`failure_knowledge` 后面会根据 `validator` 产出的失败类型分支：

```text
locator_not_found -> retrier -> dsl
timeout           -> wait_strategy -> element
assertion         -> debug -> planner
unknown           -> debug -> planner
passed            -> END
environment       -> END
```

这个文件还负责：

- 每个节点执行后写 JSON checkpoint。
- 使用 `langgraph-checkpoint-sqlite` 保存 LangGraph checkpoint。
- 从某个 checkpoint 恢复执行。

#### `agent/state.py`

定义整个 Agent 流程共享的状态 `AgentState`。

状态里会逐步放入：

- `raw_case`：原始自然语言用例。
- `analyzed_requirements`：分析后的需求。
- `plan`：测试计划。
- `intent_dsl`：意图级 DSL。
- `resolved_dsl`：带 locator 的 DSL。
- `generated_files`：生成文件路径。
- `execution_result`：执行结果。
- `validation_result`：校验结果，包含失败类型、异常类、错误签名、失败 action/target、fingerprint 和建议。
- `element_resolution`：ElementNode 的 locator 解析统计和来源采集结果。
- `human_review`：人工审核状态。
- `retry_count`：重试次数。
- `metadata`：checkpoint、调试信息、`source_case_path`、`codegen_mode`、`last_debug`、`last_repair`、`failure_artifacts`、`failure_knowledge` 等。

#### `agent/checkpoint.py`

本地 JSON checkpoint 写入器。

每个节点执行后，会在类似下面的目录保存状态：

```text
reports/checkpoints/<thread-id>/001_analyzer.json
reports/checkpoints/<thread-id>/002_planner.json
reports/checkpoints/<thread-id>/003_dsl.json
```

这些文件非常适合排查问题，因为可以看到每一步 Agent 中间产物是什么。

#### `agent/runtime_skills.py`

运行时 prompt skill 加载器。

它不是 Cursor Skill，而是本项目自己的 LLM prompt 资源加载器。

它会把这些内容拼进 LLM system prompt：

```text
system.md
common.md
当前节点 skill
按需 reference
按需 JSON resource
task prompt
```

#### `agent/runtime_resources.py`

加载结构化 JSON 资源。

例如：

- `supported_actions.json`
- `dsl_schema.json`
- `locator_sources.json`

其中 `supported_actions.json` 不只是给 LLM 看，代码里的 DSL 校验也会读取它，避免 prompt 规则和代码规则不一致。

### `android_test_agent/agent/nodes/`

LangGraph 每个节点的实现目录。

#### `analyzer.py`

`AnalyzerNode`。

职责：把原始测试用例变成结构化需求。

输入：

```text
raw_case
```

输出：

```text
analyzed_requirements
```

如果输入本身是 YAML，会尽量直接解析；否则会调用 LLM；如果 LLM 不可用，会走 fallback。

#### `planner.py`

`PlannerNode`。

职责：把需求变成测试计划。

输出示例：

```text
launch app
input username
input password
tap login button
assert home page visible
```

注意：Planner 阶段不应该生成真实 locator。如果 LLM 生成了 locator，会被清理掉。

#### `dsl.py`

`DslNode`。

职责：把测试计划变成意图级 DSL。

意图级 DSL 的 target 只描述“要找什么”，不描述“怎么找”。

例如：

```yaml
- action: tap
  target:
    name: login_button
    intent: 登录按钮
```

这里还没有 `resource-id`、XPath、UiSelector。

#### `human_review.py`

`HumanReviewNode`。

职责：可选人工审核。

如果启动时加了：

```bash
--review-intent-dsl
```

Agent 会在生成 intent DSL 后暂停，让你确认“测什么”是否正确。

如果在非交互环境中运行，无法读取人工输入时会抛出 `HumanReviewRejected`，CLI 会以 exit code `2` 结束。此时可以修改 `reports/reviews/*_intent_dsl.yaml`，再用 `--resume-from-checkpoint` 和 `--approved-intent-dsl` 从 DSL checkpoint 恢复。

#### `element.py`

`ElementNode`。

职责：把 intent DSL 里的抽象 target 解析成真实 locator。

它会并行采集：

- ADB UI dump XML。
- 截图。
- 人工配置 `config/elements.yaml`。
- 历史元素记忆 `knowledge/elements/element_memory.json`。

然后调用 `LocatorResolver`，输出 `resolved_dsl`。

这是当前框架里非常关键的节点，因为 locator 稳不稳定主要在这里决定。

#### `codegen.py`

`CodegenNode`。

职责：把 DSL 交给 `PytestAppiumCodeGenerator`，生成：

```text
generated/dsl/<name>.yaml
generated/tests/test_<name>.py
```

这是默认代码生成路径，行为稳定，类似 DSL 编译器。

#### `llm_codegen.py`

`LlmCodegenNode`。

职责：可选地让 LLM 从 resolved DSL 直接生成 pytest/Appium Python 文件。

开启方式：

```bash
python main.py --case-file tests/ApiDemos/01_app_launch_home_categories.yaml --llm-codegen
```

或：

```env
ATA_LLM_CODEGEN_ENABLED=true
```

该节点会先调用 LLM 生成 Python 代码，再做 Python `compile()` 校验。如果编译失败，会把错误反馈给 LLM 修复一次。默认不启用。

#### `executor.py`

`ExecutorNode`。

职责：执行生成出来的 pytest。

如果没有开启 `--execute`，它只会返回 dry-run，不真的跑设备测试。

#### `validator.py`

`ValidatorNode`。

职责：分析执行结果，判断是否通过，以及失败类型是什么。

失败时还会提取结构化排障信息：

- `exception_class`：异常类，例如 `NoSuchElementException`。
- `error_signature`：归一化后的错误摘要。
- `stack_summary`：项目相关堆栈摘要。
- `failing_action`：失败 action。
- `failing_target`：失败 target。
- `fingerprint`：用于失败知识库去重和检索的稳定指纹。

常见失败类型：

- `locator_not_found`
- `timeout`
- `assertion`
- `environment`
- `unknown`

#### `failure_artifacts.py`

`FailureArtifactsNode`。

职责：失败后采集设备和 Appium 诊断信息，包括：

- logcat。
- UI dump。
- 截图。
- Appium server 状态。
- 失败 trace JSON。

#### `failure_knowledge.py`

`FailureKnowledgeNode`。

职责：把失败模式沉淀到本地知识库，并把历史解决方案合并回当前建议。

它会写入：

```text
knowledge/failures/failure_memory.json
```

写入内容包括 failure type、异常类、错误签名、失败 action/target、fingerprint、建议修复方案、artifact 路径、出现次数和 verified 状态。后续 retry 成功时，会把对应 fingerprint 标记为 `verified` 并提升 confidence。

#### `retrier.py`

`RetrierNode`。

职责：处理 locator 失败。

例如 locator 找不到时，它会清掉旧 locator 信息，让流程回到 DSL/Element 重新解析。

#### `wait_strategy.py`

`WaitStrategyNode`。

职责：处理 timeout 失败。

它会尝试插入 `wait_visible` 之类的等待步骤，然后回到 `ElementNode` 重新解析执行。

#### `debug.py`

`DebugNode`。

职责：处理 assertion 或 unknown 失败。

它会记录调试信息，然后回到 `PlannerNode` 重新规划。

#### `coder.py`

历史兼容文件。

以前 `CoderNode` 同时做 DSL 和代码生成。现在已经拆成：

```text
DslNode -> CodegenNode
```

所以 `coder.py` 现在主要是兼容旧名字。

### `android_test_agent/dsl/`

DSL 相关目录。

#### `schema.py`

DSL 校验逻辑。

主要函数：

- `validate_intent_dsl()`：校验意图级 DSL。
- `validate_executable_dsl()`：校验带 locator 的可执行 DSL。
- `validate_test_dsl()`：兼容旧调用名，当前等同于 intent DSL 校验。
- `action_target_fields()`：返回某个 action 需要解析 locator 的字段，例如 `drag_and_drop` 会返回 `source` 和 `target`。
- `normalize_test_name()`：把测试名转成文件名安全格式。

支持的 action 来自：

```text
android_test_agent/agent/runtime_skills/resources/supported_actions.json
```

Planner fallback 和 runtime skills 也会使用这些 action，例如 `scroll_to_text`、扩展手势 action 和断言 action。

#### `locator_resolver.py`

locator 解析核心。

职责：把 target 的 `name/intent/label/description` 解析成真实 Appium locator。

它会按多个来源找候选：

```text
provided locator
manual mapping: config/elements.yaml
element memory: knowledge/elements/element_memory.json
ui hierarchy: ADB dump 或 driver.page_source
optional LLM selection
```

当前支持 locator 类型：

- `id`
- `android_uiautomator`
- `accessibility_id`
- `text`
- `xpath`

当前还支持：

- 多候选 `locator_candidates`。
- 主 locator 失败后 fallback 到下一个候选。
- 重复 id 命中多个元素时，根据 metadata 做二次筛选。

#### `codegen.py`

pytest/Appium 代码生成器。

它会把 DSL 渲染成一个完整 pytest 文件。生成的测试文件里包含：

- Appium driver 初始化。
- `LocatorResolver` 运行时兜底。
- locator 候选 fallback。
- 重复 locator 二次筛选。
- locator 失败 artifacts 保存。

生成的 pytest 不再维护独立的一套 action 分支，而是调用共享的 `AndroidDslActionRuntime`，确保 codegen 路径和直接 DSL 执行路径语义一致。

#### `generated_registry.py`

生成文件登记器。

职责：

- 按原始用例文本计算短 hash，作为 `case_key`。
- 将每个用例生成的 DSL/pytest 路径写入 `generated/.generated_cases.json`。
- 同一个源用例再次生成时，先清理旧的生成文件，再写入新文件。
- `output_name_from_case_path()` 会优先使用 `--case-file` 的文件名作为输出名，避免自然语言标题变化导致文件名不稳定。

#### `action_runtime.py`

DSL action 运行时。

职责：执行 `supported_actions.json` 中定义的 Android DSL action，包括：

- 基础交互：`launch_app`、`tap`、`input`、`clear`、`back`。
- 等待和断言：`wait_visible`、`assert_visible`、`assert_text`、`assert_checked`、`assert_enabled`、`assert_selected`、`assert_text_equals`、`assert_text_contains`、`wait_gone`、`assert_not_visible`。
- 手势：`long_press`、`swipe`、`scroll`、`drag_and_drop`、`tap_coordinates`、`pinch`、`zoom`、`w3c_actions`。
- 设备/App 动作：`press_key`、`hide_keyboard`、`background_app`、`activate_app`、`terminate_app`、`change_orientation`、`accept_permission`、`dismiss_dialog`。

手势优先使用 Appium UiAutomator2 的 `mobile:*Gesture`，复杂多指动作可通过 `w3c_actions` 传入 W3C actions payload。

### `android_test_agent/executor/`

执行层目录。

#### `dsl_executor.py`

包含两个执行器：

- `DSLExecutor`：直接解释执行 DSL。
- `PytestExecutor`：通过子进程执行生成的 pytest 文件。

当前主流程主要使用 `PytestExecutor`。

`PytestExecutor` 会返回 `execution_result`，其中包括 pytest 命令、stdout/stderr、return code、生成测试路径，以及 Appium server 诊断信息。

#### `AppiumServerManager`

定义在 `dsl_executor.py` 中。

职责：

- 执行前访问 `APPIUM_SERVER_URL/status` 检查 Appium 是否可用。
- 如果不可用，尝试托管启动本机 `appium` 命令。
- 托管启动时把 Appium 日志和进程输出写入 `artifacts/appium_logs/`。
- 执行结束后停止由本次流程托管启动的 Appium 进程。
- 将 `ready`、`managed`、`server_url`、`command`、`log_path`、`process_output_path` 等信息写入 `execution_result.appium_server`。

`FailureArtifactsNode` 会在失败时收集这些 managed Appium 日志路径。

#### `appium_executor.py`

Appium 直接执行封装。

职责：

- 启动 Appium driver。
- 执行 DSL step。
- 等待元素。
- 解析 locator。
- 多候选 fallback。
- 重复 locator 二次筛选。
- 成功后写回元素记忆。
- 失败后写 artifacts。

该执行器也复用 `AndroidDslActionRuntime`，避免直接执行 DSL 和生成 pytest 的行为分叉。

#### `retry_policy.py`

失败重试策略。

职责：

- 判断某类失败是否值得 retry。
- timeout 时尝试修复 DSL，例如插入 `wait_visible`。

`should_retry()` 当前允许 retry 的失败类型：

- `locator_not_found`
- `timeout`
- `assertion`
- `unknown`

最大次数来自 `ATA_MAX_RETRIES` / `config.max_retries`，默认是 `1`。`environment` 失败不会改 DSL，通常需要人工检查 Appium、ADB、包名、Activity 或设备状态。

### `android_test_agent/tools/`

底层工具目录。

这些工具不负责 Agent 决策，只负责和设备、Appium、文件打交道。

#### `base.py`

定义工具统一返回结构 `ToolResult`。

#### `adb_tool.py`

封装 ADB 命令执行。

如果 `adb` 不存在或超时，会返回失败结果，而不是直接让程序崩溃。

#### `ui_dump_tool.py`

执行：

```bash
adb shell uiautomator dump
adb pull
```

把当前 Android UI hierarchy 拉成本地 XML。

#### `screenshot_tool.py`

执行截图并拉到本地。

#### `logcat_tool.py`

采集 Android logcat。

#### `appium_tool.py`

检查 Appium server 状态。

#### `ui_hierarchy_parser.py`

解析 Android UI XML。

它会把 XML node 转成 `UIElement`，再生成 `LocatorCandidate`。

当前会根据这些信息打分：

- `resource-id`
- `text`
- `content-desc`
- `class`
- `bounds`
- `clickable`
- `enabled`
- locator 是否唯一
- UiSelector 是否组合多个条件

### `android_test_agent/memory/`

记忆系统目录。

当前是本地 JSON 存储，未来可以替换为真正的向量库。

#### `base.py`

Memory 抽象接口。

#### `vector_store.py`

简单 JSON 存储和 token 搜索实现。

名字叫 vector store，但当前并不是真正 embedding 向量检索，更像一个轻量占位实现。
它支持 append、按字段 upsert、精确查找和简单关键词搜索。

#### `case_memory.py`

历史用例记忆。

当前已经实现 `CaseMemory` 接口和本地 JSON 存储路径约定，但 Agent 主流程还没有自动写入或检索 `knowledge/cases/case_memory.json`。

#### `element_memory.py`

元素 locator 记忆。

当某个 locator 成功执行后，会写入这里，后续类似 target 可以优先复用。

#### `failure_memory.py`

失败模式记忆。

当前已经接入主流程，由 `FailureKnowledgeNode` 使用。默认保存到：

```text
knowledge/failures/failure_memory.json
```

典型字段：

- `fingerprint`：稳定失败指纹。
- `failure_type`：失败类型。
- `exception_class`：异常类。
- `error_signature`：错误摘要。
- `failing_action` / `failing_target`：失败动作和目标。
- `stack_summary`：项目相关堆栈摘要。
- `suggested_fix`：建议修复方案。
- `occurrence_count`：相同失败出现次数。
- `status`：`observed` 或 `verified`。
- `confidence`：建议可信度。
- `artifacts`：trace、截图、UI dump、logcat 等路径。

#### `retriever.py`

`KnowledgeRetriever`。

聚合多个 memory 的检索器。当前作为预留能力存在，主流程还没有直接调用它。

### `android_test_agent/llm/`

LLM 客户端目录。

#### `base.py`

定义统一 LLM 接口。

#### `deepseek_client.py`

DeepSeek API 客户端。

会读取：

```env
DEEPSEEK_API_KEY
DEEPSEEK_MODEL
DEEPSEEK_BASE_URL
ATA_LLM_TEMPERATURE
ATA_LLM_LOG_CALLS
```

如果没有配置 Key，部分节点会走 fallback。

### `android_test_agent/agent/runtime_skills/`

运行时 prompt skills。

注意：这里不是 Cursor 的 Agent Skill，而是这个项目自己给 LLM 使用的 prompt 规则库。

核心文件：

- `system.md`：全局系统提示，定义 Agent 总规则。
- `common.md`：通用输出规则。
- `requirements.md`：Analyzer 用。
- `planning.md`：Planner 用。
- `dsl.md`：DslNode 用。
- `locator.md`：LocatorResolver 用。
- `codegen.md`：LlmCodegenNode 用。
- `tools.md`：告诉 LLM 当前有哪些工具和数据来源。

#### `runtime_skills/references/`

长规则，按需加载。

例如：

- `dsl_schema.md`
- `locator_candidate_scoring.md`
- `failure_routing.md`
- `appium_patterns.md`

默认不会全部塞给 LLM，只有复杂场景或重试场景才加载。

#### `runtime_skills/resources/`

结构化 JSON 资源。

例如：

- `supported_actions.json`：支持哪些 DSL action。
- `dsl_schema.json`：DSL 结构说明。
- `locator_sources.json`：locator 来源、评分维度、选择策略。

这些资源既可以给 LLM 看，也可以被代码读取。

### `android_test_agent/agent/skills/`

MCP skill 适配预留目录。

目前不是主流程重点。

#### `skills/base.py`

定义 Skill 抽象接口。

#### `skills/mcp_adapter.py`

`MCPAdapter` 可以注册本地 `Tool`，以接近 MCP 的形式列出和调用工具。当前是预留层，主流程没有直接依赖它。

## 一次运行到底发生了什么

假设你运行：

```bash
python main.py --case-file tests/test_cases_example.yaml
```

流程如下：

### 1. 读取用例

`android_test_agent/main.py` 读取 `tests/test_cases_example.yaml`。

这个文件是自然语言测试用例，不是 DSL，也不是 pytest。

### 2. Analyzer 分析需求

`AnalyzerNode` 把自然语言转成结构化需求。

### 3. Planner 生成测试计划

`PlannerNode` 生成大致步骤，例如启动 App、输入账号、点击登录、验证首页。

### 4. DslNode 生成意图级 DSL

`DslNode` 输出 `intent_dsl`。

这个阶段只描述：

```text
我要点登录按钮
我要输入用户名
我要看到首页标题
```

还不应该出现具体 locator。

### 5. HumanReview 可选审核

如果启动时加了 `--review-intent-dsl`，这里会暂停，等待你确认 DSL 是否符合预期。

### 6. ElementNode 解析元素

`ElementNode` 会把抽象 target 解析成真实 locator。

它会用：

- 人工配置。
- 历史元素记忆。
- UI dump XML。
- Appium page source。
- 可选 LLM 候选选择。

输出 `resolved_dsl`。

### 7. Codegen 生成 pytest

`CodegenNode` 生成：

```text
generated/dsl/<name>.yaml
generated/tests/test_<name>.py
```

### 8. Executor 执行或 dry-run

如果没加 `--execute`，这里不会跑设备，只会说明代码已生成。

如果加了 `--execute`，会执行生成出来的 pytest/Appium 测试。

执行前 `PytestExecutor` 会检查 `APPIUM_SERVER_URL/status`。如果 Appium 不可用，会尝试托管启动本机 `appium` 命令，并把 `log_path`、`process_output_path`、`managed`、`ready` 等诊断信息写入 `execution_result.appium_server`。

### 9. Validator 判断结果

`ValidatorNode` 判断测试是否通过。

如果失败，会分类：

- locator 找不到
- timeout
- assertion 失败
- 环境问题
- unknown

同时会生成稳定 fingerprint，并提取异常类、错误签名、失败 action/target 和项目相关堆栈摘要。

### 10. 失败 artifacts

`FailureArtifactsNode` 会采集失败现场：

- logcat。
- UI dump。
- 截图。
- Appium 状态。
- trace JSON。

### 11. 失败知识库

`FailureKnowledgeNode` 会查询并更新：

```text
knowledge/failures/failure_memory.json
```

如果找到相似历史失败，会把历史 `suggested_fix` 合并进当前 `validation_result.suggestions`。如果后续 retry 成功，会把对应 fingerprint 标记为 `verified`。

### 12. 失败路由

LangGraph 根据失败类型决定下一步：

```text
locator_not_found -> Retrier -> DslNode
timeout           -> WaitStrategy -> ElementNode
assertion/unknown -> Debug -> PlannerNode
environment       -> END
passed            -> END
```

## 你最应该先看的文件

如果你现在已经看不懂框架了，建议按这个顺序看：

### 第一组：先看主流程

```text
android_test_agent/main.py
android_test_agent/agent/core.py
android_test_agent/agent/graph.py
android_test_agent/agent/state.py
```

这四个文件能让你理解 Agent 是怎么被启动、怎么编排、状态怎么传递的。

### 第二组：再看节点

```text
android_test_agent/agent/nodes/analyzer.py
android_test_agent/agent/nodes/planner.py
android_test_agent/agent/nodes/dsl.py
android_test_agent/agent/nodes/element.py
android_test_agent/agent/nodes/codegen.py
android_test_agent/agent/nodes/executor.py
android_test_agent/agent/nodes/validator.py
android_test_agent/agent/nodes/failure_artifacts.py
android_test_agent/agent/nodes/failure_knowledge.py
```

这几个文件对应主流程里的每一步。

### 第三组：重点看 locator

```text
android_test_agent/dsl/locator_resolver.py
android_test_agent/dsl/action_runtime.py
android_test_agent/tools/ui_hierarchy_parser.py
android_test_agent/executor/appium_executor.py
android_test_agent/dsl/codegen.py
```

这里是当前框架最复杂的部分：从“登录按钮”找到真实 Android 元素。

### 第四组：最后看 prompt skills

```text
android_test_agent/agent/runtime_skills.py
android_test_agent/agent/runtime_skills/
android_test_agent/agent/runtime_resources.py
```

这里决定 LLM 每次被调用时看到什么规则。

## 当前容易混淆的点

### `tests/` 有两种用途

`tests/test_cases_example.yaml` 和 `tests/ApiDemos/*.yaml` 是 Agent 输入用例。

`tests/test_dsl_actions.py` 和 `tests/test_failure_knowledge.py` 是框架单元测试。

真正生成的 pytest 在：

```text
generated/tests/
```

### `config/elements_example.yaml` 不会自动生效

example 文件只是模板。

真正生效的是：

```text
config/elements.yaml
```

### `intent_dsl` 和 `resolved_dsl` 不一样

`intent_dsl`：

```yaml
target:
  name: login_button
  intent: 登录按钮
```

`resolved_dsl`：

```yaml
target:
  name: login_button
  intent: 登录按钮
  locator:
    by: android_uiautomator
    value: new UiSelector().resourceId("com.example:id/login").text("登录")
```

### `runtime_skills/` 不是 Cursor Skill

它是本项目运行时给 DeepSeek/LLM 看的 prompt 文件。

### `--execute` 不强制预先启动 Appium

`PytestExecutor` 会先检查 `APPIUM_SERVER_URL/status`。如果不可用，会尝试托管启动本机 `appium` 命令。手动预启动 Appium 仍然可以，但不是必须。

### `artifacts/generated_code/` 当前是预留目录

当前主流程写 `generated/dsl/`、`generated/tests/`、`artifacts/traces/`、`artifacts/locator_failures/` 等目录；`artifacts/generated_code/` 只是预留目录。

## 当前 locator 设计状态

当前 locator 解析已经支持：

- 多候选 `locator_candidates`。
- `android_uiautomator`。
- 重复 id 的候选评分。
- 主 locator 失败后的 fallback。
- 重复 locator 命中多个元素时，按 `text/class/content-desc/bounds/clickable/enabled` 二次筛选。

还可以继续增强的方向：

- `nearby_text` 上下文。
- 成功/失败后的稳定性分数更新。
- 真正的向量库。
- OCR/视觉识别。
- 更细粒度的 failure memory 归因和自动修复策略。

## 一句话总结

这个项目现在不是一个普通 Appium 测试项目，而是一个“用 LangGraph 编排的 Android 测试生成 Agent”。

最核心的链路是：

```text
自然语言 -> 意图 DSL -> 元素解析 -> 可执行 DSL -> pytest/Appium -> 执行结果 -> 失败路由
```

你只要先抓住这条主线，再去看每个目录，就不会被现在越来越多的节点、prompt skills、locator 逻辑绕晕。
