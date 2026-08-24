# 测试计划 — 20260824-playtest评分展示控制

> req_id: 20260824-playtest评分展示控制 | 阶段: TEST_PLAN
> 关联: PRD §3.3 验收标准（LT-012 真实 HTTP E2E）、§8 测试设施

## 1. 测试范围

| 编号 | 验收点（PRD） | 测试方法 | 级别 |
|------|--------------|---------|------|
| AC-3.1 | 默认仅建议（不显示分数） | E2E step1-3 | 端到端 |
| AC-3.2 | 开关打开后学生可见分数 | E2E step5 | 端到端 |
| AC-3.3 | 教师端开关存在且可配置 | E2E step1/step5（PUT）+ 前端表单代码审查 | 端到端+静态 |
| AC-4 | 防御兜底：STANDARD 角色 API 裁剪 | E2E step3（含 API 直接读取验证） | 端到端 |
| AC-5 | 历史反馈立即生效（读取时动态裁剪） | E2E step3/step5（同一记录翻转前后行为变化） | 端到端 |
| AC-6 | 教师/其他角色不受影响 | E2E step4（教师 GET 保留 scoreJson） | 端到端 |

## 2. E2E 测试场景（LT-012）

真实 HTTP（urllib，不经 APIClient）+ 独立 sqlite 注入，服务：runserver `127.0.0.1:8765`、`db_e2e.sqlite3`。

| step | 操作 | 期望 |
|------|------|------|
| step1 | 教师 PUT `showAiScore=False` | 200，`showAiScore=false` |
| step2 | 学生 POST 上报（幂等键 key1，course=2） | 200，生成记录 |
| step3 | 注入 `score_json={'total':88}` → 学生 REPLAY key1 | 学生响应 `scoreJson=None`（隐藏） |
| step4 | 教师 GET 记录 | `scoreJson={'total':88}`（保留） |
| step5 | 教师 PUT `showAiScore=True` → 新 key2 POST → 注入 `{'total':91}` → 学生 REPLAY key2 | `scoreJson={'total':91}`（翻转后可见，历史反馈生效） |
| step6 | 教师 PUT `showAiScore=False` | 200（恢复默认） |

## 3. 静态验证

- `django manage.py check`：0 issues
- `makemigrations --check --dry-run`：No changes detected（迁移一致性）
- 前端 `tsc --noEmit`：0 errors
- 前端 lint：通过
- `@changelog` 索引完整性检查（Phase 10）

## 4. 测试数据前置（PRD §8）

- 测试课程：course 2（含 `CourseSettings` 记录，满足 NOT NULL 约束）
- 测试用户：teacher（INSTRUCTOR 成员，PUT 权限升级为 CO-OWNER，仅测试库数据）、student（STANDARD）
- 提交：submission 1 → course 2
- 幂等键：每次运行生成 uuid，避免与历史数据冲突
