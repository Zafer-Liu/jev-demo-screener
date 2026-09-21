# jev-demo-screener · 简历初筛（JD 锚定版 / JD-Anchored Resume Screener）

一次 Jev 调用完成以职位描述为锚的结构化初筛：JD 匹配度、实操深度、关键词吹牛检测，以及置信度门控的推荐结论——单次 8 项评估。

> 适配 TypeSafe Jev —— System One 决策模型（[docs.typesafe.ai](https://docs.typesafe.ai)） · [English](README.md)

## 它做什么

招聘初筛要处理的，是“JD 里每个热词都出现过”的简历。本 MVP 接收两个输入——职位描述（JD）和简历——以该 JD 为锚，一次 Jev 调用问 8 个带类型的问题：年限与深度评分、JD 匹配度评分，技能实证（关键词吹牛检测）、带人经验、开源贡献三个概率判断，加上职业轨迹与带置信度的最终推荐。信号混杂或注水时，结论是 `human_review`，不是硬猜。

流程：

- 一键载入 JD 预设（JD-1 AI 产品工程师 / JD-2 高级前端工程师）与简历样本（A 实干型 / B 关键词型），或粘贴真实材料
- 后端把两者组装成一个 state，发起一次 Jev 调用：

  ```
  JOB DESCRIPTION:
  <jd>

  =====

  RESUME:
  <简历>
  ```

- 置信度门控路由：结论为 面试 / 不推荐 / 转人工；初筛只做排序标记——最终决策留人

## 为什么用 Jev

- **带类型的概率化决策。** 一次调用 8 个答案——3 个 `Score`、3 个 `Noul` 概率、2 个 `Choice`——各有各的量表。不用设计 JSON，也不用修输出。
- **~150ms 模型延迟。** 预热后稳态约 400ms 完成一次初筛往返（共享 TLS 连接）。
- **校准置信度即路由门控。** 推荐结论自带置信度；信号混杂或注水时给出 `human_review`（实测：关键词堆砌简历以 95% 置信度转人工）。工具只负责排序，最终判断留给人——正是招聘合规想要的位置。

## 实测结果

2026-09-20 用 JD 锚定 Web 版实测；一次调用 = 8 问。"—" 表示不在本次记录范围内。

| 组合 | jd_match (0-4) | depth (0-5) | 技能实证 | 职业轨迹 | 推荐结论 |
|---|---|---|---|---|---|
| JD-1 AI 产品工程师 + 简历 A（实干型） | — | 4.0 | 95% | steady_growth | **面试** |
| JD-1 AI 产品工程师 + 简历 B（关键词型） | — | 0.2 | 44% | job_hopping | **转人工**（置信度 95%） |
| JD-2 高级前端工程师 + 简历 A（后端实干型） | **0.03** | 3.98 | — | — | **不推荐**（置信度 100%） |

第三行是本 MVP 的灵魂：同一份在 JD-1 下拿到“面试”的简历 A，换成 JD-2 后匹配度塌到 0.03/4、以 100% 置信度不推荐——而质量信号纹丝不动：深度 3.98/5、带人 95%、开源 90%。**“人不错”和“岗位不合适”被干净分开**：换 JD 结论反转，质量信号不动。

## 快速开始

需要 Python 3.10+。

```bash
pip install -r requirements.txt   # 或：pip install flask typesafe-sdk requests

# 配置 API Key（在 console.typesafe.ai 获取）
cp .env.example .env     # 然后编辑 .env
# .env 只需一行：TYPESAFE_API_KEY=<你的 key>

# Web 初筛台（JD 锚定版，一次调用 8 问）
python server.py
# → http://127.0.0.1:8768

# CLI 旧版 —— 无 JD 锚定的原始版本（7 问），留作对照
python screener.py
```

## HTTP API

**`POST /api/screen`** —— 请求体 `{"jd": "<职位描述>", "text": "<简历>"}`。一次 Jev 调用返回全部 8 项答案，外加运行元数据：

| 字段 | 含义 |
|---|---|
| `years`、`depth`、`jd_match` | Score 评分答案 |
| `skill_evidence`、`mentorship`、`opensource` | Noul 概率（0-1） |
| `progression`、`progression_conf`、`recommend`、`recommend_conf` | Choice 答案 + 置信度 |
| `wall_ms` | 本次初筛调用整体耗时（毫秒） |
| `input_tokens` | API 上报的输入 token 数（`r.usage.input_tokens`；未上报时为 0） |
| `cost_usd` | 预估输入成本，`input_tokens / 1e6 * $0.042`，保留 6 位小数 |
| `gate` | `recommend_conf < 0.6` 时为 `"low-confidence: human review advised"`（置信度门控的转人工理由），否则 `"auto"` |

错误以 JSON 返回：JD/简历为空或两者合计超过 **50,000 字符** 返回 `400`（上限用于保护模型 64k token 上下文）；Jev 调用失败返回 `502`，包成 `{"error": "jev call failed: ..."}`。

**`GET /api/history`** —— 最近 10 条初筛记录，新→旧，仅存内存（重启即清空）。每条含：`ts`（本地时间戳）、`jd`（JD 标题即首行，否则前 30 字符）、`recommend`、`jd_match`、`wall_ms`。Web 初筛台在结果面板下方把它渲染成「最近初筛」条带。

## Jev 问题设计

八问在单次 `system_one` 调用中并行发出，state 为组装后的 JD + 简历（与 `server.py` 的 `QUESTIONS` 完全一致）：

| # | 键 | 类型 | Instructions（要义） | 量表 / 阈值 |
|---|---|---|---|---|
| 1 | `years` | Score | 截至今天有多少年专业经验 | 0-5，锚点：0-1 / 2-3 / 4-5 / 6-7 / 8-9 / 10+ 年 |
| 2 | `depth` | Score | 按候选人亲手做过的东西评实操深度——“忽略技能关键词列表、头衔和公司名” | 0 无真实建造证据 · 3 端到端拥有过重要系统 · 5 职业级深度、行业水准 |
| 3 | `jd_match` | Score | 候选人满足职位描述中明确要求的程度 | 0 几乎不满足 · 3 满足所有核心要求 · 4 全面超出要求 |
| 4 | `skill_evidence` | Noul | 该岗位要求的技能有具体项目实证（建造 / 上线 / 拥有），而不只是关键词 | 概率 0-1 —— 关键词吹牛检测 |
| 5 | `mentorship` | Noul | 有真实的带人 / 团队领导经验 | 概率 0-1 |
| 6 | `opensource` | Noul | 有可验证的开源贡献 | 概率 0-1 |
| 7 | `progression` | Choice | 展现出哪种职业轨迹 | `steady_growth` 职责与职级稳步上升 · `job_hopping` 频繁短跳无成长 · `lateral_moves` 同级岗位反复横移 |
| 8 | `recommend` | Choice | 对职位描述所述岗位的录用建议 | `interview` 高度匹配，进面 · `reject` 明显不匹配 · `human_review` 信号混杂或注水，人先看 |

CLI 旧版（`screener.py`）是无 JD 锚定的基线：7 问，用通用的 `llm_experience` Noul（“真的开发过 LLM 产品，而不只是列关键词”）替代 `jd_match` 与 `skill_evidence`，`recommend` 也锚定在固定角色上。两版并存，让 JD 锚定的价值可以直接对照测量——同样的简历，更锋利的结论。

## 配置与定制

- **任意 JD + 任意简历。** 在页面两侧自由粘贴，或改 `web/index.html` 里的预设常量 `JD1`、`JD2`、`RESUME_A`、`RESUME_B` 换成你自己的样本。
- **你自己的评分标尺。** 改 `server.py` 的 `QUESTIONS`：加岗位专属 Noul 问题（比如“主导过设计系统建设”），或按你的职级体系重设 `jd_match` 锚点。
- **值得做的实验。** 同一份简历分别对 JD-1 和 JD-2 初筛，看匹配度翻转而质量信号不动。
- **服务端**：全局共享一个 `TypeSafeClient`，加锁串行化；监听 `127.0.0.1:8768`。

## 项目结构

```
jev-demo-screener/
├── screener.py       # CLI 旧版：无 JD 锚定基线，7 问（留作对照）
├── server.py         # Flask Web MVP：POST /api/screen、GET /api/history，JD 锚定，一次调用 8 问
├── web/
│   └── index.html    # 初筛台界面，内置 JD / 简历预设（单文件，无构建步骤）
├── requirements.txt  # flask>=3.0、typesafe-sdk、requests
├── LICENSE           # MIT
└── .env              # TYPESAFE_API_KEY=...（切勿提交）
```

## 注意事项

- 启动后首次调用有约 6 秒的空闲 TLS 握手；`server.py` 启动即用守护线程预热，稳态约 400ms 一次初筛。
- 按官方价格，每次初筛成本远低于 $0.001。
- `.env` 存放 API Key——务必远离版本控制。
- 合规：初筛只做排序与标记，录用决策留给人。
