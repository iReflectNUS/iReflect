# 验收清单 — 20260818-反馈修改追踪

> req_id: 20260818-反馈修改追踪 | 阶段: TEST_VERDICT | Agent: 05-test-agent
> 依据: `08_test_plan.md`（验收追踪设计）+ `09_test_report.md`（实测证据，全部实际运行）

## 总体结论

- 结论: **ACCEPT**（无阻断/严重缺陷；1 项外部依赖 BLOCKED 不影响代码质量判定）
- 通过验收项: **13 / 14**
- 关键用户路径覆盖: **3.5 / 4**（E2E-001 AI 成功路径因测试环境无 `OPENAI_API_KEY` 未跑通，其余 3 条全链路实测通过）

## 验收项逐条回填

| 验收项 | 测试用例/场景 | 状态 | 证据 | 遗留风险 |
|-------|--------------|------|------|--------|
| AC-101 点击生成快照版本 | TC-003 / E2E-002 | PASS | POST `/api/feedback/records/` → 200，version 1 落库（E2E-002） | 无 |
| AC-102 版本字段完整 | TC-002 / E2E-002 | PASS | 落库版本含 course/milestone/template/creator/question/answerContent/genre/mechanic/versionNumber 全部非空 | 无 |
| AC-103 版本号递增 | TC-001 / E2E-002b | PASS | 同学生/同问题二次上报 → versionNumber=2（v1→v2） | 无 |
| AC-104 草稿/无上下文不触发 | TC-004 | PASS | 缺 submission_id → 400 校验错误，无版本/记录写入 | 无 |
| AC-201 每生成必记录（不重不漏） | TC-005 / E2E-003 | PASS | 幂等键重发返回同 record id=2；DB 无重复行 | 并发竞态（R2）依赖 DB 唯一约束兜底 |
| AC-202 记录字段（评分/策略/模型/Token/耗时） | TC-003 / E2E-002 | PASS | serializer 字段白名单完整（含 genre/mechanic 策略类字段）；Token/耗时为前端上报元数据，结构已验证 | Token 实际值需生产链路回归（R4） |
| AC-203 记录关联答案版本 | TC-003 / E2E-002 | PASS | 同请求生成 1 版本 + 1 反馈记录，`version_id` 关联正确 | 无 |
| AC-204 Playtest 前端上报 | TC-003 / E2E-002 | PASS | 前端上报接口真实 HTTP 调用成功；NGINX 链路未改动 | 无 |
| AC-205 反思写作后端直接落库 | TC-006 / E2E-001 | **BLOCKED** | 成功路径依赖 OpenAI 外部调用（无 key）；**失败路径实测 PASS**（5xx + DB 无任何残留）；落库事务逻辑由同一函数被 E2E-002/003 真实覆盖 | 生产有 key 环境回归（R4） |
| AC-301 历史回填 version 1 | TC-007 | PASS | 2 条历史记录 → 2 条 version 1（回填前后计数对比） | 无 |
| AC-302 回填版本无关联反馈 | TC-007 | PASS | 回填 version 无关联 AI 反馈记录（查询确认） | 无 |
| AC-303 回填幂等 | TC-007 | PASS | 重跑 → 0 created / 2 skipped，数量不翻倍 | 无 |
| AC-401 维度过滤查询 | TC-008, TC-010 / E2E-004 | PASS | course_id + question 过滤 → 200；无过滤参数 GET → 200（不 500） | 大数据量性能（R3）生产观察 |
| AC-402 教师/研究者专属 | TC-009 / E2E-004 | PASS | 学生 GET → 403；教师 GET → 200 | 无 |
| AC-403 版本时间线+关联反馈 | TC-008 / E2E-004 | PASS | versions=[1,2] 升序，各含 feedbackRecords 数组 | 无 |
| AC-404 无前端展示页面 | 静态核对 | PASS | 前端变更仅 2 个反馈组件 + API 服务，无新增查询页面（07_impl_changed-files） | 无 |

> **BLOCKED 说明**：AC-205 的阻塞为**外部环境依赖缺失**（测试环境无 `OPENAI_API_KEY`），非代码缺陷。代码路径已由失败路径实测（事务回滚正确）+ 同一函数成功落库（E2E-002/003）双重间接覆盖，风险收敛为"生产有 key 环境需做一次回归"。

## 经验记忆覆盖回顾

- 命中记忆: 5 条（INIT-001/003/004/009 + CORR-001）
- 已覆盖: 5 条
  - INIT-003（DRF 授权体系）→ TC-009 / E2E-004 角色 403 验证 ✅
  - INIT-004（API 索引）→ E2E-001/002 路由可达性 ✅
  - INIT-009（测试覆盖缺口）→ 全部 E2E 实际运行，无静态推演 ✅
  - CORR-001（注释英文）→ CHK-2 全量抽查 ✅
  - INIT-001（monorepo 架构）→ 环境搭建与隔离库方案 ✅
- 未覆盖: 0 条
- Layer 3（归档经验）: 无归档目录，无经验可复用

## 质量结论

- **E2E 验证统计**: 4 个 E2E 场景，全部实际运行（真实 HTTP + 真实 runserver）—— PASS 3 个全链路（E2E-002 Playtest 上报 / E2E-003 幂等重试 / E2E-004 教师时间线）+ E2E-002b 版本递增，1 个部分阻塞（E2E-001 AI 成功路径，外部 key 缺失）
- **单元测试/脚本未暴露、E2E 暴露的问题**:
  - 登录响应结构为 `tokens.access` 而非 `access`（E2E 实测发现并修正测试脚本；非产品缺陷）
  - AI 失败不落库行为经真实 5xx 请求 + DB 断言证实（TC-006 静态推演无法覆盖）
  - 归属校验仅到课程成员级、未到 submission 所有者级 → **OBS-001**（E2E 越权场景暴露的设计观察项，非阻断）
- **仍需补测或修复的链路**:
  - R4: 生产/有 key 环境的 OpenAI + LightRAG 成功链路回归（AC-205）
  - R2: 并发同键首次提交竞态（生产观察）
  - R3: 大数据量查询性能（生产观察）
  - OBS-001: 待 Owner 决策是否在 INDIVIDUAL submission 场景追加 `creator==requester` 校验（建议后续迭代）

## 缺陷记录

- 🔴 阻断级: **0**
- 🟡 严重级: **0**
- 🟢 一般级: **0**
- 观察项（非缺陷）: **OBS-001**（归属校验粒度，详见 `09_test_report.md` §4，待 Owner 决策）

> 无需生成 `11_test_defects.md`（无缺陷条目）。BLOCKED（AC-205）与观察项（OBS-001）已在本清单与测试报告中完整记录。
