# 归档摘要 — 20260824-playtest评分展示控制

> req_id: 20260824-playtest评分展示控制 | 阶段: ARCHIVE_COMPLETE
> 归档日期: 2026-08-24

## 1. 需求交付总结

教师端课程级开关控制 Playtest AI 数字评分对学生可见性，二选一（分数+建议 / 仅建议），默认仅建议，历史反馈立即生效。

**交付形态**：
- 后端：`CourseSettings.show_ai_score`（迁移 0005）+ 序列化器/逻辑/视图透传 + 反馈上报按角色裁剪 `score_json`（防御兜底）。
- 前端：课程创建/编辑表单 `AI Feedback Settings` 开关 + 反馈渲染组件 `stripScoresFromMarkdown` 剥离 Markdown 内嵌分数（主控制点，覆盖 nginx 直达路径）。
- 双保险设计：前端保证「页面不显示」，后端保证「API 拿不到」。

## 2. 阶段完成情况

| 阶段 | 状态 |
|------|------|
| INIT / REQUIREMENTS / DESIGN / IMPL_ARCHITECT_BACKEND / IMPL_ARCHITECT_FRONTEND | ✅ 已完成 |
| IMPL_CODE | ✅ 已完成 |
| IMPL_SELF_CHECK | ✅ 已完成（09 测试报告 §3 静态检查） |
| TEST_PLAN | ✅ 已完成（08_test_plan.md） |
| TEST_EXECUTE | ✅ 已完成（09_test_report.md，E2E 6/6 PASS） |
| TEST_VERDICT | ✅ PASS |
| ARCHIVE_COMPLETE | ✅ 本文件 |

## 3. 变更规模

- 后端 8 文件（1 新增迁移），前端 5 文件；`@changelog` 索引全部维护。
- 新增功能点：配置字段、透传链路、后端裁剪、前端剥离、表单开关（5 项）。

## 4. 关键决策记录

| 决策 | 内容 |
|------|------|
| D1 | 配置存储：`CourseSettings` 加字段（一维开关，不建独立配置表） |
| D2 | 实现语义：「读取时动态裁剪」而非「生成时固化」→ 历史反馈立即生效 |
| D3 | 展示语义（R2）：playtest 分数内嵌 Markdown 绕过后端 → 主控制点前置 `stripScoresFromMarkdown`，后端仅防御兜底；用户已确认接受该方案 |

## 5. 经验沉淀（已写入记忆系统）

### 5.1 新增记忆
1. **API 字段 camelCase 约定（E2E 解析陷阱）**：Django 后端响应经 DRF/前端约定序列化为 camelCase（`scoreJson`/`feedbackRecords`），E2E 断言必须与响应字段名一致；step4 已修正而 step5 漏改导致反复误判为产品缺陷。→ `short-term/code-patterns.md`、`evolve/corrections.md`
2. **Windows 多解释器陷阱**：PowerShell 的 `python` 可能解析到 msys64 解释器（无项目依赖），子进程注入/调试必须显式使用与 runserver 一致的 `Python312` 解释器。→ `short-term/debug-traces.md`
3. **服务器进程内观测法**：当「独立进程模拟正确、HTTP 行为异常」矛盾时，最有效手段是在视图内加临时文件日志并重启服务，直接观测进程内计算值（本次以此一锤定音确认产品代码正确）。→ `short-term/debug-traces.md`

### 5.2 本需求未产生用户纠正/回退事件，无回退日志。

## 6. 遗留说明

- `backend/pigeonhole/db_e2e.sqlite3` 为 E2E 测试库，按 PRD §8 要求保留于工作区（git 未跟踪，不提交）。
- 测试服务器已停止；全部临时脚本（`tmp_*.py`）与调试日志已清理。
