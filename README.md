# Atlas | Experiment Tracking App

[English](#english) | [中文](#中文)

---

## English

### Overview

Atlas is a Django web application for research teams to manage **research groups, projects, experiments, process steps, equipment, and raw material batches**. It focuses on traceability: each step can carry equipment, recipe, status, material usage, and upstream/downstream genealogy links.

The current UI uses a compact Atlas dashboard style with a left project sidebar, modal-first editing workflows, and a Cytoscape.js genealogy visualizer.

### Core Data Model

- **Team (`ResearchGroup`)**: Research group and access boundary. Each team owns a 3-letter team code such as `AFE`, `GNY`, or `PCA`.
- **Project Category (`ProjectCategory`)**: Optional program/category metadata used by the UI, such as `Anode-free Engineering`.
- **Project (`Project`)**: Auto-numbered team project code such as `AFE001`.
- **Experiment (`Experiment`)**: Two-letter experiment suffix under a project, such as `AA`; full experiment ID is `AFE001AA`. There is no separate business concept called "flow".
- **Experiment Step (`ExperimentStep`)**: Process step inside an experiment, such as `AFE001AA-MX00`.
- **Raw material batch**: Batch-level material record that can be attached to process steps with quantity and unit.

### Features

- **Authentication and account menu**
  - Login/logout
  - Change password
  - Compact username dropdown in the top navigation

- **Team-scoped access control**
  - Normal users only see projects and experiments in their research group.
  - Staff and superusers can access all groups.

- **Overview dashboard**
  - Counts visible projects by in-progress and completed state.
  - Tracks cumulative experiment count over time with an interactive hover tooltip.
  - Shows a recent activity block for newly created experiment IDs such as `GNY001AA`.

- **Project sidebar**
  - Compact project cards with project code, group, description, owner, and date.
  - Search across project, experiment, step, and group fields.
  - Modal-based project creation from the sidebar.

- **Experiment and step management**
  - Create/delete experiments under a project.
  - Create/edit/delete steps in a modal workflow.
  - Status support: `Planned`, `Completed`, `Canceled`.
  - Inline experiment and step description editing.
  - Bulk status updates, multi-select delete, and copy steps to another accessible experiment.

- **Step genealogy**
  - Steps can reference parent steps to preserve process lineage.
  - Genealogy opens in a modal instead of navigating away from the current page.
  - Cytoscape.js visualizer shows step nodes, raw material nodes, and directed edges.
  - Clicking a step node updates the modal content without changing the main page URL.

- **Equipment database**
  - Add, edit, list, and view equipment records.
  - Track owner, location, active state, specifications, and utility requirements.
  - Equipment can be attached to process steps.

- **Raw material database**
  - Add, edit, list, and view raw material batches.
  - Track material code, batch number, supplier, owner, location, active state, and notes.
  - Raw material detail pages show where each batch is used.

- **Global search and JSON endpoints**
  - Search full experiment IDs or step IDs and redirect to the matching page.
  - `GET /api/steps/`
  - `GET /api/raw_materials/`
  - `GET /api/experiments_with_items/`

### Tech Stack

- Python + Django 5.2
- SQLite for local development
- Bootstrap, Bootstrap Icons, jQuery, Select2, and Cytoscape.js
- Static frontend assets are vendored locally under `experiment_app/static/vendor/`

### Quick Start

#### Windows one-click setup

1. Install Python 3.10 or newer from [python.org](https://www.python.org/downloads/) and select **Add Python to PATH** during installation.
2. Extract the complete Atlas project folder.
3. Double-click `setup_and_run.bat` in the project root.
4. On the first run, follow the prompt to create an administrator account.

The script creates an isolated virtual environment, installs dependencies, applies database migrations, checks the application, opens the browser, and starts Atlas at `http://127.0.0.1:8000/`. Keep the command window open while using the app; press `Ctrl+C` to stop it. Each installation uses its own local SQLite database.

When sharing the project, leave out the `experiment_app/.venv/` folder. Virtual environments are computer-specific; the setup script creates or repairs it on the recipient's computer.

#### macOS / Linux

From the repository root:

```zsh
cd experiment_app

# Use the local environment if it exists
source .venv/bin/activate

# For a fresh clone, create your own environment first
# python3 -m venv .venv
# source .venv/bin/activate
# pip install "Django>=5.2,<6"

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open `http://127.0.0.1:8000/`.

### Useful Commands

```zsh
cd experiment_app
source .venv/bin/activate

python manage.py check
python manage.py test
python manage.py runserver 8000
```

### Notes

- No barcode module is currently active in the app.
- No JavaScript build step is required.
- The database table names still use the original legacy names for compatibility, but the Django model classes now use the current business names.
- A sample uWSGI config is available at `experiment_app/uwsgi.ini`.

---

## 中文

### 概览

Atlas 是一个基于 Django 的实验追踪应用，用于研究团队管理 **研究组、项目、实验、工艺步骤、设备和原材料批次**。它的重点是可追溯性：每个步骤都可以记录设备、配方、状态、原材料用量，以及上下游谱系关系。

当前 UI 使用紧凑的 Atlas dashboard 风格：左侧项目列表、弹窗式编辑工作流，以及基于 Cytoscape.js 的步骤谱系 visualizer。

### 核心数据模型

- **研究组 / Team (`ResearchGroup`)**：普通用户的数据访问边界；每个 Team 自带 3 位 team code，例如 `AFE`、`GNY`、`PCA`。
- **项目分类 (`ProjectCategory`)**：UI 中用于展示研究方向/分类的辅助信息，例如 `Anode-free Engineering`。
- **项目 (`Project`)**：Team code 后加三位数字形成的项目编号，例如 `AFE001`。
- **实验 (`Experiment`)**：项目编号后加两位字母形成的实验编号，例如 `AFE001AA`。当前业务概念里已经没有单独的 “flow / 流程”。
- **实验步骤 (`ExperimentStep`)**：实验中的工艺步骤，例如 `AFE001AA-MX00`。
- **原材料批次**：可按批次记录，并关联到具体步骤，包含用量和单位。

### 功能

- **登录与账户菜单**
  - 登录 / 退出登录
  - 修改密码
  - 顶部导航只显示用户名，点击后展开账户操作

- **按团队隔离数据**
  - 普通用户只能看到所属研究组的项目和实验。
  - Staff / superuser 可以访问全部研究组数据。

- **项目总览 dashboard**
  - 显示当前可见项目的进行中 / 已完成数量。
  - 用趋势图追踪实验数量随日期的累计增长，并支持鼠标悬停查看数值。
  - “最近创建”动态显示新创建的实验编号，例如 `GNY001AA`。

- **左侧项目列表**
  - 更紧凑的项目卡片，同时保留项目代码、团队、描述、owner 和日期。
  - 支持按项目、实验、步骤和研究组搜索。
  - 侧边栏可通过弹窗创建新项目。

- **实验与步骤管理**
  - 在项目下创建 / 删除实验。
  - 通过弹窗新增、编辑、删除步骤。
  - 支持 `Planned`、`Completed`、`Canceled` 状态。
  - 支持 inline 编辑实验和步骤描述。
  - 支持批量改状态、批量删除，以及复制步骤到其它可访问实验。

- **步骤谱系**
  - 步骤可以关联父步骤，用于保留工艺或样品来源。
  - 谱系以弹窗显示，不跳转到新页面。
  - Cytoscape.js visualizer 展示步骤节点、原材料节点和方向连接线。
  - 点击 visualizer 内的步骤节点会在当前弹窗内切换谱系内容。

- **设备管理**
  - 新增、编辑、列表和详情页。
  - 记录负责人、位置、启用状态、规格和水电气排风等需求。
  - 设备可关联到具体步骤。

- **原材料管理**
  - 新增、编辑、列表和详情页。
  - 记录 material code、批次号、供应商、负责人、位置、启用状态和备注。
  - 原材料详情页可查看该批次被哪些步骤使用。

- **全局搜索与 JSON 接口**
  - 可搜索完整实验编号或步骤编号，并跳转到对应页面。
  - `GET /api/steps/`
  - `GET /api/raw_materials/`
  - `GET /api/experiments_with_items/`

### 技术栈

- Python + Django 5.2
- 本地开发默认 SQLite
- Bootstrap、Bootstrap Icons、jQuery、Select2、Cytoscape.js
- 前端静态依赖 vendored 在 `experiment_app/static/vendor/`

### 快速开始

#### Windows 一键安装和启动

1. 从 [python.org](https://www.python.org/downloads/) 安装 Python 3.10 或更高版本，安装时勾选 **Add Python to PATH**。
2. 解压完整的 Atlas 项目文件夹。
3. 双击项目根目录中的 `setup_and_run.bat`。
4. 首次运行时，根据提示创建管理员账号。

脚本会自动创建独立虚拟环境、安装依赖、执行数据库迁移、检查应用、打开浏览器，并在 `http://127.0.0.1:8000/` 启动 Atlas。使用期间请保持命令窗口开启，按 `Ctrl+C` 可以停止服务。每份安装使用各自独立的本地 SQLite 数据库。

分享项目时请不要包含 `experiment_app/.venv/` 文件夹。虚拟环境与具体电脑绑定；安装脚本会在同事的电脑上自动创建或修复它。

#### macOS / Linux

在仓库根目录运行：

```zsh
cd experiment_app

# 如果本地 .venv 已存在
source .venv/bin/activate

# 如果是全新 clone，先创建环境
# python3 -m venv .venv
# source .venv/bin/activate
# pip install "Django>=5.2,<6"

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

打开 `http://127.0.0.1:8000/`。

### 常用命令

```zsh
cd experiment_app
source .venv/bin/activate

python manage.py check
python manage.py test
python manage.py runserver 8000
```

### 备注

- 当前版本不启用 barcode 模块。
- 不需要 JavaScript build step。
- 数据库表名仍保留原 legacy 名称以兼容现有数据，但 Django model class 已改为当前业务命名。
- 示例 uWSGI 配置位于 `experiment_app/uwsgi.ini`。

---

## License

No license file is currently included. Add a `LICENSE` file before distributing this project publicly.
