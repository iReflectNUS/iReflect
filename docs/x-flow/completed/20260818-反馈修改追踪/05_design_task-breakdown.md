# 任务拆分 — AI反馈记录与修改版本追踪（科研数据持久化）

> req_id: 20260818-反馈修改追踪 | 阶段: DESIGN_TASK_SPLIT | Agent: 03-design-agent
> 输入: `04_design_tech-design.md`（含 RISK-DA006 用户决策：采纳幂等键方案）

## 架构任务（Phase 09: IMPL_ARCHITECT_BACKEND）

| # | 任务 | 优先级 | 复杂度 | 涉及模块 | 技术栈 | 状态 |
|---|------|--------|--------|---------|--------|------|
| A1 | 新增 `FeedbackAnswerVersion` 模型（答案版本表：course/milestone/template/creator/name/question/answer_content/version_number/genre/mechanic，`unique_together (course, milestone, template, creator, question, version_number)`） | P0 | M | `backend/pigeonhole/feedback/models.py` | Django ORM | ✅ 完成 |
| A2 | 新增 `AIFeedbackRecord` 模型（AI反馈记录表：version FK→FeedbackAnswerVersion CASCADE、feedback_type/strategy/score_json/feedback_content/model_version/token_usage_json/latency_ms） | P0 | M | `backend/pigeonhole/feedback/models.py` | Django ORM | ✅ 完成 |
| A3 | 生成迁移文件（2 新表 + 索引） | P0 | S | `backend/pigeonhole/feedback/migrations/` | Django migration | ✅ 完成 |
| A4 | 接口契约定义：`POST /api/feedback/` 入参扩展 `{content, submission_id, question}`；新增 `POST/GET /api/feedback/records/`（POST 入参含 `idempotency_key`） | P0 | S | `backend/pigeonhole/feedback/urls.py` + 前端 `feedback-api.ts` | DRF 契约 | ✅ 完成（路由注册移交 B5） |

## 业务任务（Phase 10: IMPL_CODE）

### 后端任务（Backend）

| # | 任务 | 优先级 | 复杂度 | 涉及模块 | 依赖 | 状态 |
|---|------|--------|--------|---------|------|------|
| B1 | 实现共享函数 `create_feedback_version_and_record`（事务内版本号 Max+1 递增 + 创建 version + record，幂等键去重） | P0 | M | `backend/pigeonhole/feedback/logic.py` | A1, A2 | ✅ 完成 |
| B2 | 改造 `FeedbackView`（反思写作）：入参扩展、submission 归属校验、生成反馈后事务落库（strategy 按 ID 奇偶、Advanced 提取 score_json + token usage + latency） | P0 | M | `backend/pigeonhole/feedback/views.py` | B1 | ✅ 完成 |
| B3 | 新增序列化器 `PostFeedbackRecordSerializer`（上报：submission_id/question/initial_response/feedback_content/genre/mechanic/idempotency_key）+ `FeedbackRecordQuerySerializer`（查询过滤） | P0 | S | `backend/pigeonhole/feedback/serializers.py` | A1, A2 | ✅ 完成 |
| B4 | 新增 `FeedbackRecordView`：POST（Playtest 上报，幂等去重）+ GET（EDUCATOR/ADMIN 查询版本时间线） | P0 | M | `backend/pigeonhole/feedback/views.py` | B1, B3 | ✅ 完成 |
| B5 | 路由注册 `/api/feedback/records/` | P0 | S | `backend/pigeonhole/feedback/urls.py` | B4 | ✅ 完成 |
| B6 | 回填 management command `backfill_feedback_versions`（遍历 FeedbackInitialResponse → version 1，幂等可重跑） | P1 | M | `backend/pigeonhole/feedback/management/commands/backfill_feedback_versions.py` | A1, A2 | ✅ 完成 |

### 前端任务（Frontend）— 依赖后端接口契约

| # | 任务 | 优先级 | 复杂度 | 涉及模块 | 依赖 | 状态 |
|---|------|--------|--------|---------|------|------|
| F1 | `feedback-api.ts`：`getFeedback` 入参增加 `submission_id`/`question`；新增 `createFeedbackRecord` mutation（POST records/，携带 `idempotency_key` UUID） | P0 | M | `frontend/src/redux/services/feedback-api.ts` | A4, B4 | ✅ 完成 |
| F2 | `types/feedback.ts`：新增 `FeedbackRecordPostData` 类型（含 idempotency_key） | P0 | S | `frontend/src/types/feedback.ts` | A4 | ✅ 完成 |
| F3 | `form-field-feedback-renderer.tsx`：`getFeedback` 调用传 `submission_id`（FeedbackContext）+ `question` | P0 | S | `frontend/src/components/form-field-feedback-renderer.tsx` | F1 | ✅ 完成 |
| F4 | `form-field-playtest-feedback-renderer.tsx`：收到 LightRAG 响应后调用 `createFeedbackRecord` 上报（genre/mechanic/initial_response + feedback_content + idempotency_key） | P0 | M | `frontend/src/components/form-field-playtest-feedback-renderer.tsx` | F1, F2 | ✅ 完成 |

## 依赖关系图

```
A1 ──┬──> A3 (migration)
A2 ──┘
A1/A2 ──> B1 ──> B2, B4
B3 ──> B4
B4 ──> B5
B6 (独立，依赖 A1/A2)
A4 ──> F1 ──> F3, F4
F2 ──> F4
```

## 执行顺序建议

1. **Phase 09**：A1 → A2 → A3 → A4（骨架 + 契约）
2. **Phase 10 后端**：B1 → B2 → B3 → B4 → B5 → B6
3. **Phase 10 前端**：F2 → F1 → F3 → F4（前端依赖后端契约，先后端后前端）

## 完成条件

- ✅ 架构/业务任务已区分（3 架构 + 6 后端业务 + 4 前端业务）
- ✅ 依赖关系明确（前后端契约解耦，后端优先）
- ✅ 风险已闭环（RISK-DA006 用户已确认采纳幂等键方案）
