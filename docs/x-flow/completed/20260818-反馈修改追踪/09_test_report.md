# 测试报告 — 20260818-反馈修改追踪

> req_id: 20260818-反馈修改追踪 | 阶段: TEST_EXECUTE | Agent: 06-implement-agent
> 执行方式: 隔离库 `db_e2e.sqlite3`（独立于开发库）+ 真实 `runserver` + 真实 HTTP 请求（stdlib urllib）+ 真实 `manage.py` 命令

## 1. 执行摘要

| 类别 | 数量 | 结果 |
|------|------|------|
| 真实 HTTP 测试用例 | 11 | ✅ 10 PASS / ⚠️ 1 BLOCKED（外部依赖） |
| DB 断言 | 5 项 | ✅ 全部 PASS |
| backfill 命令（TC-007） | 首次 + 幂等重跑 | ✅ PASS |
| 静态/逻辑审查 | 6 文件 | ✅ 通过 + 1 观察发现（OBS-001） |

## 2. 测试矩阵

| 用例 | 验收 | 结果 | 证据 |
|------|------|------|------|
| E2E-002 Playtest 上报 v1 | AC-201/203/204 | ✅ PASS | POST `/api/feedback/records/` 200；version 1 落库，字段完整（course/milestone/template/creator/question/answerContent/genre/mechanic/versionNumber） |
| E2E-002b 连续上报版本递增 | AC-101/103 | ✅ PASS | 同一学生/问题第二次上报 → versionNumber=2 |
| E2E-003 幂等去重 | AC-201, RISK-DA006 | ✅ PASS | 相同 idempotency_key 重发 → 返回相同 record id=2；DB 无重复行 |
| E2E-004 教师查询时间线 | AC-401/403 | ✅ PASS | GET records/?course_id=&question= → 200，versions=[1,2] 升序，各含 feedbackRecords |
| E2E-001 AI 成功路径 | AC-205 | ⚠️ BLOCKED | 测试环境无 `OPENAI_API_KEY`（外部依赖缺失）；落库事务路径已由 E2E-002/003（同一 `create_feedback_version_and_record`）真实覆盖 |
| E2E-001 失败路径（无 key） | AC-205, TC-006 | ✅ PASS | POST `/api/feedback/` → 5xx，**DB 无任何残留版本/记录**（失败不落库） |
| TC-004 缺 submission_id | AC-104 | ✅ PASS | 400 校验错误 |
| TC-007 backfill 首跑 | AC-301/302 | ✅ PASS | 2 条历史 → 2 条 version 1；回填版本无关联 AI 反馈记录 |
| TC-007 backfill 幂等重跑 | AC-303 | ✅ PASS | 重跑 → 0 created / 2 skipped |
| TC-009 学生访问查询 | AC-402 | ✅ PASS | GET records/ 学生 → 403 |
| TC-011 outsider 越权上报 | NFR-2 | ✅ PASS | 非课程成员上报 → 400 |
| TC-012 存量接口回归 | 兼容性 | ✅ PASS | POST initial-response/ → 200，get_or_create 行为不变 |

### DB 最终断言（5/5 PASS）
- 版本总数 = 5（E2E 3 + backfill 2）✅
- 学生 v1/v2、学生2 v1 均存在 ✅
- AI 反馈记录 = 3（无 OpenAI 失败残留）✅
- idempotency_key 全部唯一 ✅
- backfill 版本无关联反馈 ✅

## 3. 通用检查项（CHK）

| 编号 | 检查项 | 结果 |
|------|--------|------|
| CHK-1 | 编译（py_compile + check + tsc） | ✅ PASS（本轮重跑通过） |
| CHK-2 | 注释英文（CORR-001） | ✅ PASS（Phase 11 全量英文化，本轮新增代码为临时测试脚本已清理） |
| CHK-3 | SQL 安全 | ✅ PASS（全程 ORM；查询过滤走 `IdField`/CharField 白名单校验） |
| CHK-4 | 空值/边界 | ✅ PASS（缺 submission_id→400；无过滤参数 GET→200；空答案不落库） |
| CHK-5 | 迁移一致性 | ✅ PASS（`migrate` 干净应用 0003；开发库无残留迁移） |
| CHK-6 | 存量回归 | ✅ PASS（TC-012） |

## 4. 静态/逻辑审查发现

### OBS-001（观察发现，非阻断）
- **现象**: `create_feedback_version_and_record` 的归属校验只到**课程成员级**（`coursemembership_set.get(user=requester)`），不校验 `submission.creator`。E2E 实测：学生 2（课程成员，非 submission 所有者）可在学生 1 的 **INDIVIDUAL** 类型 submission 下成功上报版本+反馈记录（200）。
- **影响**: GROUP submission 协作场景下该行为正确（组员共同编辑）；INDIVIDUAL submission 下允许同学写入版本记录，会造成「A 的版本挂在 B 的 submission」数据错位。
- **处置**: 不修改代码（TEST_EXECUTE 只验证）；标记为待 Owner 决策项，可放入后续迭代（如按 submission_type=INDIVIDUAL 时校验 creator==requester）。

### 审查通过项
- `views.py`: GET 查询使用 `select_related` + `prefetch_related`（无 N+1）；权限矩阵正确（POST: 全体、GET: EDUCATOR/ADMIN）
- `serializers.py`: `PostFeedbackRecordSerializer` 字段完整，`idempotency_key=UUIDField(optional)` 兼容 `crypto.randomUUID()`
- `logic.py`: 幂等分支先返回已有记录；版本号同维度 Max+1；整体事务（AI 失败不落库已实测）
- 前端 `form-field-playtest-feedback-renderer.tsx`: 每次生成用 `crypto.randomUUID()`（RTK 请求级复用同 key → 网络重试自动去重，RISK-DA006 闭环）

## 5. 遗留风险更新

| 风险 | 状态 |
|------|------|
| R1 前端 idempotency_key 正确性 | ✅ 已关闭（randomUUID 每次唯一 + RTK 重试复用同 key） |
| R2 并发同键竞态 | ⚠️ 未实测（依赖 DB 唯一约束兜底；单请求环境无法复现并发，标注为生产观察项） |
| R3 大数据量查询性能 | ⚠️ 未实测（索引设计已核对：creator+question+created_at；标注为生产观察项） |
| R4 生产 OpenAI/LightRAG 链路 | ⚠️ BLOCKED：测试环境无 `OPENAI_API_KEY`，AI 成功路径需在生产/有 key 环境回归（E2E-001） |

## 6. 环境记录

- 隔离库 `db_e2e.sqlite3` 已删除；临时脚本（fixture/e2e/backfill/verify）已全部清理
- 测试服务（runserver:8765）已停止
- 开发库 `db.sqlite3` 未被污染
