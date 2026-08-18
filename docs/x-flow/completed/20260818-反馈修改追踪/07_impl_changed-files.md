# 变更文件清单 — AI反馈记录与修改版本追踪（科研数据持久化）

> req_id: 20260818-反馈修改追踪 | 阶段: IMPL_SELF_CHECK | Agent: 04-implement-agent
> 输入: `06_impl_log.md` + git status/diff

## 汇总

| 类别 | 文件数 | 说明 |
|------|--------|------|
| 后端核心（含 @changelog） | 6 | models/logic/views/serializers/urls + 回填命令 |
| 后端迁移/包文件 | 4 | migration 0003 + management 包结构 |
| 前端 | 5 | types/constants/api/组件 × 2 |
| 工程配置 | 2 | `.gitignore`、`yarn.lock` |

## 1. 后端新增文件

| 文件 | 类型 | @changelog | 说明 |
|------|------|-----------|------|
| `backend/pigeonhole/feedback/management/__init__.py` | ADD | 无（空文件） | management 包标记 |
| `backend/pigeonhole/feedback/management/commands/__init__.py` | ADD | 无（空文件） | commands 包标记 |
| `backend/pigeonhole/feedback/management/commands/backfill_feedback_versions.py` | ADD | ✅ v1.0.0 | 历史数据回填命令（幂等可重跑） |
| `backend/pigeonhole/feedback/migrations/0003_feedbackanswerversion_aifeedbackrecord.py` | ADD | 无（Django 自动生成） | 2 张新表迁移 |

## 2. 后端修改文件

| 文件 | 变更要点 | @changelog |
|------|---------|-----------|
| `backend/pigeonhole/feedback/models.py` | +`FeedbackAnswerVersion`、+`AIFeedbackRecord`（unique_together + idempotency_key 唯一约束） | ✅ v1.1.0 |
| `backend/pigeonhole/feedback/logic.py` | +`create_feedback_version_and_record`、usage/score 辅助函数；ChatGPT 系列改造为返回元组 | ✅ v1.1.0 |
| `backend/pigeonhole/feedback/views.py` | `FeedbackView` 入参扩展 + 事务落库；+`FeedbackRecordView`（POST 上报 / GET 查询） | ✅ v1.1.0 |
| `backend/pigeonhole/feedback/serializers.py` | `PostFeedbackSerializer` 扩展；+`PostFeedbackRecordSerializer`、+`FeedbackRecordQuerySerializer` | ✅ v1.1.0 |
| `backend/pigeonhole/feedback/urls.py` | +`api/feedback/records/` 路由 | ✅ v1.1.0 |

## 3. 前端修改文件（项目现状：frontend/src 不使用 @changelog）

| 文件 | 变更要点 | 说明 |
|------|---------|------|
| `frontend/src/types/feedback.ts` | +`FeedbackRecordPostData` / `FeedbackRecordResponseData`；`FeedbackData[RECORD_ID]`；`FeedbackPostData` 扩展 | 类型契约 |
| `frontend/src/constants/index.ts` | +`FEEDBACK_CONTENT` / `IDEMPOTENCY_KEY` / `RECORD_ID` | 常量扩展 |
| `frontend/src/redux/services/feedback-api.ts` | `getFeedback` 入参扩展；+`createFeedbackRecord` mutation | RTK Query 端点 |
| `frontend/src/components/form-field-feedback-renderer.tsx` | `getFeedback` 传 `submission_id` + `question` | 反思写作组件 |
| `frontend/src/components/form-field-playtest-feedback-renderer.tsx` | LightRAG 响应后调用 `createFeedbackRecord` 上报（含 idempotency_key） | Playtest 组件 |

## 4. 工程配置

| 文件 | 变更 |
|------|------|
| `.gitignore` | 忽略本地产物 |
| `frontend/yarn.lock` | LF→CRLF 行尾转换产生大 diff，无实质内容变更 |
| `frontend/package-lock.json` | 本地产物（npm install 生成），未跟踪 |

## 5. @changelog 覆盖说明（code-indexing-spec §4）

- **后端 6 个核心文件**（新增或重度修改）：已初始化 `@changelog`（标记对 + 三列表格 + REQ/TECH 关联 + `@author chuckyang123`），内容英文。
- **migration 0003**：Django 自动生成，人为添加头注释会在下次 `makemigrations` 时被覆盖，故不添加（§4 豁免）。
- **`__init__.py`**：空文件，无注释价值（§4 豁免）。
- **前端 5 个文件**：整个 `frontend/src` 项目现状 0 处 `@changelog`（存量文件同样无），为保持全库一致性不单独引入；变更均为既有文件增量修改，可由 git diff 追溯（§4 豁免）。
- **`yarn.lock` / `.gitignore`**：非源码文件，不适用（§4 豁免）。

## 6. 任务拆分完成度

- 架构任务：A1 ✅ A2 ✅ A3 ✅ A4 ✅
- 后端业务：B1 ✅ B2 ✅ B3 ✅ B4 ✅ B5 ✅ B6 ✅
- 前端业务：F1 ✅ F2 ✅ F3 ✅ F4 ✅
