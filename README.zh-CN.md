# PromptBoundary

[English](README.md) · [Skill 正文](skills/promptboundary/SKILL.md) · [评测材料](evaluation/)

用户说过“别再拿那件私事开玩笑”，后来又说“再吐槽我一次”。这两个要求可以同时满足。PromptBoundary 帮助模型保留对话里的纠错，分辨用户是否改变了要求，并在发出回答前检查实际措辞。

**Agent Skill** 适合能读取对话的 Agent。**Python 控制器**适合能接管模型调用的应用，可保存结构化的纠错记录、在生成前判断冲突，并检查和修订草稿。两者均在应用层工作。Python 运行时只依赖标准库，要求 Python 3.10 或更高版本。

## 安装与免费演示

```sh
git clone --branch v0.1.0 https://github.com/Naterisy/PromptBoundary.git
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

[v0.1.0 发布页](https://github.com/Naterisy/PromptBoundary/releases/tag/v0.1.0) 同时提供独立 Skill ZIP、可离线安装的 Python wheel 及 SHA-256 校验值。

## 接入真实本地模型

启动支持 JSON 模式的 Chat Completions 服务。例如安装 llama.cpp 并自行下载 GGUF 模型后执行：

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

每个对话使用独立的 `State`。用 `turn.state.to_dict()` 和 `State.from_dict(saved)` 保存和恢复会话。生成失败时，返回状态仍会保留已经确认的纠错；如需重试同一个用户回合，应传入该回合之前的状态。如需组合使用 Skill 与控制器，把 Skill 文件的 UTF-8 正文作为 `system_prefix` 传入 `StageModel`。适配器会把对话和待审核草稿发送到配置的推理端点。处理私人内容时可选用本机模型；如需保存会话状态，应自行设置访问权限和清理期限。

## 运行 HTTP 中间件

先启动代理，再在另一个终端提交完整消息历史。

```sh
promptboundary serve --base-url http://127.0.0.1:18764/v1 --model pb-qwen --skill SKILL.md --port 8080
```

```sh
curl -sS http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"pb-qwen","messages":[{"role":"user","content":"Please drop the titles. Just call me Lee."},{"role":"assistant","content":"Sure, Lee."},{"role":"user","content":"Greet me and suggest a podcast topic."}],"temperature":0,"max_tokens":384}'
```

代理只监听本机回环地址，每次从消息历史重建状态，支持单个候选、非流式纯文本 Chat Completions。用 `GET /v1/models` 查询模型名。`max_tokens` 按每次模型调用计算。响应会汇总提供方返回的历史重放、生成、审核和重试 Token 数。通过响应头 `X-PromptBoundary-Status` 或 SDK 的 `turn.status` 检查是否发生回退。想用本地 Mock 测试 HTTP 接口时运行 `promptboundary serve --mock`，请求中的模型名填 `promptboundary-mock`。

## 控制器如何做判断

1. 意图解析器读取最新用户消息、最近的对话和仍生效的记录，提出带作用范围的改动，并引用当前用户的原话。控制器验证操作类型、记录 ID、有效期和原文证据后再更新状态。
2. 生成器读取本轮请求和有效约束。单轮例外只覆盖这一轮。明确撤销会结束对应记录。
3. 审核器检查实际回答中的越界行为和不必要的拒绝。审核不通过会返回具体修改意见，默认允许再生成一次。所有草稿都未通过时，调用方会收到回退状态。

SDK 保留最近 12 条对话消息、应用指令和记录表。记录表可能保留含私人内容的原话，以及已失效的纠错记录。请按会话隔离并及时清理。HTTP 示例每次重放历史，会增加调用次数，重建的解释也可能发生变化。这个无认证的本机服务适合可信单用户环境。

## 开发与复现

在仓库根目录执行 `python -m unittest discover -s tests -v`。HTTP 集成测试需要可用的回环端口。评测输入、计分器、模型原始回答和实验说明见[评测目录](evaluation/)。代码、Skill 和合成用例采用 [MIT 许可证](LICENSE)。模型权重需根据发布方的条款另行取得。
