---
req_id: 20260818-反馈修改追踪
title: AI反馈记录与修改版本追踪（科研数据持久化）
priority: P0
created_at: 2026-08-18
keywords: [AI反馈, 修改版本, 修改追踪, 数据持久化, 科研数据, 数据采集, FeedbackInitialResponse]
related_archives: []
---

# AI反馈记录与修改版本追踪（科研数据持久化）

> 本文档为精化版 PRD，已合并 2026-08-18 澄清对话结论（共 3 项，见 `02_clarify_log.md`）。

## 1. 背景与目标

**现状问题**：
- 系统现有两套 AI Review 引擎（反思写作评分 GPT-4o、Playtest 反馈评分 LightRAG+GPT-4o），生成的评分与反馈**只存在于前端内存**，刷新即丢失，无任何数据库持久化。
- 现有 `FeedbackInitialResponse` 表通过 `unique_together = (course, milestone, template, creator, question)` 限制**每学生每问题仅一条记录**，且使用 `get_or_create` 逻辑——再次生成时旧数据不更新、新数据丢弃，无法反映学生的修改过程。

**目标**：为科研数据收集，持久化记录两部分数据：
1. **学生答案的每次修改版本**（首次→中间态→末次）
2. **每次 AI 生成的反馈记录**（评分明细 + 反馈内容 + 元数据）

并将 AI 反馈**关联到触发时的答案版本**，形成「修改-反馈」可追踪时间线，支持后续分析学生反思文本演变与 AI 反馈质量。

## 2. 功能需求

### 2.1 答案修改版本记录
- **描述**: 每次学生点击"Generate Feedback"时，快照当前答案文本生成一条版本记录 [澄清 Q2]
- **用户故事**: 作为研究者，我希望学生每次触发 AI 反馈时的答案都被快照留痕，以便分析反思文本在每次反馈迭代间的演变
- **优先级**: P0
- **验收标准**:
  - [ ] 每次点击"Generate Feedback"生成一条答案版本记录（快照当前 TextArea 内容）[澄清 Q2]
  - [ ] 版本记录包含：学生、课程、里程碑、模板、问题、答案原文、版本号、创建时间
  - [ ] 版本号按时间递增（version 1 → 2 → 3...），同一次生成会话内唯一
  - [ ] 不点击生成反馈则不产生新版本（草稿保存不触发）[澄清 Q2]

### 2.2 AI 反馈生成记录
- **描述**: 每次 AI 反馈生成成功后，持久化记录 AI 的完整输出，并关联到触发生成的答案版本
- **用户故事**: 作为研究者，我希望每次 AI 反馈生成都被记录，以便分析 AI 评分的准确性与反馈变化
- **优先级**: P0
- **验收标准**:
  - [ ] 每次生成 AI 反馈都写入一条记录（不再受 `unique_together` 单条限制）
  - [ ] 记录包含：评分结果（6 阶段明细或总分）、反馈内容、生成策略（Basic/Advanced/Playtest）、模型版本、Token 用量、耗时、时间戳
  - [ ] 每条 AI 反馈记录**关联到触发生成时的答案版本**（与 2.1 版本记录同请求写入）[澄清 Q2]
  - [ ] **Playtest（LightRAG）反馈由前端收到响应后调用 Django API 上报保存**，不改动 NGINX 代理链路 [澄清 Q1]
  - [ ] 反思写作（Feature 1）反馈在后端 `/api/feedback/` 直接落库 [推断]

### 2.3 历史数据回填
- **描述**: 将 `FeedbackInitialResponse` 中已存在的历史记录回填为 version 1 [澄清 Q3]
- **优先级**: P1
- **验收标准**:
  - [ ] 数据迁移脚本将现有 `FeedbackInitialResponse` 记录回填为每个学生/问题组合的 version 1
  - [ ] 回填的 version 1 无关联 AI 反馈记录（历史数据无 AI 输出）
  - [ ] 回填不破坏原表数据，可重复执行（幂等）[AI 推断]

### 2.4 数据查询接口（教师/研究者专用）
- **描述**: 提供只读 API 供教师/研究者查询修改与反馈历史
- **优先级**: P1
- **验收标准**:
  - [ ] 可按课程 / 学生 / 里程碑 / 问题维度过滤查询
  - [ ] 仅教师（Teacher）与研究者角色可访问
  - [ ] 返回包含版本时间线及每版本关联的 AI 反馈记录
  - [ ] 本次不做前端展示页面 [用户确认：仅后端存储]

## 3. 非功能需求
- **性能**: 版本记录与 AI 反馈表需建索引（creator + question + created_at），保证查询效率
- **安全**: 学生原始文本与 AI 反馈属敏感数据，仅授权角色（教师/研究者）可通过 API 访问；上报 API 需校验请求者身份与学生归属
- **兼容性**: 现有 `FeedbackInitialResponse` 数据流（学生原文收集、前端渲染）保持不变；前端反馈组件新增上报逻辑但不改变展示行为

## 4. 约束与假设
- 现有 `FeedbackInitialResponse.unique_together` 约束需放开或改造 [关键约束]
- [AI 推断] 采用新增表存储版本与 AI 反馈记录，保留旧表兼容历史数据
- [AI 推断] 答案版本记录与 AI 反馈记录各自独立存储，通过外键关联（version_id）
- **前端需配合改动**: 两个反馈渲染组件（`form-field-feedback-renderer.tsx` / `form-field-playtest-feedback-renderer.tsx`）在生成成功后增加上报调用 [澄清 Q1/Q2]
- 数据上报发生在**前端收到 AI 响应之后**，AI 生成失败不上报 [AI 推断]

## 5. 影响范围
- **涉及服务**: backend（Django + DRF）+ frontend（Next.js）
- **涉及模块**: `pigeonhole/feedback`（models / views / serializers / logic）+ 两个前端反馈组件 + 前端 feedback-api/playtest-api 服务
- **数据库变更**: 是（新增表；改造 `FeedbackInitialResponse` 约束；数据迁移脚本）
- **前端**: 是（反馈组件新增上报逻辑；不改 UI 展示）[澄清 Q1/Q2]
- **外部依赖**: NGINX 代理链路不变（Playtest 仍直连 LightRAG，前端上报回 Django）[澄清 Q1]

## 6. 开放问题
- [x] Playtest 反馈记录方式？→ **已解决**：前端上报回 Django [澄清 Q1]
- [x] 版本记录触发时机？→ **已解决**：点击 Generate Feedback 时快照 [澄清 Q2]
- [x] 历史数据是否回填？→ **已解决**：回填为 version 1 [澄清 Q3]
- [ ] 答案版本表与 AI 反馈记录表是独立两张表还是一张记录表（type 区分）？[设计阶段决策]
- [ ] Playtest 反馈记录的评分/Token 用量字段如何获得（LightRAG 响应结构）？[设计阶段探索]
- [ ] 版本号唯一性约束：同一 (course, milestone, template, creator, question) 内 version 递增的并发安全？[设计阶段决策]

## 7. 知识库参考
- 现有 AI Review 架构: `backend/pigeonhole/feedback/{models,views,serializers,logic}.py`
- 前端反馈组件: `frontend/src/components/form-field-feedback-renderer.tsx`、`form-field-playtest-feedback-renderer.tsx`
- 前端 API 服务: `frontend/src/redux/services/feedback-api.ts`、`playtest-api.ts`
- 表单数据模型: `backend/pigeonhole/forms/models.py`、`backend/pigeonhole/courses/models.py`
- 权限体系: `backend/pigeonhole/users/middlewares.py`（AccountType 分级）
