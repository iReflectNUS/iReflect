# 技术设计 — AI反馈记录与修改版本追踪（科研数据持久化）

> req_id: 20260818-反馈修改追踪 | 阶段: DESIGN_ARCHITECT | Agent: 03-design-agent
> 输入: `03_clarify_prd-refined.md` + 代码探索结果

## 1. 需求摘要

为科研数据收集，持久化记录：① 学生每次点击"Generate Feedback"时的**答案快照版本**（version 1→2→3...）；② 每次 AI 生成的**反馈记录**（评分、内容、策略、元数据）。AI 反馈关联到触发时的答案版本，形成「修改-反馈」时间线。仅后端存储 + 教师/研究者查询 API，不做前端展示。

**三条已澄清决策**：
1. Playtest 反馈（LightRAG）由**前端收到响应后上报 Django**，NGINX 链路不变
2. 答案版本在**点击 Generate Feedback 时快照**
3. `FeedbackInitialResponse` 历史数据**回填为 version 1**

## 2. 现有代码分析

### 2.1 相关类和模块

| 模块 | 文件 | 关键内容 |
|------|------|---------|
| 反馈模型 | `backend/pigeonhole/feedback/models.py` | `FeedbackInitialResponse`：course/milestone/template/creator/name/question/initial_response/genre/mechanic，`unique_together` 限制单条 |
| 反馈视图 | `backend/pigeonhole/feedback/views.py` | `FeedbackView`（POST /feedback/）、`FeedbackInitialResponseView`（POST /feedback/initial-response/） |
| 反馈逻辑 | `backend/pigeonhole/feedback/logic.py` | `askChatGPTOriginal`（Basic）、`askChatGPT`（Advanced: 3次评分取平均+结构化反馈）、`createFeedbackInitialResponseIfNotExists` |
| 反馈序列化 | `backend/pigeonhole/feedback/serializers.py` | `PostFeedbackSerializer`（仅 content）、`PostFeedbackInitialResponseSerializer` |
| 前端反馈 | `frontend/src/components/form-field-feedback-renderer.tsx` | 反思写作反馈渲染：getFeedback(content) → tryStoreInitialResponse |
| 前端Playtest | `frontend/src/components/form-field-playtest-feedback-renderer.tsx` | Playtest反馈渲染：fetch /api/playtest/ → tryStoreInitialResponse |
| API 服务 | `frontend/src/redux/services/feedback-api.ts` / `playtest-api.ts` | RTK Query 端点 |
| 类型定义 | `frontend/src/types/feedback.ts` | `FeedbackData`、`PlaytestResponseData`、`FeedbackInitialResponsePostData` |
| 上下文 | `frontend/src/contexts/feedback-data-collection-provider.tsx` | `FeedbackContext`: `{testMode, submissionId}` |
| 权限 | `backend/pigeonhole/users/middlewares.py` | `check_account_access(AccountType.STANDARD/EDUCATOR/ADMIN)` |

### 2.2 现有模式识别

- **上报模式**：前端已有 `tryStoreInitialResponse`（RTK mutation → POST initial-response）的完整链路，新增反馈记录可复用该模式
- **事务模式**：`createFeedbackInitialResponseIfNotExists` 使用 `@transaction.atomic` + `get_or_create`
- **权限模式**：`check_account_access` 装饰器，`submission_id` → `CourseSubmission` → `coursemembership_set.get(user=requester)` 归属校验
- **A/B 分流**：`requester.id % 2 == 0` → Basic，否则 Advanced
- **策略差异**：Basic 返回纯文本 markdown；Advanced 内部有结构化 `Grade`/`Feedback`（pydantic）对象，但对外仅返回 markdown

## 3. 技术方案

### 3.1 整体方案

新增两张表 + 一个查询 API + 反思路径后端直接落库 + Playtest 路径前端上报：

```
学生点击 Generate Feedback
        │
        ├── 反思写作(Feature 1):  POST /api/feedback/  ←── 后端落库
        │     FeedbackView 扩展入参(submission_id, question)
        │     → 事务内创建 FeedbackAnswerVersion + AIFeedbackRecord
        │
        └── Playtest(Feature 2): 前端 fetch /api/playtest/ (LightRAG, 不改)
              → 收到响应后 → POST /api/feedback/records/ ← 前端上报
              → 后端创建 FeedbackAnswerVersion + AIFeedbackRecord

教师/研究者:  GET /api/feedback/records/?course=&creator=&milestone=&question=
              → 返回版本时间线 + 每版本关联的 AI 反馈
```

### 3.2 数据库设计

新增两张表（`@changelog` 注释规范，遵循 existing `TimestampedModel` 模式）：

**表 1: `FeedbackAnswerVersion`（答案版本表）**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | AutoField | 主键 |
| course | FK → Course | 课程 |
| milestone | FK → CourseMilestone (null) | 里程碑 |
| template | FK → CourseMilestoneTemplate (null) | 模板 |
| creator | FK → CourseMembership (null) | 学生 |
| name | CharField | 模板名称快照 |
| question | CharField | 问题文本 |
| answer_content | TextField | 答案快照（触发时内容） |
| version_number | PositiveIntegerField | 版本号（同组合内从 1 递增） |
| genre | TextField (null) | Playtest 专用 |
| mechanic | TextField (null) | Playtest 专用 |
| created_at / updated_at | DateTime | 时间戳 |

**表 2: `AIFeedbackRecord`（AI 反馈记录表）**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | AutoField | 主键 |
| version | FK → FeedbackAnswerVersion | 关联答案版本（CASCADE） |
| feedback_type | CharField | `REFLECTION` / `PLAYTEST` |
| strategy | CharField | `BASIC` / `ADVANCED` / `PLAYTEST` |
| score_json | JSONField (null) | 6阶段评分明细（Advanced 可用；Basic/Playtest 为 null） |
| feedback_content | TextField | AI 反馈 markdown 全文 |
| model_version | CharField | 模型标识（gpt-4o / lightrag-hybrid） |
| token_usage_json | JSONField (null) | Token 用量（若有） |
| latency_ms | FloatField (null) | 生成耗时（毫秒） |
| created_at / updated_at | DateTime | 时间戳 |

**索引设计**：
- `FeedbackAnswerVersion`: `unique_together (course, milestone, template, creator, question, version_number)` → 保证版本号唯一
- `AIFeedbackRecord`: 普通 FK 索引即可

> 版本号递增逻辑：查询该 (course, milestone, template, creator, question) 组合下最大 version_number + 1。为防并发，放在 `@transaction.atomic` + `select_for_update` 或依赖 unique_together 捕获冲突重试。

### 3.3 接口设计

**A. 修改现有接口 — POST `/api/feedback/`（反思写作）**

- 入参扩展: `{content, submission_id, question}`（`submission_id`/`question` 用于版本落库；`content` 即答案快照）
- 响应不变: `{annotated_content: '', feedback: <markdown>}`
- 逻辑变化: 生成反馈后，在事务内创建 `FeedbackAnswerVersion` + `AIFeedbackRecord`
  - `strategy`: `requester.id % 2 == 0 ? BASIC : ADVANCED`
  - `score_json`: Advanced 模式由内部 `Feedback` 结构化对象提取；Basic 模式为 `null`
  - `token_usage_json`: 汇总各次调用 `query.usage`；`latency_ms`: 统计耗时
- 权限: 保持 `check_account_access(STANDARD, EDUCATOR, ADMIN)` + submission 归属校验（复用 `createFeedbackInitialResponseIfNotExists` 的校验模式）

**B. 新增接口 — POST `/api/feedback/records/`（Playtest 上报）**

- 入参: `{submission_id, question, initial_response, feedback_content, genre, mechanic}`
- 行为: 前端收到 LightRAG 响应后调用；后端创建 `FeedbackAnswerVersion`（genre/mechanic 同步） + `AIFeedbackRecord`（feedback_type=PLAYTEST, strategy=PLAYTEST）
- 权限: 同上（复用 submission 归属校验）
- 幂等: 可选 `idempotency_key`（前端每次生成生成 UUID）防止重试产生重复记录 [待确认，见 RISK]

**C. 新增接口 — GET `/api/feedback/records/`（教师/研究者查询）**

- 权限: `check_account_access(AccountType.EDUCATOR, AccountType.ADMIN)`（仅教师/研究者）
- Query 参数: `course`（必填）、`creator`（学生 CourseMembership id，可选）、`milestone`（可选）、`question`（可选）
- 响应结构:
```json
{
  "records": [
    {
      "creator": {"id": 1, "name": "..."},
      "question": "What did you learn?",
      "versions": [
        {
          "version_number": 1,
          "answer_content": "初稿...",
          "created_at": "...",
          "feedback_records": [
            {
              "feedback_type": "REFLECTION",
              "strategy": "ADVANCED",
              "score_json": {"stage_1_score": 2, "...": "...", "total": 10.5},
              "feedback_content": "**Stage 1...**",
              "model_version": "gpt-4o",
              "created_at": "..."
            }
          ]
        }
      ]
    }
  ]
}
```
- 不分页或简单 limit 参数 [待确认]

**D. 数据回填 — management command 或 data migration**

- 遍历现有 `FeedbackInitialResponse` → 创建 `FeedbackAnswerVersion`（version_number=1, answer_content=initial_response, genre/mechanic 同步）
- 无关联 AIFeedbackRecord
- 幂等: 以唯一约束存在性判断，可重复执行

### 3.4 核心逻辑

**版本号生成（共享函数）**：
```python
@transaction.atomic
def create_feedback_version_and_record(
    submission, requester_membership, question, answer_content,
    feedback_type, strategy, feedback_content, score_json=None,
    genre=None, mechanic=None, model_version=None, token_usage=None, latency_ms=None,
):
    # 1. 锁定该组合的行或查询最大版本号
    max_version = FeedbackAnswerVersion.objects.filter(
        course=..., milestone=..., template=..., creator=..., question=question
    ).aggregate(m=Max("version_number"))["m"] or 0
    version = FeedbackAnswerVersion.objects.create(
        ..., version_number=max_version + 1, ...
    )
    record = AIFeedbackRecord.objects.create(
        version=version, feedback_type=..., strategy=..., ...
    )
    return version, record
```

**反思写作落库（FeedbackView.post 改造）**：
- `serializer.validated_data` 增加 `submission_id`、`question`
- 先做 submission 归属校验（复用现有模式）
- 生成反馈（Basic/Advanced 按 ID 奇偶）
- Advanced 时从内部 `Feedback` 对象提取 score_json + 汇总 token usage
- 调共享函数落库 → 返回

**Playtest 上报（新增 FeedbackRecordView.post）**：
- 校验 submission 归属
- 调共享函数落库（feedback_type=PLAYTEST, strategy=PLAYTEST, score_json=null）

### 3.5 多端架构设计

#### 3.5.1 涉及端清单

| 端 | 技术栈 | 项目目录 | 主要改动 |
|----|--------|---------|---------|
| 后端 | Django + DRF | `backend/pigeonhole/feedback/` | models（2新表）、views（改造+2新接口）、serializers、logic、migrations、management command |
| 前端 | Next.js + RTK Query | `frontend/src/` | feedback-api（入参扩展+新增端点）、playtest 组件（上报）、feedback 组件（入参） |

> 注: 本次设计采用单 Agent 完成——两端接口契约耦合度高（同一事务语义横跨前后端），统一视角设计可保证一致性。涉及端为 2，但改动集中，Teams 并行收益有限。

#### 3.5.2 前后端接口契约

| API | Method | 请求 | 响应 | 端 |
|-----|--------|------|------|-----|
| `/api/feedback/` | POST | `{content, submission_id, question}` | `{annotated_content, feedback}`（不变） | FE→BE |
| `/api/feedback/records/` | POST | `{submission_id, question, initial_response, feedback_content, genre?, mechanic?}` | `{created: bool}` | FE→BE |
| `/api/feedback/records/` | GET | `?course=&creator=&milestone=&question=` | `{records: [...]}` | BE→教师/研究者 |
| `/api/playtest/` | POST | 不变 | 不变 | FE→NGINX→LightRAG |

#### 3.5.3 各端技术方案

**后端（Django）**：
- 2 个新模型继承 `TimestampedModel`
- `FeedbackView` 扩展入参 + 落库逻辑（后端主导，保证 Advanced 结构化评分不丢失）
- 新增 `FeedbackRecordView`（POST 上报 + GET 查询，可拆两个 View 或一个 View 两个方法）
- management command: `backfill_feedback_versions`
- 序列化器: `PostFeedbackRecordSerializer`、`FeedbackRecordQuerySerializer`
- 迁移文件 + 回填脚本

**前端（Next.js）**：
- `feedback-api.ts`:
  - `getFeedback` mutation 入参增加 `submission_id`, `question`
  - 新增 `createFeedbackRecord` mutation（POST /api/feedback/records/）
- `form-field-feedback-renderer.tsx`: `getFeedback` 调用增加 `submission_id`（来自 FeedbackContext）和 `question`
- `form-field-playtest-feedback-renderer.tsx`: 收到 `raw.response` 后，调用 `createFeedbackRecord` 上报（复用已有 genre/mechanic/initial_response 变量）
- `types/feedback.ts`: 新增 `FeedbackRecordPostData` 类型

#### 3.5.4 跨端数据流

```
[反思写作]
FE 点击按钮 → getFeedback({content, submission_id, question}) → BE 校验+生成AI反馈
    → BE 事务落库(version+record) → BE 返回 feedback → FE 展示
    → FE 照旧 tryStoreInitialResponse（初始回答收集逻辑不变）

[Playtest]
FE 点击按钮 → fetch /api/playtest/(query, mode) → LightRAG 返回 response
    → FE 展示 response
    → FE createFeedbackRecord({submission_id, question, initial_response, feedback_content, genre, mechanic})
    → BE 校验+事务落库(version+record) → FE 照旧 tryStoreInitialResponse
```

### 3.6 经验记忆参考

- 记忆 INIT-004（API 索引）: 现有 `/api/feedback/`、`/api/playtest/` 路径约定，新增端点沿用 `/api/feedback/` 前缀
- 记忆 INIT-005（数据模型）: 课程/里程碑/模板/提交/成员模型层级（Course→CourseMilestone→CourseMilestoneTemplate→CourseSubmission→CourseSubmissionComment）
- 记忆 INIT-006（权限体系）: AccountType（ADMIN/EDUCATOR/STANDARD）与 Role（CO_OWNER/INSTRUCTOR/STUDENT）双轨；本需求查询接口用 AccountType 控制
- 代码质量标准（always-applied）: `@changelog` 头注释、参数化查询、函数 ≤40 行、复用优先

## 4. 影响评估

| 维度 | 影响 |
|------|------|
| 数据库 | 新增 2 表；`FeedbackInitialResponse` 表保留不动（历史兼容） |
| 后端 | `feedback` app 4 个文件改动 + 2 个新文件 + 1 migration + 1 management command |
| 前端 | 3 个文件改动（feedback-api、types、2 个反馈组件） |
| API 契约 | `/api/feedback/` 入参扩展（向后兼容：新增必填字段需前端同步改） |
| NGINX/LightRAG | 无改动 |
| 权限 | 查询接口收紧为 EDUCATOR/ADMIN |
| 数据量 | 每次生成反馈新增 2 行记录；预计每学生每问题数十行，量级可控 |

## 5. 技术决策记录 (ADR)

| ADR | 决策 | 理由 | 备选 |
|-----|------|------|------|
| ADR-1 | 反思写作反馈由**后端直接落库** | Advanced 模式有结构化评分对象，后端落库可保存 score_json；避免前端解析 markdown 重构评分（不可靠） | 前端上报（丢结构化评分） |
| ADR-2 | Playtest 反馈由**前端上报**（已澄清） | LightRAG 绕过 Django，前端收到响应后有完整数据；不改 NGINX | Django 代理（改动大） |
| ADR-3 | **两张独立表**（版本表+反馈表，FK 关联） | 一个版本可能关联多次反馈（未来）？——当前 1:1，但分离利于扩展与查询 | 单表 type 区分 |
| ADR-4 | version_number 同组合内递增 | 满足"首次→末次"追踪；回填历史为 version 1 | 全局递增（难以对比同学生演进） |
| ADR-5 | 查询接口按 AccountType（EDUCATOR/ADMIN）控制 | 教师/研究者语义对应系统 AccountType，实现简单 | Role 控制（更细但复杂） |

## 6. 风险评估

### 6.1 风险清单

| ID | 类别 | 严重度 | 概率 | 描述 | 策略 | 应对措施 | 状态 |
|----|------|--------|------|------|------|---------|------|
| RISK-DA001 | integration | high | possible | `/api/feedback/` 入参扩展（新增必填 submission_id/question），前端未同步改将导致 400 | avoid | 前端组件与后端同步修改；开发顺序：先后端后前端 | open |
| RISK-DA002 | requirement | medium | likely | Basic 模式（偶数 ID）只返回纯文本反馈，score_json 无结构化数据，科研评分分析不完整 | mitigate | score_json 允许 null；Basic 文本中保留评分段落（现有 prompt 已包含）；未来可升级 Basic 策略 | open |
| RISK-DA003 | performance | low | unlikely | 版本号递增在并发下可能冲突 | mitigate | unique_together + 捕获 IntegrityError 重试；单用户场景并发极低 | open |
| RISK-DA004 | technical | low | possible | token_usage 需从多次 OpenAI 调用聚合，改造成本 | mitigate | 仅记录累计 usage；无法聚合时置 null，不阻塞主流程 | open |
| RISK-DA005 | security | medium | possible | 查询接口若权限校验不严会泄露学生文本 | avoid | `check_account_access(EDUCATOR, ADMIN)` + course 成员/角色二次校验 | open |
| RISK-DA006 | requirement | medium | possible | 上报接口（Playtest）重复提交产生重复版本（网络重试） | mitigate | 前端携带 idempotency_key（UUID），后端唯一约束去重，重复返回已有记录 | closed（用户已确认） |
| RISK-DA007 | technical | medium | possible | 回填脚本与现有 `unique_together` 冲突/部分失败 | mitigate | 幂等设计（存在性检查）+ 事务批量 + 可重跑 | open |

### 6.2 风险矩阵

```
              概率
           likely | possible | unlikely
high    |         |   🔴DA1  |
medium  | 🟡DA2  |   🟡DA5  |
        |        |   🟡DA6  |
        |        |   🟡DA7  |
low     |         |   🟢DA4  |  🟢DA3
```

### 6.3 需要用户决策的风险

> ⚠️ 以下风险需要您的确认才能确定最终方案：

**RISK-DA006** — Playtest 上报接口是否需要幂等保护？
- **影响**: 前端网络重试/双击可能导致同一答案生成多条重复版本记录，污染科研数据
- **建议**: 前端每次生成携带 `idempotency_key`（UUID），后端唯一约束去重
- **备选**:
  1. 不引入幂等 — 依赖前端逻辑防重（简单，但有重复风险）
  2. 幂等键 — 后端唯一约束，重复提交返回已有记录（更可靠，增加少量实现成本）
- **请选择处理方式**: 采纳建议 / 选择备选 / 提供其他方案

### 6.4 已缓解的风险

| ID | 措施 |
|----|------|
| RISK-DA001 | 前后端同步修改 + 明确开发顺序 |
| RISK-DA002 | score_json 允许 null，Basic 文本含评分段落 |
| RISK-DA003 | unique_together + 重试 |
| RISK-DA004 | 聚合或置 null |
| RISK-DA005 | 双层权限校验 |
| RISK-DA007 | 幂等回填脚本 |

## 7. 开放问题（设计阶段遗留）

- [x] RISK-DA006: 用户已确认采纳幂等键方案（备选 2）
- [ ] 查询接口是否需要分页？默认 limit 值？
- [ ] 版本号是否用 `select_for_update` 锁行还是依赖唯一约束重试？（实现细节，Phase 09/10 定）

## 完成条件

- ✅ tech-design.md 已生成（含 §6 风险评估）
- ✅ 八维度扫描完成（7 项风险，含 1 项 high 待处理）
- ✅ high 风险已标注（RISK-DA001 通过开发顺序规避）
- ✅ risks.json 待更新（下一步）
- ✅ 风险即时报备（RISK-DA006 pending 需用户决策）
