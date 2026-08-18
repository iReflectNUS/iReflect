# 实现日志 — AI反馈记录与修改版本追踪（科研数据持久化）

> req_id: 20260818-反馈修改追踪 | 阶段: IMPL_ARCHITECT_BACKEND + IMPL_CODE + IMPL_SELF_CHECK | Agent: 04-implement-agent
> 输入: `04_design_tech-design.md` + `05_design_task-breakdown.md`

## 1. 实现范围

按 `05_design_task-breakdown.md` 执行：

- **Phase 09 (IMPL_ARCHITECT_BACKEND)**: A1 `FeedbackAnswerVersion` 模型、A2 `AIFeedbackRecord` 模型、A3 迁移、A4 接口契约
- **Phase 10 (IMPL_CODE) 后端**: B1 共享函数 `create_feedback_version_and_record`、B2 `FeedbackView` 改造、B3 序列化器、B4 `FeedbackRecordView`、B5 路由注册、B6 回填命令
- **Phase 10 (IMPL_CODE) 前端**: F2 类型定义、F1 API 端点、F3 反思写作组件、F4 Playtest 组件

## 2. 关键实现决策

| # | 决策 | 说明 |
|---|------|------|
| 1 | 幂等键方案（RISK-DA006） | `AIFeedbackRecord.idempotency_key` UUID 唯一约束，重复提交直接返回已有记录 |
| 2 | 版本号 Max+1 | 同 (course, milestone, template, creator, question) 维度聚合 `Max(version_number)+1` |
| 3 | 事务落库 | `create_feedback_version_and_record` 使用 `@transaction.atomic`：幂等查重 → 归属校验 → 版本递增 → 创建 version + record |
| 4 | 策略路由 | `requester.id % 2 == 0` → `askChatGPTOriginal`（BASIC），否则 `askChatGPT`（ADVANCED） |
| 5 | Advanced 元数据 | score_json 从结构化 `Feedback` 提取、token_usage 聚合、latency_ms 计时 |
| 6 | `getFeedback` 保持 query | 兼容 `useLazyGetFeedbackQuery`，不改为 mutation（避免破坏既有调用） |
| 7 | Playtest 前端上报 | LightRAG 链路不改 NGINX，前端收到响应后调用 `createFeedbackRecord` 上报 |

## 3. 变更文件清单

详见 `07_impl_changed-files.md`（含每个文件的 @changelog 覆盖状态与说明）。

## 4. 验证结果

| 检查项 | 命令 | 结果 |
|--------|------|------|
| Django system check | `manage.py check` | ✅ System check identified no issues |
| 迁移一致性 | `makemigrations --check --dry-run` | ✅ No changes detected |
| 后端语法 | `py -3.12 -m py_compile`（6 文件） | ✅ 通过 |
| 后端 lint | ruff | ✅ 0 errors |
| 前端类型检查 | `npx tsc --noEmit` | ✅ 0 errors |
| 注释语言扫描 | 全量中文搜索（backend + frontend） | ✅ 0 命中（注释已全部英文化） |

> 注：验证使用临时环境变量（`SQL_ENGINE=django.db.backends.sqlite3`），不创建 `.env` 遗留文件。

## 5. 自检发现与处理（IMPL_SELF_CHECK）

| # | 发现 | 处理 |
|---|------|------|
| 1 | 新增代码注释混用中文（@changelog 表、docstring、行内注释共 22 处） | 全部改写为英文（用户要求：所有 comment 一律英文），并沉淀为项目约定 CORR-001 |
| 2 | `SQL_ENGINE=sqlite3` 校验报错 `No module named 'sqlite3.base'` | settings.py 中 ENGINE 需完整 backend 路径，改用 `django.db.backends.sqlite3` |
| 3 | `getFeedback` 实现中途被误改为 mutation | 修正回 `build.query`，保持 `useLazyGetFeedbackQuery` 反向兼容 |
| 4 | migration / `__init__.py` / 前端文件无 @changelog | 按 code-indexing-spec §4 说明原因，见 `07_impl_changed-files.md` §5 |
| 5 | 前端 `yarn.lock` 出现大 diff | LF→CRLF 行尾转换所致，非功能变更 |

## 6. 需求覆盖对照

| 需求（PRD 要点） | 实现 | 状态 |
|------------------|------|------|
| 答案快照版本（version 1→2→3…） | `FeedbackAnswerVersion` + 回填命令（历史为 version 1） | ✅ |
| AI 反馈记录（评分/内容/策略/元数据） | `AIFeedbackRecord`（score_json / token_usage_json / latency_ms / strategy） | ✅ |
| 「修改-反馈」时间线 | version FK → record，GET 查询接口按版本聚合返回 | ✅ |
| 重复提交防护（科研数据纯净） | `idempotency_key` 唯一约束（RISK-DA006） | ✅ |
| 仅后端存储 + 教师/研究者查询 | GET `records/` 限 EDUCATOR/ADMIN；无前端展示 | ✅ |

## 7. 遗留事项

- 查询接口分页 / 默认 limit 值仍为开放问题（设计阶段遗留，不影响当前实现）
- `backend/pigeonhole/db.postgresql`、`frontend/package-lock.json` 为本地产物（未跟踪，`.gitignore` 已覆盖 db 文件）
