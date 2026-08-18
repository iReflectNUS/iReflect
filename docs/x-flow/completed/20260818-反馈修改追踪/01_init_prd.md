---
req_id: 20260818-反馈修改追踪
title: AI反馈记录与修改版本追踪（科研数据持久化）
priority: P0
created_at: 2026-08-18
keywords: [AI反馈, 修改版本, 修改追踪, 数据持久化, 科研数据, 数据采集, FeedbackInitialResponse]
related_archives: []
---

# AI反馈记录与修改版本追踪（科研数据持久化）

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
- **描述**: 学生每次保存/提交表单答案时，为文本类字段创建一条版本记录
- **用户故事**: 作为研究者，我希望学生每次修改答案都留痕，以便分析反思文本的演变过程
- **优先级**: P0
- **验收标准**:
  - [ ] 学生每次保存/提交答案，文本内容发生变化时生成新版本记录
  - [ ] 版本记录包含：学生、课程、里程碑、模板、问题、答案原文、版本号、创建时间
  - [ ] 相同内容重复保存不产生新版本 [AI 推断]
  - [ ] 版本号按时间递增，可完整还原首次→末次的所有状态

### 2.2 AI 反馈生成记录
- **描述**: 每次点击"Generate Feedback"时，持久化记录 AI 的完整输出
- **用户故事**: 作为研究者，我希望每次 AI 反馈生成都被记录，以便分析 AI 评分的准确性与反馈变化
- **优先级**: P0
- **验收标准**:
  - [ ] 每次生成 AI 反馈都写入一条记录（不再受 `unique_together` 单条限制）
  - [ ] 记录包含：评分结果（6 阶段明细或总分）、反馈内容、生成策略（Basic/Advanced/Playtest）、模型版本、Token 用量、耗时、时间戳
  - [ ] 每条 AI 反馈记录关联到**触发生成时的答案版本**
  - [ ] 兼容现有 `FeedbackInitialResponse` 旧数据，不破坏已有记录 [AI 推断]

### 2.3 数据查询接口（教师/研究者专用）
- **描述**: 提供只读 API 供教师/研究者查询修改与反馈历史
- **优先级**: P1
- **验收标准**:
  - [ ] 可按课程 / 学生 / 里程碑 / 问题维度过滤查询
  - [ ] 仅教师（Teacher）与研究者角色可访问
  - [ ] 返回包含版本时间线及每版本关联的 AI 反馈记录
  - [ ] 本次不做前端展示页面 [用户确认：仅后端存储]

## 3. 非功能需求
- **性能**: 版本记录与 AI 反馈表需建索引（creator + question + created_at），保证查询效率
- **安全**: 学生原始文本与 AI 反馈属敏感数据，仅授权角色（教师/研究者）可通过 API 访问
- **兼容性**: 现有 `FeedbackInitialResponse` 数据流（学生原文收集、前端渲染）保持不变

## 4. 约束与假设
- 现有 `FeedbackInitialResponse.unique_together` 约束需放开或改造 [关键约束]
- [AI 推断] 采用新增表存储版本与 AI 反馈记录，保留旧表兼容历史数据
- [AI 推断] 答案版本记录与 AI 反馈记录各自独立存储，通过外键关联
- [AI 推断] 学生保存答案与生成反馈的触发点均在后端已有 API 处拦截（`/api/feedback/` 与提交保存接口）

## 5. 影响范围
- **涉及服务**: backend（Django + DRF）
- **涉及模块**: `pigeonhole/feedback`（models / views / serializers / logic）
- **数据库变更**: 是（新增表；改造 `FeedbackInitialResponse` 约束）
- **前端**: 无变更（仅后端存储）
- **外部依赖**: LightRAG 路径下 Playtest 反馈的数据采集方式需评估 [见开放问题]

## 6. 开放问题
- [ ] Playtest（LightRAG）反馈目前由前端经 NGINX 直连 LightRAG，**绕过 Django**——其 AI 反馈记录需要前端上报回 Django，还是将 /api/playtest/ 改走 Django 代理？[需设计阶段决策]
- [ ] "修改提交"的触发点：是 Django 保存接口（提交/保存时）还是更细粒度（每次表单变更）？
- [ ] 答案版本表与 AI 反馈记录表是独立两张表还是一张记录表（type 区分）？
- [ ] 已有历史数据（`FeedbackInitialResponse` 中已存的学生原文）是否回填为第一个版本？

## 7. 知识库参考
- 现有 AI Review 架构: `backend/pigeonhole/feedback/{models,views,serializers,logic}.py`
- 前端反馈组件: `frontend/src/components/form-field-feedback-renderer.tsx`、`form-field-playtest-feedback-renderer.tsx`
- 表单数据模型: `backend/pigeonhole/forms/models.py`、`backend/pigeonhole/courses/models.py`
- 权限体系: `backend/pigeonhole/users/middlewares.py`（AccountType 分级）
