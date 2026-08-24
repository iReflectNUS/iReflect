---
req_id: 20260824-playtest评分展示控制
title: Playtest AI 评分展示控制 — 任务拆分
phase: DESIGN_TASK_SPLIT
created_at: 2026-08-24T11:40:00+08:00
author: 03-design-agent
---

# Playtest AI 评分展示控制 — 任务拆分

## 架构任务（Phase 09: IMPL_ARCHITECT_BACKEND）

| # | 任务 | 优先级 | 复杂度 | 涉及模块 | 技术栈 |
|---|------|--------|--------|---------|--------|
| A1 | `CourseSettings` 模型新增 `show_ai_score` 字段（default=False）+ 生成迁移 000X | P0 | 低 | courses/models.py + migrations | Django |
| A2 | `CourseSettingsSerializer.fields` 追加 `show_ai_score`（显式字段列表） | P0 | 低 | courses/serializers.py | DRF |
| A3 | 前端常量 `SHOW_AI_SCORE` + `types/courses.ts` 类型追加 `show_ai_score: boolean` | P0 | 低 | constants/index.ts + types/courses.ts | TS |

## 业务任务（Phase 10: IMPL_CODE）

### 后端任务（Backend）

| # | 任务 | 优先级 | 复杂度 | 涉及模块 | 依赖 |
|---|------|--------|--------|---------|------|
| B1 | `update_course()` 增加 `show_ai_score` 参数并写入 settings；`CourseView.put` 透传 validated_data | P0 | 低 | courses/logic.py + courses/views.py | A1, A2 |
| B2 | `ai_feedback_record_to_json()` 增加 `include_score` 参数（默认 True），score_json 按参数裁剪 | P0 | 低 | feedback/logic.py | — |
| B3 | `FeedbackRecordView.post` 按课程配置裁剪：STANDARD 且 show_ai_score=False → include_score=False；`get` 保持 True | P0 | 低 | feedback/views.py | A1, B2 |

### 前端任务（Frontend）

| # | 任务 | 优先级 | 复杂度 | 涉及模块 | 依赖 |
|---|------|--------|--------|---------|------|
| F1 | `course-edit-form.tsx` 新增「Show AI scores to students」SwitchField（schema + UI + Tooltip） | P0 | 低 | components/course-edit-form.tsx | A3 |
| F2 | `form-field-playtest-feedback-renderer.tsx` 渲染前按配置剥离分数区块（`stripScoresFromMarkdown` + `useGetCourseId` 获取配置） | P0 | 中 | components/form-field-playtest-feedback-renderer.tsx | A3 |

## 依赖关系

```
A1 ──► A2 ──► B1
  │
  ├──► B3 (读取 show_ai_score)
  └──► F1/F2 (通过 API 读取 showAiScore，依赖 A1/A2/A3 落库)
A3 ──► F1, F2
B2 ──► B3
```

- **Phase 09 骨架**：A1 → A2 → A3（模型 → 序列化 → 前端契约）
- **Phase 10 后端**：B2（独立）→ B1 → B3（依赖 A1/A2）
- **Phase 10 前端**：F1、F2（依赖 A3，相互独立）

## 复杂度评估

- 全任务复杂度均为低~中；核心难点在 **F2 的 Markdown 剥离函数**（需要按 LightRAG prompt 输出格式精确匹配，含兜底）
- 无外部依赖变更；无新建表（仅 CourseSettings 加字段）
