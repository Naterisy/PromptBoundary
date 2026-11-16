# PromptBoundary

[English](README.md) · [Skill 正文](skills/promptboundary/SKILL.md) · [评测材料](evaluation/)

用户说过“别再拿那件私事开玩笑”，后来又说“再吐槽我一次”。这两个要求可以同时满足。PromptBoundary 帮助模型保留对话里的纠错，分辨用户是否改变了要求，并在发出回答前检查实际措辞。

**Agent Skill** 适合能读取对话的 Agent。**Python 控制器**适合能接管模型调用的应用，可保存结构化的纠错记录、在生成前判断冲突，并检查和修订草稿。两者均在应用层工作。Python 运行时只依赖标准库，要求 Python 3.10 或更高版本。

## v0.2 实验结果

**结果依赖模型，跨模型的改善门槛没有通过。** 在新的 24 个中英文场景和隐藏组别的独立评分中，7B 新版控制器的任务完成数为 19/24，旧版为 13/24；越界从 8/20 降到 3/20，约束保持（含纠错、偏好和隐私边界）均为 6/10。平均耗时从 24.23 秒降到 12.44 秒，Token 从 2,989 降到 2,270。但 3B 上虽然越界减少，任务完成数却比旧版少一项，也低于原始模型。Skill 与控制器组合在两个模型上的结果同样存在反转。

请结合[完整六组报告、288 条原始回答、独立评分及开销](evaluation/REPORT-v4.md)选择配置。[v0.1.0 的失败与结果](evaluation/REPORT.md)继续保留。v0.2 明确作为实验版本发布，不宣称是普遍有效的升级。实验没有测量宿主自动发现 Skill 的能力。

## 安装与免费演示

```sh
git clone --branch v0.2.0 https://github.com/Naterisy/PromptBoundary.git
cd PromptBoundary
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
promptboundary demo
```

演示使用合成对话和本地脚本 Mock。要让 Codex 发现 Skill，单独执行以下命令即可：

```sh
mkdir -p ~/.agents/skills
cp -R skills/promptboundary ~/.agents/skills/
```

在新对话里使用 `$promptboundary`，或让 Agent 根据描述选择它。只想在某个项目中使用时，把目录复制到该项目的 `.agents/skills/`。Skill 可以脱离 Python 包独立安装。[Codex Skill 文档](https://developers.openai.com/codex/skills/)

[v0.2.0 实验版发布页](https://github.com/Naterisy/PromptBoundary/releases/tag/v0.2.0) 同时提供独立 Skill ZIP、可离线安装的 Python wheel 及 SHA-256 校验值。

只安装 Python CLI 时，可在虚拟环境中直接执行：

```sh
python -m pip install https://github.com/Naterisy/PromptBoundary/releases/download/v0.2.0/promptboundary-0.2.0-py3-none-any.whl
promptboundary demo
```

## 接入真实本地模型

启动支持结构化输出的 Chat Completions 服务。适配器优先用 JSON Schema 解析意图、审核回答，端点明确表示不支持时可回退到 JSON 对象模式。草稿使用普通文本生成。例如安装 llama.cpp 并自行下载 GGUF 模型后执行：

```sh
llama-server -m /path/to/instruct.gguf --host 127.0.0.1 --port 18764 --alias pb-qwen -c 8192 -np 1
```

```python
from promptboundary import BoundaryController, OpenAICompatible, StageModel, State

upstream = OpenAICompatible("http://127.0.0.1:18764/v1", "pb-qwen")
model = StageModel(upstream, generation={"temperature": 0, "max_tokens": 512})
controller = BoundaryController(model, max_retries=1)
state = State()
for request in ["以后别叫我老板。推荐一种早餐。", "用刚才那种随意的语气，再推荐一个。"]:
    turn = controller.run(state, request)
    state = turn.state
    print(turn.text)
```

每个对话使用独立的 `State`。用 `turn.state.to_dict()` 和 `State.from_dict(saved)` 保存和恢复会话。生成失败时，返回状态仍会保留已经确认的纠错。如需重试同一个用户回合，应传入该回合之前的状态。如需组合使用 Skill 与控制器，把 Skill 文件的 UTF-8 正文作为 `system_prefix` 传入 `StageModel`。从 v0.2 起，这个前缀只参与回答生成，解析与审核使用各自的协议；生成阶段的应用指令保留原生 system/developer 角色，结构化阶段则通过 JSON 输入接收历史。适配器会把对话和待审核草稿发送到配置的推理端点。处理私人内容时可选用本机模型。如需保存会话状态，应自行设置访问权限和清理期限。

## 运行 HTTP 中间件

先启动代理，再在另一个终端提交完整消息历史。

```sh
promptboundary serve --base-url http://127.0.0.1:18764/v1 --model pb-qwen --port 8080
```

```sh
curl -sS http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"pb-qwen","messages":[{"role":"user","content":"Please drop the titles. Just call me Lee."},{"role":"assistant","content":"Sure, Lee."},{"role":"user","content":"Greet me and suggest a podcast topic."}],"temperature":0,"max_tokens":384}'
```

如需测试组合配置，可额外添加 `--skill SKILL.md`；其效果并未在两个模型上保持一致。代理只监听本机回环地址，每次从消息历史重建状态，支持单个候选、非流式纯文本 Chat Completions。用 `GET /v1/models` 查询模型名。`max_tokens` 按每次模型调用计算。响应会汇总提供方返回的历史重放、生成、审核和重试 Token 数。通过响应头 `X-PromptBoundary-Status` 或 SDK 的 `turn.status` 检查是否发生回退。想用本地 Mock 测试 HTTP 接口时运行 `promptboundary serve --mock`，请求中的模型名填 `promptboundary-mock`。

## 控制器如何做判断

1. 解析器引用当前用户的原话，提出带作用范围的记录改动。历史消息重放只提取记忆变化；当前回合还会结合有限的对话历史判断意图与隐私。控制器验证操作、记录 ID、有效期和证据后再更新状态。
2. 生成器保留用户当前的实际请求，应用相关记录。单轮例外只覆盖这一轮，明确撤销会结束对应记录。个人玩笑涉及受保护经历时，生成阶段会省去私人历史，保留用户要求的主题和非私人纠错。当用户本轮明确授权使用某些私人内容时，则保留原始的有限历史及其余有效约束，判断授权范围；这条路径不承诺移除所有敏感内容。
3. 审核器检查实际回答是否满足适用要求，以及是否存在误拒。审核通过时只返回简短结论；拒绝时必须提供对应具体记录或当前要求的原文证据，默认允许再生成一次。缺少依据的结论可以触发第二次核对。已确认的违规草稿会被拦截。若已交付回答标记为 `degraded`，表示解析或审核仍有不确定性，可查看该回合事件。

SDK 保留最近 12 条对话消息、应用指令、记录表和数量有限的未解析用户回合。记录表可能保留含私人内容的原话，以及已失效的纠错记录。请按会话隔离并及时清理。HTTP 示例每次重放历史，会增加调用次数，重建的解释也可能发生变化。这个无认证的本机服务适合可信单用户环境。模型可能误判作用范围，放过利用私人经历的笑话，或错误拦截合适的回答。访问控制、操作授权和私密数据的存储仍由宿主应用负责。

每轮最多有两次意图解析，最多产生 `max_retries + 1` 版草稿，每版最多两次审核。如果端点明确不支持 JSON Schema，适配器可能额外发起兼容请求。未解析的原话最多保留六轮。受保护场景需要审核明确通过，普通任务遇到两次无依据的审核结论时可以降级交付，并通过 `X-PromptBoundary-Status` 返回 `degraded`。

## 开发与复现

在仓库根目录执行 `python -m unittest discover -s tests -v`。HTTP 集成测试需要可用的回环端口。评测输入、计分器、模型原始回答和实验说明见[评测目录](evaluation/)。代码、Skill 和合成用例采用 [MIT 许可证](LICENSE)。模型权重需根据发布方的条款另行取得。
