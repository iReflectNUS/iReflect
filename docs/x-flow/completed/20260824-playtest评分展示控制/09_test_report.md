# 测试报告 — 20260824-playtest评分展示控制

> req_id: 20260824-playtest评分展示控制 | 阶段: TEST_EXECUTE / TEST_VERDICT
> 测试日期: 2026-08-24 | 测试环境: Windows / Python312 / SQLite（db_e2e.sqlite3）/ runserver 127.0.0.1:8765

## 1. 结论（TEST_VERDICT）

**PASS — 验收通过，可进入归档。**

PRD §3.3 全部验收标准（AC-3.1/3.2/3.3 + AC-4/5/6）通过；静态检查全绿；实现与「按课程配置、二选一、历史反馈立即生效」的需求语义一致。

## 2. E2E 结果（LT-012，真实 HTTP）

| step | 用例 | 结果 | 详情 |
|------|------|------|------|
| step1 | 教师 PUT `showAiScore=False` | ✅ PASS | `code=200, showAiScore=false` |
| step2 | 学生 POST 上报（key1） | ✅ PASS | 记录生成 |
| step3 | 注入 88 后学生 REPLAY → 隐藏分数 | ✅ PASS | `scoreJson=None`（注入值 88 未泄露） |
| step4 | 教师 GET → 保留分数 | ✅ PASS | `scoreJson={'total':88}` |
| step5 | 翻转 True 后学生 REPLAY → 可见分数 | ✅ PASS | `flip=true, scoreJson={'total':91}`（历史反馈立即生效） |
| step6 | 恢复 `showAiScore=False` | ✅ PASS | `code=200` |

**关键语义验证**：
- step3/step5 为**同一记录**翻转前后行为变化 → 证明「读取时动态裁剪」，历史反馈立即生效（AC-5）。
- step3（隐藏）/step4（教师保留）对比 → 学生与教师角色隔离正确（AC-6），且为同一后端数据。

## 3. 静态检查

| 检查项 | 结果 |
|--------|------|
| `django manage.py check` | ✅ System check identified no issues (0 silenced) |
| `makemigrations --check --dry-run` | ✅ No changes detected |
| 前端 `tsc --noEmit` | ✅ exit 0 |
| 前端 lint | ✅ 通过 |
| `@changelog` 索引 | ✅ 已维护 |

## 4. 缺陷记录与根因分析

### 4.1 缺陷 #1（测试脚本，非产品代码）：step5 断言读取字段名错误
- **现象**：E2E step5 反复 FAIL——翻转 `showAiScore=True` 后学生 REPLAY 仍断言 `score_json=None`。
- **排查过程**：
  1. 核对 DB：record `score_json={'total':91}`、`show_ai_score=1`、version course_id=2 ✅
  2. 独立进程 shell 模拟 `ai_feedback_record_to_json(record, include_score=True)` → `{'total':91}` ✅
  3. 给 `views.py` 加临时调试日志并重启服务器 → 日志显示 REPLAY 时服务器进程内 **`include_score=true`、`score_json_seen={'total':91}`** ✅（同时响应体字节数 1282 > 首次 POST 1274，印证分数已包含）
  4. **根因**：E2E 脚本 `rec4.get("score_json")` 字段名错误——API 响应为 camelCase `scoreJson`（step4 早已修正，step5 漏改）。`.get("score_json")` 恒为 None，属**测试脚本 bug，产品代码自始正确**。
- **修复**：脚本改为 `rec4.get("scoreJson")`（同时修正 step3 同类隐患），重跑全 PASS。
- **经验沉淀**：见归档摘要 §5 与记忆条目「API 字段 camelCase 约定」。

### 4.2 调试期辅助发现（不影响结论）
- 当前 shell 的 `python` 解析到 msys64 解释器（无 django），导致调试脚本注入子进程失败——必须显式使用与 runserver 一致的 `Python312` 解释器。
- 服务器调试日志写至 `views.py` 所在目录（`feedback/`），非脚本 cwd。

## 5. 测试设施
- 测试库 `backend/pigeonhole/db_e2e.sqlite3`；测试服务 runserver:8765（测试结束已停止）；临时脚本与日志已清理。
