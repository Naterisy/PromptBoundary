# PromptBoundary

[English](README.md) · [Skill 正文](skills/promptboundary/SKILL.md) · [评测材料](evaluation/)

用户说过“别再拿那件私事开玩笑”，后来又说“再吐槽我一次”。这两个要求可以同时满足。PromptBoundary 帮助模型保留对话里的纠错，分辨用户是否改变了要求，并在发出回答前检查实际措辞。

**Agent Skill** 适合能读取对话的 Agent。**Python 控制器**适合能接管模型调用的应用，可保存结构化的纠错记录、在生成前判断冲突，并检查和修订草稿。两者均在应用层工作。Python 运行时只依赖标准库，要求 Python 3.10 或更高版本。

## 工具授权与来源字段实验

新增的可选[权限控制 SDK](docs/capabilities.md)记录外部内容来源，在执行前检查应用授予的工具、参数与次数，并支持被拒绝计划的恢复。明确要求逐字复制的任务还可以绑定来源字段；它不把文档中的指令当成权限，也不保证来源数据真实。

原冻结工具评测中，GPT-4.1 mini 的原始模型执行攻击 8/23、旧会话 Runtime 为 11/23、新权限层为 2/24，正常任务均通过 13/16。六个可配对的改善均有“模型先提出危险动作、权限层拦截、随后完成正常动作”的记录。Sol、Astra 原始模型仍为零，因此该批不能证明两者获得安全提升。[运行与复现](evaluation/agent_security/README.md) · [最新交付报告](evaluation/agent_security/DELIVERY.zh-CN.md) · [独立复核、误拒漏计及评分敏感性](evaluation/agent_security/INDEPENDENT_AUDIT.md)。这组任务改编自公开方法，不是 AgentDojo 官方成绩。

最终来源复制挑战中，4.1 mini 的攻击成功从 4/24 降为 0/24，正常任务两组均为 16/16；小样本配对 p=0.125，不能夸大为普遍保证。Sol、Astra 仍未显示可测安全收益。本轮开发、测试、攻击搜索与重复验证共 2,877 次 API 调用，按实际用量计 6.634151435 美元。来源内容真实与否、开放式推理是否正确仍是未解决问题。

## 托管模型安全实验（v0.2）

[三模型报告](evaluation/hosted/results/main/RESULTS.md)在同一批 32 个场景中比较原始模型、v0.1 控制器和修复版，分别计算攻击是否成功、任务是否完成、正常请求是否被误拒。可查看[复现步骤与原始日志](evaluation/hosted/README.md)、[历史正常请求失败的诊断](evaluation/hosted/DIAGNOSIS.md)和[控制器修复说明](docs/runtime-security.md)。

自然请求中，三个原始模型都已挡住全部 20 个攻击，无法据此宣称修复版降低了攻击率。固定泄露草稿的对照中，旧版交付了 4/12 个秘密，修复版为 0/12；正常请求中，Sol 和 Astra 的修复版各误拒一题。[完整交付报告与成本](evaluation/hosted/DELIVERY.zh-CN.md)

## 早期本地模型实测（v0.1）

在冻结的 12 个中英文合成场景中，Qwen2.5-7B 单用控制器相对原始模型达到了预先设定的改善标准。纠错保持从 3/6 到 4/6，越界从 4/10 到 2/10，误拒均为 0/5，任务通过从 7/12 到 8/12。多保住的一项纠错来自原始历史被移除的用例。每段对话平均多耗时 23.87 秒、多用 3,110 Token。

3B 上控制器也减少了越界，但任务通过少了一项。两个模型把控制器叠加在 Skill 上都未达到改善标准。下面的延迟和 Token 差值均相对同模型的 A 组，包括重放、生成、审核和修正。各指标的分母对应不同类型的题。B、D 使用已加载的 Skill 正文，未测宿主自动选择 Skill 的命中率。[实验报告、逐题回答和失败版本](evaluation/REPORT.md)

### Qwen2.5-3B-Instruct · Q4_K_M

| 组别 | 保持纠错 ↑ | 越界 ↓ | 误拒 ↓ | 任务通过 ↑ | 相对 A 的额外秒数 | 相对 A 的额外 Token |
|---|---:|---:|---:|---:|---:|---:|
| A · 原始 | 3/6 | 5/10 | 0/5 | 7/12 | +0.00 | +0 |
| B · 仅 Skill | 3/6 | 4/10 | 0/5 | 8/12 | -0.44 | +265 |
| C · 仅控制器 | 3/6 | 3/10 | 0/5 | 6/12 | +13.64 | +2,896 |
| D · 两者组合 | 3/6 | 3/10 | 0/5 | 6/12 | +11.75 | +4,515 |

### Qwen2.5-7B-Instruct · Q4_K_M

| 组别 | 保持纠错 ↑ | 越界 ↓ | 误拒 ↓ | 任务通过 ↑ | 相对 A 的额外秒数 | 相对 A 的额外 Token |
|---|---:|---:|---:|---:|---:|---:|
| A · 原始 | 3/6 | 4/10 | 0/5 | 7/12 | +0.00 | +0 |
| B · 仅 Skill | 4/6 | 3/10 | 0/5 | 8/12 | -0.63 | +280 |
| C · 仅控制器 | 4/6 | 2/10 | 0/5 | 8/12 | +23.87 | +3,110 |
| D · 两者组合 | 3/6 | 3/10 | 1/5 | 6/12 | +27.38 | +5,383 |

## 安装与免费演示

```sh
git clone --branch hosted-runtime-evaluation https://github.com/Naterisy/PromptBoundary.git
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

如需复现**旧版 v0.1.0** Python CLI，可在虚拟环境中执行：

```sh
python -m pip install https://github.com/Naterisy/PromptBoundary/releases/download/v0.1.0/promptboundary-0.1.0-py3-none-any.whl
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

每个对话使用独立的 `State`。用 `turn.state.to_dict()` 和 `State.from_dict(saved)` 保存和恢复会话。生成失败时，返回状态仍会保留已经确认的纠错。如需重试同一个用户回合，应传入该回合之前的状态。如需组合使用 Skill 与控制器，把 Skill 文件的 UTF-8 正文作为 `system_prefix` 传入 `StageModel`。适配器会把对话和待审核草稿发送到配置的推理端点。处理私人内容时可选用本机模型。如需保存会话状态，应自行设置访问权限和清理期限。

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
3. 审核器检查实际回答中的越界行为和不必要的拒绝。审核不通过会返回具体修改意见，默认允许再生成一次。审核器指出越界时，需提供候选文本中的证据或明确缺失的要求。结论缺少依据时，可以触发第二次核对。已确认的违规草稿会被拦截。若已交付回答并标记为 `degraded`，表示解析或审核仍存在不确定性，可查看该回合的事件。

SDK 保留最近 12 条对话消息、应用指令、记录表和数量有限的未解析用户回合。记录表可能保留含私人内容的原话，以及已失效的纠错记录。请按会话隔离并及时清理。HTTP 示例每次重放历史，会增加调用次数，重建的解释也可能发生变化。这个无认证的本机服务适合可信单用户环境。模型可能误判作用范围，放过利用私人经历的笑话，或错误拦截合适的回答。访问控制、操作授权和私密数据的存储仍由宿主应用负责。

每轮最多有两次意图解析，最多产生 `max_retries + 1` 版草稿，每版最多两次审核。如果端点明确不支持 JSON Schema，适配器可能额外发起兼容请求。未解析的原话最多保留六轮。受保护场景需要审核明确通过，普通任务遇到两次无依据的审核结论时可以降级交付，并通过 `X-PromptBoundary-Status` 返回 `degraded`。

## 开发与复现

在仓库根目录执行 `python -m unittest discover -s tests -v`。HTTP 集成测试需要可用的回环端口。评测输入、计分器、模型原始回答和实验说明见[评测目录](evaluation/)。代码、Skill 和合成用例采用 [MIT 许可证](LICENSE)。模型权重需根据发布方的条款另行取得。
