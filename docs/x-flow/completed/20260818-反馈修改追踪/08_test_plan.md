# 测试计划 — 20260818-反馈修改追踪

> req_id: 20260818-反馈修改追踪 | 阶段: TEST_PLAN | Agent: 05-test-agent
> 输入: `03_clarify_prd-refined.md` + `07_impl_changed-files.md` + 三层记忆检索

## 测试范围

- 变更文件数: 15（后端 10 + 前端 5）
- 验收标准数: 14（AC-101~104 / AC-201~205 / AC-301~303 / AC-401~404）
- 测试用例数: 12
- E2E 场景数: 4

## 命中的经验记忆

| 记忆 ID | 摘要 | 转化后的测试关注点 |
|---------|------|-------------------|
| INIT-003 | Django + DRF + JWT；`check_account_access` + course 级中间件授权 | AC-402 角色访问控制、NFR-2 上报身份/归属校验 → TC-009 / TC-011 |
| INIT-004 | API 索引：`/api/feedback/`、`/api/playtest/` 等 REST 路由 | E2E 路由可达性与响应结构断言 → E2E-001 / E2E-002 |
| INIT-009 | 后端 7 个空测试 stub、无前端测试（覆盖缺口） | 禁止静态推演，所有 E2E 必须实际运行（编译→启动→发请求→验证） |
| CORR-001 | 所有代码注释（含 @changelog、docstring、行内）一律英文 | 通用检查项 CHK-2：新增代码注释英文抽查 |

> Layer 3（归档需求经验）：`docs/x-flow/completed/` 不存在，无归档经验可复用。

## 测试用例

### TC-001: 反思写作（Feature 1）连续生成产生多版本
- 关联验收标准: PRD §2.1 AC-101 / AC-103
- 前置条件: 后端服务运行、数据库已迁移；测试学生 + 含 TextArea 字段的 milestone 模板 + 已提交 submission
- 测试步骤:
  1. 以学生身份 POST `/api/feedback/`，携带 `submission_id`、`question`、答案文本 A、`mode=basic`
  2. 修改答案文本为 B，再次 POST（新 request_id）
  3. 查询数据库 `feedback_feedbackanswerversion` 与 `feedback_aifeedbackrecord`
- 预期结果:
  - 两次请求各产生 1 条版本记录（version 1、version 2），version 按学生/问题维度递增
  - 每次各产生 1 条 AI 反馈记录，`version_id` 指向对应版本
- 类型: 正常

### TC-002: 版本记录字段完整性
- 关联验收标准: PRD §2.1 AC-102
- 前置条件: TC-001 已执行
- 测试步骤:
  1. 查询任意一条 `FeedbackAnswerVersion`
- 预期结果: 字段齐全且正确：creator(学生)、course、milestone、template、question、answer(原文快照)、version、created_at 均为非空
- 类型: 单元

### TC-003: Playtest 前端上报（带 submission_id）落库
- 关联验收标准: PRD §2.2 AC-201 / AC-203 / AC-204
- 前置条件: 后端服务运行；测试学生已提交 milestone
- 测试步骤:
  1. 以学生身份 POST `/api/feedback/records/`，携带 `submission_id`、`question`、`answer`、`idempotency_key`、策略=playtest、评分/反馈/模型版本/usage 元数据
- 预期结果: 响应 201；同请求内生成 1 条版本快照 + 1 条 AI 反馈记录，`version_id` 关联正确
- 类型: 正常

### TC-004: 不携带 submission_id 时不落库（纯生成）
- 关联验收标准: PRD §2.1 AC-104（草稿/无上下文不产生版本）
- 前置条件: 后端服务运行
- 测试步骤:
  1. POST `/api/feedback/`（反思写作）或 `/api/feedback/records/`（Playtest），**不携带** `submission_id`
- 预期结果: 接口正常返回反馈内容；数据库中不产生新的版本记录与 AI 反馈记录
- 类型: 边界

### TC-005: 幂等键去重（RISK-DA006）
- 关联验收标准: PRD §2.2 AC-201（无重复记录）
- 前置条件: 后端服务运行；已有一条 idempotency_key 上报记录
- 测试步骤:
  1. 使用相同 `idempotency_key` + 相同 payload 再次 POST `/api/feedback/records/`
- 预期结果: 第二次请求不新增记录，返回已有记录（去重成功）；`feedback_aifeedbackrecord` 中该 key 仅 1 行
- 类型: 异常/回归（历史缺陷模式：网络重试重复落库）

### TC-006: AI 生成失败不落库
- 关联验收标准: PRD §4 约束（生成失败不上报）
- 前置条件: 可 mock 或触发 ChatGPT/LightRAG 调用失败
- 测试步骤:
  1. 使 AI 生成接口抛错（如无效 API key / 依赖服务不可达），再次触发生成
- 预期结果: 接口返回错误；事务整体回滚，无任何版本/反馈记录写入
- 类型: 异常

### TC-007: 历史回填命令（首次执行 + 幂等重跑）
- 关联验收标准: PRD §2.3 AC-301 / AC-302 / AC-303
- 前置条件: 数据库存在若干 `FeedbackInitialResponse` 历史记录；无 `FeedbackAnswerVersion`
- 测试步骤:
  1. 执行 `python manage.py backfill_feedback_versions`
  2. 核对 version 1 数量 = 历史记录数；对应 `aifeedbackrecord` 无关联
  3. 再次执行同一命令
- 预期结果: 首次生成每学生/问题 version 1；原表数据未被破坏；重跑跳过已存在项，数量不翻倍（幂等）
- 类型: 正常/回归

### TC-008: 查询 API 维度过滤
- 关联验收标准: PRD §2.4 AC-401 / AC-403
- 前置条件: 已有版本+反馈数据（TC-001/003 数据）
- 测试步骤:
  1. 教师身份 GET `/api/feedback/records/`，分别按 `course`、`creator`、`milestone`、`question` 过滤
- 预期结果: 各维度过滤生效；返回结构含版本时间线（按 version 升序）及每版本关联的 AI 反馈记录
- 类型: 正常

### TC-009: 非授权角色访问被拒
- 关联验收标准: PRD §2.4 AC-402、NFR-2
- 前置条件: 有 Student / Teacher / Researcher 三类账号
- 测试步骤:
  1. Student 身份 GET `/api/feedback/records/`
  2. Teacher / Researcher 身份 GET 同一地址
- 预期结果: Student 返回 403（无权限）；Teacher / Researcher 返回 200
- 类型: 异常

### TC-010: 查询无过滤参数兜底
- 关联验收标准: PRD §2.4 AC-401（过滤为可选）
- 前置条件: 教师身份
- 测试步骤:
  1. GET `/api/feedback/records/`（不带任何过滤参数）
- 预期结果: 按实现返回（全部记录或 400 提示），不得 500；响应结构稳定
- 类型: 边界

### TC-011: 上报接口身份与归属校验
- 关联验收标准: PRD §3 安全（上报 API 校验请求者身份与学生归属）
- 前置条件: 学生 A 与 学生 B 账号
- 测试步骤:
  1. 学生 A 尝试以学生 B 的 `submission_id` 上报
  2. 学生 A 以自己 `submission_id` 上报
- 预期结果: 越权上报被拒（403/400）；本人上报成功
- 类型: 异常

### TC-012: 存量数据流回归（FeedbackInitialResponse 不变）
- 关联验收标准: PRD §3 兼容性（现有数据流保持不变）
- 前置条件: 已有旧版接口/组件行为基线
- 测试步骤:
  1. 学生提交初始回答（`get_or_create` 路径）
  2. 触发一次 AI 反馈
  3. 检查 `FeedbackInitialResponse` 行为与前端展示
- 预期结果: 初始回答收集与前端渲染行为与改动前一致；旧表数据无破坏
- 类型: 回归

## 端到端场景

### E2E-001: 反思写作「修改→生成→落库」全链路
- 来源: PRD §2.1/2.2 主链路 + 记忆 INIT-004（/api/feedback/ 路由）
- 链路: 前端 `form-field-feedback-renderer.tsx`（getFeedback 携带 submission_id/question）→ `/api/feedback/` → ChatGPT 生成 + `create_feedback_version_and_record` 事务 → PostgreSQL 版本快照 + AI 反馈记录
- 关键断言:
  - 响应含反馈内容与 6 阶段评分明细（basic/advanced）
  - DB 中 version 递增、record.version_id 关联正确、usage/tokens/耗时字段非空
- 风险关注点: 事务原子性（AI 失败是否整体回滚）；请求参数传递是否完整

### E2E-002: Playtest「LightRAG 响应→前端上报」全链路
- 来源: PRD §2.2 AC-204（前端上报，不改 NGINX）+ 澄清 Q1
- 链路: 前端 `form-field-playtest-feedback-renderer.tsx` → LightRAG（NGINX 代理直连，不变）→ 收到响应后 `createFeedbackRecord`（含 idempotency_key）→ `/api/feedback/records/` → 事务落库
- 关键断言: 上报成功后 DB 出现 1 版本 + 1 记录；`idempotency_key` 唯一；LightRAG 代理链路未被改动
- 风险关注点: 前端上报失败时的用户提示；幂等键生成位置（每次生成会话唯一）

### E2E-003: 幂等重试防重（网络抖动场景）
- 来源: RISK-DA006 + 记忆 INIT-009（历史缺陷模式）
- 链路: 模拟网络重试 → 相同 idempotency_key 重复 POST `/api/feedback/records/`
- 关键断言: 两条请求后 DB 仅 1 条记录；返回体均为同一条记录数据
- 风险关注点: 并发重复提交下的竞态（DB 唯一约束兜底）

### E2E-004: 教师/研究者查询时间线
- 来源: PRD §2.4 + 记忆 INIT-003（角色授权）
- 链路: 教师登录 → GET `/api/feedback/records/?course=..&creator=..&milestone=..&question=..` → 版本时间线（v1→v2→v3 升序）+ 各版本关联 AI 反馈
- 关键断言: 过滤生效；时间线顺序正确；每版本关联反馈可回溯；Student 访问被 403
- 风险关注点: 大数据量下的索引命中（creator+question+created_at）；N+1 查询

## 验收追踪设计

| 验收项 | 对应测试用例 | 对应 E2E 场景 | 后续证据要求 |
|-------|-------------|--------------|-------------|
| AC-101（点击生成快照版本） | TC-001, TC-003 | E2E-001, E2E-002 | 报告中给出请求日志 + DB 版本记录数 |
| AC-102（版本字段完整） | TC-002 | E2E-001 | 报告中给出查询结果/日志 |
| AC-103（版本号递增） | TC-001 | E2E-001 | 报告中给出 version 序列 |
| AC-104（草稿不触发） | TC-004 | — | 报告中给出无 submission_id 的行为结论 |
| AC-201（每生成必记录） | TC-001, TC-003, TC-005 | E2E-001, E2E-002, E2E-003 | 报告中给出记录数与幂等去重结论 |
| AC-202（记录字段：评分/策略/模型/Token/耗时） | TC-001, TC-003 | E2E-001, E2E-002 | 报告中给出字段清单核对结论 |
| AC-203（记录关联版本） | TC-001, TC-003 | E2E-001, E2E-002 | 报告中给出 version_id 关联核对 |
| AC-204（Playtest 前端上报） | TC-003 | E2E-002 | 报告中给出前端→Django 请求日志 |
| AC-205（反思写作后端直接落库） | TC-001 | E2E-001 | 报告中给出 /api/feedback/ 请求日志 |
| AC-301（历史回填 version 1） | TC-007 | — | 报告中给出回填前后计数对比 |
| AC-302（回填版本无关联反馈） | TC-007 | — | 报告中给出关联查询结果 |
| AC-303（回填幂等） | TC-007 | — | 报告中给出重跑计数结论 |
| AC-401（维度过滤查询） | TC-008, TC-010 | E2E-004 | 报告中给出过滤响应片段 |
| AC-402（教师/研究者专属） | TC-009 | E2E-004 | 报告中给出 403 响应日志 |
| AC-403（版本时间线+关联反馈） | TC-008 | E2E-004 | 报告中给出时间线响应片段 |
| AC-404（无前端页面） | —（仅实现核对） | — | 静态核对：无新增前端查询页面 |

## 通用检查项

| 编号 | 检查项 | 说明 |
|------|--------|------|
| CHK-1 | 编译检查 | 后端 `py_compile` + `manage.py check`；前端 `tsc --noEmit` |
| CHK-2 | 代码规范（CORR-001） | 新增/修改文件注释抽查：全部英文 |
| CHK-3 | SQL 安全 | 查询均为 ORM 参数化，无字符串拼接；动态过滤白名单校验 |
| CHK-4 | 空值/边界防护 | submission_id 缺失、过滤参数缺失、空答案等边界不 500 |
| CHK-5 | 迁移一致性 | `makemigrations --check --dry-run` 无变化 |
| CHK-6 | 关键链路回归 | 存量 `FeedbackInitialResponse` 数据流与前端展示不变（TC-012） |

## 遗留风险

- **R1**: Playtest 上报依赖前端正确生成唯一 `idempotency_key`，若前端 Bug 导致重复 key 会误去重 → E2E-003 覆盖
- **R2**: 并发同键首次提交的竞态窗口 → 依赖 DB 唯一约束兜底，E2E-003 验证
- **R3**: 查询接口数据量大时性能 → 索引设计核对（NFR-1）+ E2E-004 观察
