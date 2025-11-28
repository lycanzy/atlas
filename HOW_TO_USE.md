# ETA App User Guide / ETA 应用使用指南

[English](#english) | [中文](#chinese)

---

<a name="english"></a>
# 🇬🇧 ETA App User Guide

## Introduction
The **Experiment Tracking App (ETA)** is designed to help research groups efficiently manage their projects, experiments, and experimental workflows. It allows for detailed tracking of steps, equipment usage, and cross-experiment dependencies.

## Key Concepts
*   **Project**: The top-level category (e.g., "Solar Cell Research").
*   **Experiment (Exp)**: A specific experimental run belonging to a project. Names are auto-generated (e.g., `PROJ001`).
*   **Flow**: A sequence of steps within an experiment, identified by a 2-letter code (e.g., `AA`). Full ID: `PROJ001AA`.
*   **Step**: A single action within a flow. Steps can be linked to *any* previous step from any experiment to create a history chain. Full ID: `PROJ001AA-BB01`.

## Getting Started

### 1. Login
*   Access the login page.
*   Enter your username and password.
*   **Note**: You will only see experiments and projects that belong to your **Research Group**.

### 2. The Dashboard
*   After logging in, you will see the **Dashboard**.
*   This lists the latest experiments from your group.
*   You can **Search** for experiments by name or description.

## Managing Experiments

### Create a New Experiment
1.  Click the **"Add Experiment"** button.
2.  Select a **Project** from the dropdown list.
3.  Enter a **Description** (optional but recommended).
4.  Click **Save**. The system will automatically generate a unique Experiment Name (e.g., `SOL005`).

### Viewing an Experiment
*   Click on an experiment name in the dashboard to view its details.
*   You will see a list of **Flows** and **Steps**.

## Managing Flows and Steps

### Adding a Flow
1.  Inside an experiment, click **"Add Flow"**.
2.  Enter a **2-letter code** (e.g., `AA`, `BB`).
3.  The flow will be created (e.g., `SOL005AA`).

### Adding a Step
1.  Click the **"+" (Add Step)** button next to a Flow.
2.  **Step Name**: Enter a 2-letter code for the step type (e.g., `CL` for Cleaning).
3.  **Previous Step (Crucial Feature)**:
    *   You can link this step to a parent step.
    *   **Search**: Type to search for *any* step from *any* experiment in the system.
    *   This allows you to continue a sample's history from a different experiment.
4.  **Equipment**: Select the tool/equipment used.
5.  **Status**: Set to "Planned", "Completed", or "Canceled".
6.  **Components**: Add any materials used.

### Managing Steps
*   **Edit**: Click the edit icon to change details.
*   **Status**: You can quickly update the status (e.g., mark as Completed).
*   **Copy Steps**: You can select multiple steps and copy them to another flow.

## Equipment Management
*   Navigate to the **Equipment** section.
*   You can **Add**, **Edit**, or **View** details of lab equipment.
*   Equipment can be linked to specific steps to track usage.

## Barcodes
*   **Flow Barcodes**: Generate a printable barcode for an entire flow.
*   **Step Barcodes**: Generate a barcode for a specific step.
*   These can be used for physical tracking of samples in the lab.

---

<a name="chinese"></a>
# 🇨🇳 ETA 应用使用指南

## 简介
**实验跟踪应用 (ETA)** 旨在帮助研究小组高效管理项目、实验和实验工作流。它支持对实验步骤、设备使用情况以及跨实验的依赖关系进行详细跟踪。

## 核心概念
*   **项目 (Project)**: 最高层级的分类 (例如：“太阳能电池研究”)。
*   **实验 (Experiment)**: 属于某个项目的具体实验运行。名称由系统自动生成 (例如：`PROJ001`)。
*   **流程 (Flow)**: 实验中的一系列步骤序列，由2个字母的代码标识 (例如：`AA`)。完整ID：`PROJ001AA`。
*   **步骤 (Step)**: 流程中的单个操作。步骤可以链接到系统中*任何*实验的*任何*前置步骤，从而创建完整的历史链条。完整ID：`PROJ001AA-BB01`。

## 入门指南

### 1. 登录 (Login)
*   访问登录页面。
*   输入您的用户名和密码。
*   **注意**: 您只能看到属于您所在**研究小组 (Research Group)** 的实验和项目。

### 2. 仪表盘 (Dashboard)
*   登录后，您将看到**仪表盘**。
*   这里列出了您小组的最新实验。
*   您可以按名称或描述**搜索**实验。

## 管理实验

### 创建新实验
1.  点击 **"Add Experiment" (添加实验)** 按钮。
2.  从下拉列表中选择一个 **Project (项目)**。
3.  输入 **Description (描述)** (可选，但建议填写)。
4.  点击 **Save (保存)**。系统将自动生成唯一的实验名称 (例如：`SOL005`)。

### 查看实验
*   在仪表盘中点击实验名称以查看详情。
*   您将看到该实验下的 **Flows (流程)** 和 **Steps (步骤)** 列表。

## 管理流程和步骤

### 添加流程 (Flow)
1.  在实验详情页，点击 **"Add Flow" (添加流程)**。
2.  输入一个 **2字母代码** (例如：`AA`, `BB`)。
3.  流程将被创建 (例如：`SOL005AA`)。

### 添加步骤 (Step)
1.  点击流程旁边的 **"+" (添加步骤)** 按钮。
2.  **Step Name (步骤名称)**: 输入步骤类型的2字母代码 (例如：`CL` 代表清洗)。
3.  **Previous Step (前置步骤 - 核心功能)**:
    *   您可以将此步骤链接到一个父步骤。
    *   **搜索**: 输入文字以搜索系统中的*任何*实验的*任何*步骤。
    *   这允许您延续来自不同实验的样品的历史记录。
4.  **Equipment (设备)**: 选择使用的工具/设备。
5.  **Status (状态)**: 设置为 "Planned" (计划中), "Completed" (已完成), 或 "Canceled" (已取消)。
6.  **Components (组件)**: 添加使用的材料。

### 管理步骤
*   **编辑**: 点击编辑图标以更改详情。
*   **状态**: 您可以快速更新状态 (例如：标记为已完成)。
*   **复制步骤**: 您可以选择多个步骤并将它们复制到另一个流程中。

## 设备管理 (Equipment)
*   导航至 **Equipment (设备)** 部分。
*   您可以 **添加**、**编辑** 或 **查看** 实验室设备的详情。
*   设备可以链接到具体的步骤以跟踪使用情况。

## 条形码 (Barcodes)
*   **流程条形码**: 为整个流程生成可打印的条形码。
*   **步骤条形码**: 为特定步骤生成条形码。
*   这些条形码可用于实验室中样品的物理跟踪。
