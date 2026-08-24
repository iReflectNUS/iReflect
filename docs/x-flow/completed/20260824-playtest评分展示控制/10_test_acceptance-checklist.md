# 验收清单 — 20260824-playtest评分展示控制

> req_id: 20260824-playtest评分展示控制 | 阶段: TEST_VERDICT
> 关联: PRD §3 验收标准（docs/prd/20260824-playtest评分展示控制.md）

## §3.1 课程级展示模式配置

| 验收标准 | 证据 | 结果 |
|---------|------|------|
| 课程设置页出现「AI 评分展示」开关（分数+建议 / 仅建议） | 课程创建/编辑表单新增 `AI Feedback Settings` 区块（SwitchField + Tooltip） | ✅ |
| 默认值为「仅建议」，新建课程即生效 | 模型 `default=False` + 前端 `DEFAULT_VALUES.showAiScore=false`；Serializer 回读缺省 False | ✅ |
| 保存后配置持久化 | `CourseSettings.show_ai_score` 落库；E2E step1/step5 PUT 200 + DB 核对 `(course 2, show_ai_score=1)` | ✅ |
| 非教师角色无法修改（403 或 UI 不可见） | PUT `/courses/{id}/` 沿用 `check_account_access`（CO-OWNER/OWNER 成员级）；配置控件仅在教师表单出现 | ✅ |

## §3.2 学生端按配置渲染反馈

| 验收标准 | 证据 | 结果 |
|---------|------|------|
| 「分数+建议」时学生端展示分数与文字建议 | E2E step5：翻转后 REPLAY `scoreJson={'total':91}` | ✅ |
| 「仅建议」时不显示任何数字分数（总分与分维度全隐藏） | 前端 `stripScoresFromMarkdown`（`**Professor Feedback:**` 锚点截断 + 行正则兜底）；E2E step3：`scoreJson=None` | ✅ |
| 仅建议模式不出现分数占位符/空值显示 | 剥离逻辑整段移除 Score 行，node 样例 3 组通过 | ✅ |
| 教师修改后历史反馈立即生效（无需刷新旧数据） | 「读取时动态裁剪」实现；E2E step3/step5 **同一记录**翻转前后行为变化 | ✅ |

## §3.3 后端强制过滤（安全）

| 验收标准 | 证据 | 结果 |
|---------|------|------|
| 「仅建议」时学生角色响应不含 score_json | `FeedbackRecordView.post`：STANDARD 且 `show_ai_score=False` → `include_score=False` → `score_json=None` | ✅ |
| 教师/管理员响应不受影响，始终含完整分数 | `include_score=True` 默认分支；E2E step4：教师 GET `scoreJson={'total':88}` | ✅ |
| E2E 实测：仅建议无分数，切回后同接口出现分数 | E2E step3（无）→ step5（有），LT-012 真实 HTTP | ✅ |

## 非功能需求

| 项 | 证据 | 结果 |
|----|------|------|
| 安全：后端兜底而非仅前端隐藏 | 后端 `include_score` 裁剪 + 前端剥离双保险；EV-001 越权经验引用 | ✅ |
| 兼容性：旧课程无需数据迁移 | `show_ai_score` 新增字段 default=False，迁移 0005 仅 AddField | ✅ |
| 性能：不引入 N+1 | 配置读取为单记录 reverse OneToOne 查询（每请求一次），无列表 N+1 新增 | ✅ |

## 结论

**全部验收标准通过。** 测试报告见 `09_test_report.md`。
