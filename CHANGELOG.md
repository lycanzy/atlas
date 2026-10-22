# 更新日志

本文件记录 Atlas 每个可发布版本中对用户可见的变化，格式遵循 Keep a Changelog 的简化约定。

Bug 修复条目统一以 `[bug fix]` 标记，并说明具体问题及修复后的表现；自动生成日志时，修复类提交标题也使用该标记。

## [Unreleased]

## [v0.1.7-alpha] - 2026-10-22

### 新增

- 步骤操作栏新增“表征数据”按钮，点击后进入图像数据页面并自动按当前步骤编号搜索。


### 提交记录

- Add characterization uploads and improve image search

## [v0.1.6-alpha] - 2026-10-14

### 提交记录

- docs: clarify bug fix entry in v0.1.5 changelog

## [v0.1.5-alpha] - 2026-10-14

### 问题修复

- [bug fix] 修正前置步骤选择的提示文案，明确普通用户也可跨团队搜索和选择历史步骤；补充新增、编辑步骤时跨团队关联的回归测试，确保该行为持续可用。

## [v0.1.4-alpha] - 2026-09-23

### 提交记录

- Add sample image viewer, cell active material mass, and reliable project numbering

## [v0.1.3-alpha] - 2026-09-07

### 提交记录

- Add experiment activity dashboard and workflow refinements

## [v0.1.2-alpha] - 2026-09-02

### 新增

- 推送到 `main` 时，GitHub Actions 会收集本次 push 的提交标题，将非空的 `[Unreleased]` 固化为带日期的下一个补丁版本，并自动创建新的空 `[Unreleased]` 区域；空区域不会显示在更新日志页面上。
- 实验详情页的“新增实验”“新增步骤”“编辑实验步骤”和删除确认窗口支持在桌面端拖动；拖动位置受可视标题栏约束，关闭后恢复居中。
- 首页概览支持在“我的”和“全局”数据范围之间切换，并保持项目列表与详情的既有访问边界。
- 新增 14、30、90 天实验增长趋势，以及计划步骤、已完成步骤和电芯关联状态等真实指标。
- 新增更新日志页面和 GitHub 自动校验，确保应用变更同步更新本文件。
- 新增 Project 级用户授权：负责人可授权自己 Team 的项目，Superuser 可授权任意项目，授权变更同时写入审计日志。
- 团队和成员管理新增“负责人”角色展示；负责人拥有受 Team 范围限制的项目授权管理入口。
- 首页新增精选教程卡片和常用帮助入口，并加入配套的本地教程图片资源。

### 变更

- 更新日志提交记录改由 GitHub 发布工作流生成，避免本地 Git 钩子在提交后遗留未提交的日志改动。
- 弹窗拖动采用无第三方依赖的 Pointer Events 实现，并增加选定弹窗标记、静态资源缓存版本和视图回归测试。
- 首页采用中文时段问候、精简概览面板、精选教程和常用帮助布局。
- 普通用户现在可以通过“全局”查看所有团队正在进行的实验数量、汇总指标与实验趋势；项目列表和详情权限仍限定在所属团队。
- 电芯的“Package 号”统一更名为“测试单号”，覆盖数据库字段、录入编辑、搜索、谱系展示、管理页面与审计快照。
- 项目可见范围在原有同 Team 自动访问基础上，增加显式授权项目，并同步应用于项目详情、步骤、样品关联和相关 API。

### 维护

- 移除已跟踪的 Codex/设计 QA 临时截图和报告，并忽略 `.codex_tmp/` 与 `design-qa.md`，避免后续将本地验证产物提交到仓库。

### 提交记录

- Automate changelog patch releases
- Make experiment modals draggable and clean QA artifacts
- Add project access controls and refresh Atlas dashboard
