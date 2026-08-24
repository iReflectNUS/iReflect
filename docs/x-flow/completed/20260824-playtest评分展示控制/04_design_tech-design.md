---
req_id: 20260824-playtest评分展示控制
title: Playtest AI 评分展示控制（教师端开关）— 技术设计
phase: DESIGN_ARCHITECT
created_at: 2026-08-24T11:35:00+08:00
author: 03-design-agent
---

# Playtest AI 评分展示控制 — 技术设计

## 1. 关键架构事实（探索结论）

### 1.1 Playtest 反馈链路（学生视角）

```
学生点击「Generate feedback」
  → 前端读取 public/prompt_for_playtest_feedback.txt
  → POST /api/playtest/（nginx 代理 → LightRAG /query）
  → 返回 Markdown 文本（含 **Score: [xx/100]**、10 维度 x/10、知识图谱 x/50）
  → 前端 setFeedback(playtestResponse) 直接渲染 ←【学生看到分数的位置】
  → createFeedbackRecord(POST /api/feedback/records/) 上报（响应被 .unwrap() 丢弃，不展示）
```

**结论**: Playtest 分数**内嵌在 LightRAG 返回的 Markdown 文本中**，经 nginx 代理直达前端，**完全绕过 Django 后端**。学生可见分数的唯一控制点是**前端渲染层**。

### 1.2 反思路径（反思写作）

- `FeedbackView.post` 响应 `{annotated_content, feedback, record_id}` — **不含 score_json**
- 学生端 feedback-renderer 展示的也是 AI 文本（askChatGPT），非结构化分数

### 1.3 教师报告页

- `FeedbackRecordView.get`（EDUCATOR/ADMIN only）→ `ai_feedback_record_to_json` 含完整 `score_json`
- 教师始终可见分数 → **不受学生可见性配置影响**

### 1.4 已有配置载体（复用现成链路）

`CourseSettings`（OneToOne Course）→ `CourseSettingsSerializer`（显式字段）→ `Post/PutCourseSerializer`（MergeSerializersMixin 合并）→ `update_course()`（显式参数逐字段透传）→ 前端 `course-edit-form.tsx`（SwitchField 模式）

## 2. 总体方案

| 层次 | 方案 | 理由 |
|------|------|------|
| **前端学生渲染层（主控制点）** | playtest renderer 根据课程配置，在渲染 LightRAG 文本前**剥离 Markdown 中的分数区块**，仅保留文字建议 | 分数源头在外部 AI 文本，Django 无法介入 |
| **后端 API 层（防御性兜底）** | `ai_feedback_record_to_json` 增加 `include_score` 参数；`FeedbackRecordView.post`（学生上报）按课程配置裁剪 score_json；GET（教师）始终完整 | 防止未来前端/API 暴露 score_json（呼应 EV-001） |
| **配置存储** | `CourseSettings.show_ai_score` 布尔字段，`default=False`（默认仅建议） | 复用现成链路，6 处小改动 |
| **前端教师端** | `course-edit-form.tsx` 新增 SwitchField「向学生展示 AI 评分」 | 复用现成表单模式 |

## 3. 后端设计

### 3.1 模型：`CourseSettings.show_ai_score`

**文件**: `backend/pigeonhole/courses/models.py`

```python
class CourseSettings(models.Model):
    # ...existing fields...
    show_ai_score = models.BooleanField(
        default=False,
        help_text="If False (default), students only see AI text suggestions, "
                  "not numeric scores (score_json). Teachers always see scores.",
    )
```

- `default=False` → 存量课程无需 backfill，立即生效「仅建议」新默认（符合 PRD §4 兼容性）

### 3.2 迁移

```
py manage.py makemigrations courses   # 生成 000X_coursesettings_show_ai_score
```

### 3.3 序列化器：`CourseSettingsSerializer`

**文件**: `backend/pigeonhole/courses/serializers.py` → fields 追加 `"show_ai_score"`

### 3.4 业务逻辑：`update_course`

**文件**: `backend/pigeonhole/courses/logic.py` → `update_course()` 增加 `show_ai_score` 参数并写入 settings（与现有一致逐字段透传）

### 3.5 视图：`CourseView.put`

**文件**: `backend/pigeonhole/courses/views.py` → `validated_data["show_ai_score"]` 透传（与现有一致）

### 3.6 后端 API 裁剪（防御性兜底）

**文件**: `backend/pigeonhole/feedback/logic.py` + `feedback/views.py`

```python
# logic.py
def ai_feedback_record_to_json(record: AIFeedbackRecord, include_score: bool = True) -> dict:
    data = to_base_json(record)
    data |= { ..., "score_json": record.score_json if include_score else None, ... }
    return data
```

- `FeedbackRecordView.post`（学生上报）: 读取 `record.version.course` 的 `settings.show_ai_score` → 若 False 且 requester 为 STANDARD → `include_score=False`
- `FeedbackRecordView.get`（教师报告页）: 保持 `include_score=True` 不变

## 4. 前端设计

### 4.1 常量：`SHOW_AI_SCORE`

**文件**: `frontend/src/constants/index.ts`

```typescript
export const SHOW_AI_SCORE = "showAiScore";  // camelCase 由后端渲染层自动转换
```

### 4.2 类型：`frontend/src/types/courses.ts`

`CourseSettings` 类型追加 `show_ai_score: boolean`

### 4.3 教师端设置：`course-edit-form.tsx`

- schema 追加 `[SHOW_AI_SCORE]: z.boolean()`
- UI 新增 SwitchField，仿照「Make group members public」模式（Text + Tooltip + ThemeIcon + SwitchField）
- 文案建议: "Show AI scores to students" / Tooltip: "When off, students only see AI text suggestions without numeric scores. Teachers always see full scores."

### 4.4 学生端渲染：`form-field-playtest-feedback-renderer.tsx`

**核心逻辑**：在 `setFeedback(playtestResponse)` 前根据课程配置剥离分数区块。

```typescript
// 通过 useGetCourseId() 获取 courseId，useGetSingleCourseQuery 拉取课程
// course.settings.showAiScore === false 时剥离分数

function stripScoresFromMarkdown(md: string): string {
  // 剥离以下区块（保留 Professor Feedback / Final Summary 等文字建议）：
  // 1. **Score: [xx/100]** 行
  // 2. **Breakdown of Key Ingredients:** 到下一个二级/三级标题 或结尾
  // 3. **Genre & Mechanic Evaluation (Knowledge Graph Score):** 区块
}
```

- 配置为「分数+建议」时：原样渲染（与现状一致，零回归）
- 配置为「仅建议」时：剥离分数区块后渲染
- **说明**: 该组件需访问课程上下文 → 通过 `useGetCourseId()`（组件已在课程提交页面内，courseId 可从 URL 获取）

### 4.5 课程 API 类型（如必要）

确认 `feedback-api.ts` / `courses-api.ts` 的 `CourseSettings` 类型自动随后端字段扩展（RTK Query 无编译期类型校验，仅 `types/courses.ts` 需同步）

## 5. 影响文件清单

| # | 文件 | 改动 |
|---|------|------|
| B1 | `backend/pigeonhole/courses/models.py` | +`show_ai_score` 字段 |
| B2 | `backend/pigeonhole/courses/migrations/000X_*.py` | makemigrations 生成 |
| B3 | `backend/pigeonhole/courses/serializers.py` | CourseSettingsSerializer fields +`show_ai_score` |
| B4 | `backend/pigeonhole/courses/logic.py` | update_course +参数 |
| B5 | `backend/pigeonhole/courses/views.py` | CourseView.put 透传 |
| B6 | `backend/pigeonhole/feedback/logic.py` | ai_feedback_record_to_json +include_score |
| B7 | `backend/pigeonhole/feedback/views.py` | FeedbackRecordView.post 按配置裁剪 |
| F1 | `frontend/src/constants/index.ts` | +SHOW_AI_SCORE |
| F2 | `frontend/src/types/courses.ts` | CourseSettings +show_ai_score |
| F3 | `frontend/src/components/course-edit-form.tsx` | +SwitchField |
| F4 | `frontend/src/components/form-field-playtest-feedback-renderer.tsx` | 渲染前剥离分数（主控制点） |

## 6. 风险与缓解

| 风险 | 等级 | 缓解 |
|------|------|------|
| **R1**: LightRAG 文本格式不固定，正则剥离可能漏/误伤 | 中 | 剥离逻辑按 prompt 约定的固定区块头匹配（Score/Breakdown/Knowledge Graph），未命中时整段保留兜底；E2E 用固定 prompt 文本验证 |
| **R2**: 学生经 `/api/playtest/` 直接获取原始文本（绕过前端剥离） | 中 | 该接口是外部 LightRAG 代理，非本系统数据；且 PRD 语义是「展示控制」而非「数据加密」— 前端剥离即满足展示语义；如需强加密需改造代理层（超出本次范围，记录为生产观察项） |
| **R3**: 反思路径是否也需剥离分数 | 低 | 已确认反思路径响应不含 score_json，学生看到的是 AI 文本；如教师要求反思也仅建议 → 需同样剥离（本次范围外，记录观察项） |
| **R4**: `include_score` 参数调用点遗漏 | 低 | 搜索 `ai_feedback_record_to_json(` 全部调用点逐一确认（预计 2 处：post + get） |

## 7. 测试策略（映射 PRD 验收）

| PRD 验收 | 测试方式 |
|----------|---------|
| 3.1 教师端开关 | E2E: EDUCATOR PUT course 带 showAiScore 字段 → GET 回读一致 |
| 3.1 默认仅建议 | 建新课程 → settings.show_ai_score = false |
| 3.2 学生端按配置渲染 | E2E + 组件单测: playtest renderer 在 showAiScore=false 时剥离分数区块；true 时保留 |
| 3.2 仅建议不显示占位符 | 组件单测: 剥离后无空 div/NaN |
| 3.3 学生 API 响应无分数 | E2E: STANDARD 上报 → 响应 scoreJson 为 null；EDUCATOR GET → scoreJson 完整 |
| 3.3 配置变更即时生效 | E2E: 先 false 上报 → 教师改 true → 学生重拉 → 含分数（读取时动态裁剪语义） |

## 8. 开放问题

- [x] **OQ-1**: playtest renderer 的 courseId 获取方式 — 已确认：`useGetCourseId()` 从 URL 路由参数读取（组件在课程提交页面内，URL 含 courseId）
- [x] **OQ-2**: 剥离函数是否应用于反思路径 — 否（本次仅 playtest）；反思路径响应不含 score_json，观察项 R3 已记录
- [x] **OQ-3**: `CourseData` 结构 — `CourseSummaryData & CourseSettings`（settings 扁平合并），前端 `course.showAiScore` 直接可读
