# 实现日志 — 20260824-playtest评分展示控制

> req_id: 20260824-playtest评分展示控制 | 阶段: IMPL_CODE | Agent: main-agent
> 输入: `04_design_tech-design.md` + `05_design_task-breakdown.md`

## 1. 实现总览

| 任务 | 内容 | 状态 |
|------|------|------|
| A1 | 迁移 0005：`CourseSettings.show_ai_score`（default=False） | ✅ 已生成并应用 |
| A2 | `CourseSettingsSerializer` 暴露 `show_ai_score`（required=False, default=False） | ✅ |
| A3 | 常量/类型贯通：后端 `SHOW_AI_SCORE` + 前端 `SHOW_AI_SCORE` | ✅ |
| B1 | 配置透传：`course_to_json` / `create_course` / `update_course` 显式 `show_ai_score` 参数 | ✅ |
| B2 | `ai_feedback_record_to_json(record, include_score=True)` 防御裁剪参数 | ✅ |
| B3 | `FeedbackRecordView.post` 学生角色按课程配置裁剪 `score_json` | ✅ |
| F1 | 教师端开关：课程创建/编辑表单 SwitchField + Tooltip（AI Feedback Settings 区块） | ✅ |
| F2 | 前端剥离：`stripScoresFromMarkdown` 锚点截断 + 正则兜底，按配置渲染 | ✅ |

## 2. 关键决策与实现说明

### 2.1 主控制点 vs 防御兜底（架构分层）
- **主控制点（前端）**：playtest 分数内嵌于 LightRAG Markdown（`**Score: [xx/100]**`），经 nginx 直达前端、绕过 Django。因此 `form-field-playtest-feedback-renderer.tsx` 以 `**Professor Feedback:**` 锚点截断 + 行正则过滤兜底剥离全部数字分数，满足「页面不显示」的展示语义（R2 用户决策：接受该方案，不改造 nginx 层）。
- **防御兜底（后端）**：`FeedbackRecordView.post` 对 STANDARD 角色且课程 `show_ai_score=False` 时返回 `score_json=None`，防止学生绕过 UI 直接读 API（PRD §3.3 / §4 安全要求，EV-001 记忆）。

### 2.2 配置链路
`CourseSettings.show_ai_score`（default=False）→ `CourseSettingsSerializer`（显式 BooleanField required=False default=False）→ `update_course()` / `create_course()` 显式参数 → 前端 `DEFAULT_VALUES.showAiScore=false` + SwitchField。

### 2.3 历史反馈立即生效
实现为「读取时按当前配置动态裁剪」，不做「生成时固化」—— 课程开关变更后，学生下一次拉取/上报即按新配置渲染，历史反馈同样生效（PRD §5 约束）。

## 3. 质量活动记录

| 检查 | 结果 |
|------|------|
| `django manage.py check` | ✅ 0 issues |
| `makemigrations --check --dry-run` | ✅ No changes detected |
| 前端 `tsc --noEmit` | ✅ 0 errors |
| 前端 lint | ✅ 通过 |
| 迁移应用（db_e2e） | ✅ 0005 已应用 |
| Serializer 回读（缺省 False / 传 True） | ✅ |
| `stripScoresFromMarkdown` node 样例（3 组） | ✅ |
| `@changelog` 编码索引 | ✅ 全部新增/重度修改文件已维护版本表 |

## 4. 未决/风险

- R2（分数内嵌 Markdown，仅前端剥离）已在 clarify 阶段由用户决策接受，risks.json 已记录 `discussionStatus: closed`。
