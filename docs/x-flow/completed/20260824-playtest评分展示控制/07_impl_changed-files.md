# 变更文件清单 — 20260824-playtest评分展示控制

> req_id: 20260824-playtest评分展示控制 | 阶段: IMPL_CODE 产物

## 1. 后端（8 个文件）

| 文件 | 变更类型 | 内容 |
|------|---------|------|
| `backend/pigeonhole/courses/models.py` | 修改 | 新增 `CourseSettings.show_ai_score = BooleanField(default=False)`；文件头补 `@changelog` |
| `backend/pigeonhole/courses/migrations/0005_coursesettings_show_ai_score.py` | 新增 | `AddField` 迁移（已应用至 db_e2e） |
| `backend/pigeonhole/courses/serializers.py` | 修改 | `CourseSettingsSerializer.fields` 加入 `show_ai_score`；显式 `BooleanField(required=False, default=False)` |
| `backend/pigeonhole/courses/logic.py` | 修改 | `course_to_json` 输出 `SHOW_AI_SCORE`；`create_course`/`update_course` 签名加 `show_ai_score: bool`；保存到 settings |
| `backend/pigeonhole/courses/views.py` | 修改 | POST/PUT 两处调用透传 `show_ai_score=validated_data["show_ai_score"]` |
| `backend/pigeonhole/feedback/logic.py` | 修改 | `ai_feedback_record_to_json(record, include_score=True)`；`@changelog` v1.2.0 |
| `backend/pigeonhole/feedback/views.py` | 修改 | `FeedbackRecordView.post` 学生角色按课程配置计算 `include_score` |
| `backend/pigeonhole/pigeonhole/common/constants.py` | 修改 | 新增 `SHOW_AI_SCORE = "show_ai_score"` |

## 2. 前端（5 个文件）

| 文件 | 变更类型 | 内容 |
|------|---------|------|
| `frontend/src/constants/index.ts` | 修改 | 新增 `SHOW_AI_SCORE = "showAiScore"` |
| `frontend/src/types/courses.ts` | 修改 | `[SHOW_AI_SCORE]: boolean` 类型 |
| `frontend/src/components/course-creation-form.tsx` | 修改 | schema + `DEFAULT_VALUES.showAiScore=false` + AI Feedback Settings 区块（SwitchField + Tooltip） |
| `frontend/src/components/course-edit-form.tsx` | 修改 | 同上（编辑表单） |
| `frontend/src/components/form-field-playtest-feedback-renderer.tsx` | 修改 | 导出 `stripScoresFromMarkdown`；按 `accountType === Standard && course?.showAiScore === false` 剥离分数；新增 3 个 hook 导入 |

## 3. 数据与测试设施（不进正式代码库）

| 文件 | 说明 |
|------|------|
| `backend/pigeonhole/db_e2e.sqlite3` | E2E 测试库（已按 PRD §8 注入课程/成员/提交等测试数据） |
| `docs/x-flow/active/20260824-playtest评分展示控制/*` | 工作流阶段产物（本文件所在目录） |

> 注：E2E 临时脚本（`tmp_e2e_show_score.py` / `tmp_dbg_*.py` / `tmp_server_*.log`）已在本 flow 收尾时清理，不留入代码库。
