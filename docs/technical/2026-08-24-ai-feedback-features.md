# iReflect AI 反馈模块技术文档

> 覆盖两个已合入 `feature/chuckyang123/20260818/ai-feedback-version-tracking` 分支的 feature：
>
> 1. **反馈修改追踪**（AI Feedback Answer Version Tracking）— commit `0a9347a`
> 2. **Playtest 评分展示控制**（Course-level control for playtest AI score visibility）— commit `c95a5da`
>
> 本文档以「读懂代码」为目标：列出每个改动的文件、改动点，并解释为什么这样做。建议配合 `git show <commit> -- <file>` 查看逐行 diff。

---

## 1. 总览

| Feature | 解决的问题 | 核心思想 | 提交 |
|---------|-----------|---------|------|
| 反馈修改追踪 | 学生反复修改答案触发 AI 反馈，但系统只存最后一次，无法还原修改轨迹 / 做研究分析 | 每次生成反馈时**快照答案版本**，并持久化一条**反馈记录**（含分数、token、延迟） | `0a9347a` |
| Playtest 评分展示控制 | 学生能看到 playtest AI 数字评分，教师希望能按课程控制学生是否看到 | 课程级开关 `showAiScore`（默认关），前端**剥离 Markdown 中的分数块** + 后端**裁剪 score_json** 双保险 | `c95a5da` |

两个 feature 共用同一套新表结构（`FeedbackAnswerVersion` / `AIFeedbackRecord`）：第一个 feature 建立数据管道，第二个 feature 在管道响应端做可见性控制。

---

## Part A. 反馈修改追踪（Feature 1）

### A.1 功能目标

- 每次触发 AI 反馈时，把学生当时的答案保存为一个「版本快照」，形成修改时间线。
- 每条 AI 反馈本身也落库：类型（reflection / playtest）、策略、分数 JSON、token 用量、延迟、模型版本。
- **幂等**：前端网络重试不会产生重复记录。
- 教师 / 管理员可通过查询接口按课程、学生、里程碑、问题拉取版本时间线。

### A.2 数据模型（`backend/pigeonhole/feedback/models.py`）

新增两张表（迁移 `0003_feedbackanswerversion_aifeedbackrecord.py`）：

```
FeedbackInitialResponse (原有, 1 份答案)
        │
        ▼ 触发 AI 反馈时
FeedbackAnswerVersion  (1 学生 × 1 问题 × N 次修改 → N 个版本)
        │ 1 ──── N
AIFeedbackRecord       (每个版本可产生 1 条或多条 AI 反馈记录)
```

**`FeedbackAnswerVersion`** — 答案版本表：

| 字段 | 说明 |
|------|------|
| `course / milestone / template / creator` | 归属课程、里程碑、模板、学生成员身份（`CourseMembership`） |
| `name` | 快照模板名（`submission.template.__str__()`） |
| `question` | 触发反馈的问题标识 |
| `answer_content` | **本次触发时的答案快照**（核心） |
| `version_number` | 版本号，从 1 递增 |
| `genre / mechanic` | playtest 上下文（可选） |

关键约束 `Meta.unique_together = (course, milestone, template, creator, question, version_number)`：版本号在「同一学生同一问题」维度内唯一，保证时间线可重建。

**`AIFeedbackRecord`** — AI 反馈记录表：

| 字段 | 说明 |
|------|------|
| `version` | 外键 → 触发本次反馈的答案版本 |
| `feedback_type` | `REFLECTION` / `PLAYTEST` |
| `strategy` | `BASIC` / `ADVANCED` / `PLAYTEST`（LightRAG） |
| `score_json` | 数字评分 JSON（**Feature 2 的裁剪对象**） |
| `feedback_content` | 完整反馈文本 |
| `model_version` | 模型版本 |
| `token_usage_json` | token 用量 |
| `latency_ms` | 延迟 |
| `idempotency_key` | **UUID 唯一索引** → 幂等去重（对应风险 RISK-DA006） |

### A.3 API 设计（`feedback/urls.py` + `feedback/views.py`）

路由：`records/` → `FeedbackRecordView`（DRF `APIView`）。

**POST `records/`** — 前端上报 AI 反馈（playtest 路径由前端直接调用；reflection 路径复用旧的 `/feedback/` 生成接口）：
1. `PostFeedbackRecordSerializer` 校验入参（`submission_id`、`question`、`initial_response`、`feedback_content`、`idempotency_key`、`genre`、`mechanic`）。
2. 调用 `create_feedback_version_and_record(...)` 落库（见 A.4）。
3. 返回 `{ record, version }` 两个 JSON（`ai_feedback_record_to_json` / `feedback_answer_version_to_json`）。

> 注意：POST 允许 `STANDARD / EDUCATOR / ADMIN` 三种角色。Feature 2 在此方法的响应处加了 `include_score` 逻辑（见 B.4）。

**GET `records/`** — 查询版本时间线（仅 `EDUCATOR / ADMIN`）：
- 支持 `course_id`、`user_id`、`milestone_id`、`question` 过滤。
- `select_related + prefetch_related` 避免 N+1。
- 返回结构：每个版本 + 其下 `feedback_records` 列表，按 `(creator, question, version_number)` 排序 → 直接还原修改时间线。

### A.4 核心业务逻辑（`feedback/logic.py`）

`create_feedback_version_and_record(...)`（约 496–574 行），按执行顺序拆解：

```python
# 1) 幂等去重：同 idempotency_key 直接返回已有记录
if idempotency_key:
    existing = AIFeedbackRecord.objects.filter(idempotency_key=idempotency_key).first()
    if existing is not None:
        return existing

# 2) 校验：submission 必须存在，requester 必须是该课程成员
submission = CourseSubmission.objects.select_related("course", "milestone", "template").get(id=submission_id)
requester_membership = submission.course.coursemembership_set.get(user=requester)

# 3) 版本号 = 同维度内 Max(version_number) + 1
max_version = FeedbackAnswerVersion.objects.filter(
    course=..., milestone=..., template=..., creator=..., question=question
).aggregate(max_version=Max("version_number"))["max_version"]
version_number = (max_version or 0) + 1

# 4) 创建版本快照 + 反馈记录（同一事务，整体成功或整体回滚）
version = FeedbackAnswerVersion.objects.create(...)
record = AIFeedbackRecord.objects.create(version=version, ...)
return record
```

设计要点：
- **事务**：`@transaction.atomic` 包住整个创建过程，任一步失败全部回滚，不会出现「有版本无记录」的脏数据。
- **版本号并发安全**：`unique_together` 兜底约束，极端并发下唯一索引冲突会阻止重复版本号。
- **幂等优先级最高**：网络重试（前端 `crypto.randomUUID()` 每次生成新 key）不产生重复数据。

另外两个 JSON 序列化函数：
- `ai_feedback_record_to_json(record, include_score=True)` — Feature 2 增加了 `include_score` 参数（见 B.4）。
- `feedback_answer_version_to_json(version)` — 输出版本快照字段。

### A.5 前端改动

| 文件 | 改动 |
|------|------|
| `src/redux/services/feedback-api.ts` | 新增 `createFeedbackRecord` mutation（POST `records/`）、`createInitialResponseIfNotExists` |
| `src/types/feedback.ts` | 新增 `FeedbackRecordRequest` 等类型定义 |
| `src/components/form-field-feedback-renderer.tsx` | **reflection 路径**：生成反馈时持久化 `initial_response`（`submission_id` + `question` + `initial_response`） |
| `src/components/form-field-playtest-feedback-renderer.tsx` | **playtest 路径**：生成反馈后调用 `createFeedbackRecord`，带 `idempotency_key: crypto.randomUUID()` 防重（见 A.6） |

### A.6 playtest 前端上报流程（playtest renderer）

```
用户点 Generate Feedback
  → fetch("/prompt_for_playtest_feedback.txt") + Genre/Mechanic 拼 prompt
  → POST 到 LightRAG nginx 接口（分数内嵌在返回的 Markdown 里）   ← 绕过 Django
  → setFeedback(原始 Markdown)                                     ← 见 Feature 2 的剥离逻辑
  → tryStoreInitialResponse(...)      保存首次答案
  → createFeedbackRecord({... idempotency_key: crypto.randomUUID()})  ← 幂等上报到 Django
```

### A.7 历史数据回填（`feedback/management/commands/backfill_feedback_versions.py`）

上线前已有历史 `FeedbackInitialResponse`（改造前只有「最后一次」）。回填命令把每条历史答案生成一个 `version_number=1` 的快照 + 一条记录（`feedback_content` 为空占位），保证研究查询接口从一开始就有完整时间线。执行方式：

```bash
python manage.py backfill_feedback_versions
```

---

## Part B. Playtest 评分展示控制（Feature 2）

### B.1 功能目标与产品决策

- **按课程**配置（不是全局、不是按用户）。
- 二选一：`分数 + 建议`（开关开）/ `仅建议`（开关关，隐藏所有数字，只留文字）。
- **默认关**（`show_ai_score = False`），即默认学生看不到分数。
- **对历史反馈立即生效**：开关是运行时判断，不依赖反馈产生时的设置。
- 教师端始终可见。

### B.2 架构背景：为什么需要「双保险」

关键事实：**playtest 反馈由 LightRAG 直接经 nginx 返回前端，完全绕过 Django**。分数内嵌在 Markdown 文本中：

```
**Score: [xx/100]**
**Breakdown of Key Ingredients:** 10 x [x/10]
**Genre & Mechanic Evaluation (Knowledge Graph Score):** [x/50]
**Professor Feedback:** (文字)          ← 学生实际需要看到的部分
**Final Summary:** (文字)
```

因此：
- **主控制点 = 前端**：拿到原始 Markdown 时直接剥离分数块（这是「页面不显示」的唯一可靠手段）。
- **防御兜底 = 后端**：POST `records/` 返回给学生的 `score_json` 置为 `null`，防止任何绕过前端的通道泄露分数（如开发者工具、未来新增客户端）。

### B.3 配置链路（前端开关 → DB → 生效）

```
课程创建/编辑表单（SwitchField）
   │  name = SHOW_AI_SCORE = "showAiScore"（camelCase，前端常量）
   ▼
courses-api PUT/POST /courses/{id}/
   ▼
courses/views.py  POST/PUT：show_ai_score=validated_data["show_ai_score"]
   ▼
courses/logic.py  create_course()/update_course() 签名新增 show_ai_score: bool
   ▼
courses/models.py CourseSettings.show_ai_score = BooleanField(default=False)   ← 迁移 0005
   ▼
GET /courses/{id}/ → course_to_json() 输出 SHOW_AI_SCORE = "show_ai_score"（snake_case）
   ▼
前端 useGetSingleCourseQuery → course.showAiScore
```

字段命名注意：**后端 DB/JSON 用 snake_case `show_ai_score`，前端常量用 camelCase `showAiScore`**，DRF 响应会自动转 camelCase。

### B.4 生效机制（双保险）

**① 前端剥离 — `stripScoresFromMarkdown(markdown)`**（`form-field-playtest-feedback-renderer.tsx`，46–71 行）

```ts
// 主路径：以 "**Professor Feedback:**" 为锚点，丢掉它之前的所有分数块
const professorAnchor = "**Professor Feedback:**";
const anchorIndex = markdown.indexOf(professorAnchor);
if (anchorIndex !== -1) return markdown.slice(anchorIndex).trim();

// 回退路径（锚点缺失，格式漂移 RISK-R1）：按行正则过滤
//   ^\*\*Score:\s*\[\d+\/\d+\]\*\*          → 总分行
//   ^[-*]\s+\*\*[^*]+:\*\*\s+\[\d+\/\d+\]    → 单项分（Specificity 等）
//   ^[-*]\s+\*\*\[\d+\/\d+\]\*\*             → 知识图谱分
//   ^\*\*(Breakdown of Key Ingredients|Genre & Mechanic Evaluation) → 分数区小标题
```

触发条件：

```ts
const shouldHideScores =
  accountType === AccountType.Standard && course?.showAiScore === false;

setFeedback(shouldHideScores ? stripScoresFromMarkdown(raw) : raw);
```

> 只有**学生**（`AccountType.Standard`）且课程关闭开关时才剥离；教师/管理员直接看原始 Markdown。

**② 后端裁剪 — `include_score`**（`feedback/views.py` `FeedbackRecordView.post`，151–165 行）

```python
include_score = True
if requester.account_type == AccountType.STANDARD:
    course_settings = getattr(record.version.course, "coursesettings", None)
    include_score = bool(course_settings is not None and course_settings.show_ai_score)

data = {
    "record": ai_feedback_record_to_json(record, include_score=include_score),
    "version": feedback_answer_version_to_json(record.version),
}
```

`ai_feedback_record_to_json(record, include_score)` 在 `include_score=False` 时把 `"score_json": None` 输出（`feedback/logic.py`）。

### B.5 角色 × 配置可见性矩阵

| 角色 | 课程开关 | playtest 页面 Markdown | POST records/ 响应 score_json |
|------|---------|----------------------|------------------------------|
| 学生（Standard） | 关（默认） | 仅文字建议，无任何数字 | `null` |
| 学生（Standard） | 开 | 分数 + 建议全显示 | 完整分数 |
| 教师 / 管理员 | 任意 | 分数 + 建议全显示 | 完整分数 |

### B.6 前端表单改动

- `src/constants/index.ts`：`SHOW_AI_SCORE = "showAiScore"`。
- `src/types/courses.ts`：课程设置类型新增 `[SHOW_AI_SCORE]: boolean`。
- `src/components/course-creation-form.tsx`：schema + `DEFAULT_VALUES.showAiScore: false`（新建课程默认隐藏）。
- `src/components/course-edit-form.tsx`：新增 **AI Feedback Settings** 区块（`Title order={4}`）+ `SwitchField` + Tooltip 说明：
  - 「When disabled, students only see the AI text suggestions and all numeric scores are hidden. Teachers always see the scores. This applies to existing feedback immediately.」

### B.7 后端改动文件一览

| 文件 | 改动 |
|------|------|
| `courses/models.py` | `CourseSettings.show_ai_score` 字段（默认 `False`） |
| `courses/migrations/0005_coursesettings_show_ai_score.py` | AddField 迁移 |
| `courses/serializers.py` | `show_ai_score` 字段（`required=False, default=False`） |
| `courses/logic.py` | `course_to_json` 输出 `SHOW_AI_SCORE`；`create_course` / `update_course` 新增 `show_ai_score` 参数并落库 |
| `courses/views.py` | POST/PUT 透传 `show_ai_score=validated_data["show_ai_score"]`（PUT 需 `Role.CO_OWNER`） |
| `feedback/logic.py` | `ai_feedback_record_to_json` 新增 `include_score` 参数 |
| `feedback/views.py` | `FeedbackRecordView.post` 按学生 + 开关决定 `include_score` |
| `pigeonhole/common/constants.py` | `SHOW_AI_SCORE = "show_ai_score"` |

---

## 2. 端到端时序（两个 feature 交汇处）

以「学生（隐藏分数）在 playtest 表单点 Generate Feedback」为例：

```
学生前端                            nginx/LightRAG              Django
   │                                     │                        │
   │── POST prompt+genre+mechanic ──────▶│                        │
   │◀── 原始 Markdown（含 Score 块）─────│                        │
   │                                     │                        │
   │── shouldHideScores? ────────────────┼────────────────────────┤
   │── stripScoresFromMarkdown ──────────┼────────────────────────┤
   │── setFeedback(仅文字) ──────────────┼────────────────────────┤
   │                                     │                        │
   │── POST /records/ (idempotency_key) ─┼───────────────────────▶│ create_feedback_version_and_record
   │◀── {record(score_json:null), version} ◀──────────────────────│ 版本号 Max+1 + 快照 + 记录
   │                                                              │ include_score=False（学生+开关关）
```

教师端同一次操作：不剥离 Markdown、`include_score=True`，全量数据落库不受影响。

---

## 3. 关键文件速查表

| 关注点 | 文件 |
|--------|------|
| 两张新表定义 | `backend/pigeonhole/feedback/models.py` |
| 版本创建核心逻辑 | `backend/pigeonhole/feedback/logic.py` → `create_feedback_version_and_record` |
| 上报/查询 API | `backend/pigeonhole/feedback/views.py` → `FeedbackRecordView`；`urls.py` → `records/` |
| 分数隐藏（前端主控） | `frontend/src/components/form-field-playtest-feedback-renderer.tsx` → `stripScoresFromMarkdown` / `shouldHideScores` |
| 分数隐藏（后端兜底） | `backend/pigeonhole/feedback/views.py` → `FeedbackRecordView.post`；`feedback/logic.py` → `ai_feedback_record_to_json` |
| 课程开关 | `courses/models.py` `CourseSettings.show_ai_score`；`courses/logic.py` `create/update_course`；`courses/views.py` |
| 课程表单开关 UI | `frontend/src/components/course-edit-form.tsx`（AI Feedback Settings 区块）；`course-creation-form.tsx` |
| 历史数据回填 | `backend/pigeonhole/feedback/management/commands/backfill_feedback_versions.py` |

## 4. 调试与验证

```bash
# 后端完整性
cd backend && python manage.py check && python manage.py makemigrations --check

# 前端类型与规范
cd frontend && npx tsc --noEmit && yarn lint

# 查询某个学生的版本时间线（教师视角）
GET /api/feedback/records/?course_id=1&user_id=2&milestone_id=3

# 回填历史数据（上线后只跑一次）
python manage.py backfill_feedback_versions
```

排障提示：
- 学生仍看到分数 → 检查课程 `CourseSettings.show_ai_score` 是否 `False`（默认），以及 `useGetSingleCourseQuery` 返回的 `showAiScore`。
- 接口返回 `score_json` 为 `null` → 是 Feature 2 兜底生效的正常现象；教师/管理员角色不受影响。
- 重复记录 → 检查前端是否每次都生成新的 `idempotency_key`；相同 key 第二次请求会被后端直接返回已有记录。

## 5. 提交记录

```
0a9347a feat: add AI feedback answer version tracking
c95a5da feat: add course-level control for playtest AI score visibility
```

相关需求文档：`docs/prd/20260818-反馈修改追踪.md`、`docs/prd/20260824-playtest评分展示控制.md`。
