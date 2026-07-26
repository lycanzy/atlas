(() => {
    "use strict";

    const workspace = document.getElementById("insightsWorkspace");
    if (!workspace) return;

    const elements = {
        form: document.getElementById("insightsForm"),
        question: document.getElementById("insightsQuestion"),
        submit: document.getElementById("insightsSubmit"),
        messages: document.getElementById("insightsMessages"),
        history: document.getElementById("insightsHistory"),
        historyEmpty: document.getElementById("insightsHistoryEmpty"),
        clearHistory: document.getElementById("clearInsightsHistory"),
        empty: document.getElementById("insightsResultEmpty"),
        loading: document.getElementById("insightsResultLoading"),
        unavailable: document.getElementById("insightsResultUnavailable"),
        content: document.getElementById("insightsResultContent"),
        scope: document.getElementById("insightsScope"),
        dataSource: document.getElementById("insightsDataSource"),
        summary: document.getElementById("insightsSummaryTitle"),
        visualizationSection: document.getElementById("insightsVisualizationSection"),
        visualizations: document.getElementById("insightsVisualizations"),
        rowCount: document.getElementById("insightsRowCount"),
        tableHead: document.getElementById("insightsTableHead"),
        tableBody: document.getElementById("insightsTableBody"),
        sql: document.getElementById("insightsSql"),
        copySql: document.getElementById("copyInsightsSql"),
    };

    const demoResponses = {
        "pca001-capacity": {
            answer: "PCA001 在 2026 年 4–6 月的首圈克容量均值为 181.9 mAh/g，较 1–3 月的 176.8 mAh/g 提升 2.9%。样本量由 42 颗增加到 58 颗，标准差由 8.1 降至 6.4 mAh/g。该结果展示相关性，仍需结合配方和工艺变更确认原因。",
            sql: `SELECT
    CASE
        WHEN fcm.tested_on BETWEEN :period_1_start AND :period_1_end THEN '2026 Q1'
        WHEN fcm.tested_on BETWEEN :period_2_start AND :period_2_end THEN '2026 Q2'
    END AS period,
    COUNT(DISTINCT c.id) AS cell_count,
    ROUND(AVG(fcm.specific_discharge_capacity_mah_g), 1) AS avg_specific_capacity,
    ROUND(STDDEV_POP(fcm.specific_discharge_capacity_mah_g), 1) AS capacity_stddev
FROM analytics_cell_first_cycle_metric AS fcm
JOIN experiment_flow_cell AS c ON c.barcode = fcm.cell_barcode
JOIN experiment_flow_expstep AS es ON es.id = c.step_id
JOIN experiment_flow_expflow AS e ON e.id = es.experiment_id
JOIN experiment_flow_exp AS p ON p.id = e.project_id
JOIN experiment_flow_project AS pc ON pc.id = p.project_id
WHERE pc.group_id = :research_group_id
  AND p.exp_name = 'PCA001'
  AND fcm.tested_on BETWEEN :period_1_start AND :period_2_end
GROUP BY period
ORDER BY period
LIMIT 100;`,
            columns: [
                { key: "period", label: "对比周期" },
                { key: "cells", label: "电芯数量" },
                { key: "capacity", label: "平均克容量" },
                { key: "stddev", label: "标准差" },
                { key: "change", label: "相对变化" },
            ],
            rows: [
                { period: "2026 年 1–3 月", cells: 42, capacity: "176.8 mAh/g", stddev: "8.1 mAh/g", change: "基准" },
                { period: "2026 年 4–6 月", cells: 58, capacity: "181.9 mAh/g", stddev: "6.4 mAh/g", change: "+2.9%" },
            ],
            visualizations: [{
                kind: "line",
                title: "PCA001 月度首圈克容量均值",
                x_axis: "制备月份",
                y_axis: "首圈克容量 (mAh/g)",
                categories: ["1 月", "2 月", "3 月", "4 月", "5 月", "6 月"],
                y_min: 170,
                y_max: 186,
                summary: "PCA001 月度首圈克容量从 1 月的 176.1 mAh/g 上升至 6 月的 184.2 mAh/g。",
                series: [{
                    name: "PCA001",
                    unit: "mAh/g",
                    color: "#2f66d0",
                    data: [176.1, 176.9, 177.4, 179.8, 181.7, 184.2],
                }],
            }],
            metadata: { row_count: 2, truncated: false, scope: "当前 Team", source: "模拟电化学数据" },
        },
        "gm001-cycling": {
            answer: "GM001 历史上可追溯至 126 颗电芯，其中 48 颗搭配 FS02 正极。FS02 组合在第 100、300、500 圈的容量保持率分别为 96.2%、90.8% 和 86.7%，均高于其他正极组合；到第 500 圈优势扩大到 7.8 个百分点。",
            sql: `SELECT
    ccr.cycle_number,
    CASE WHEN cathode.material_code = 'FS02' THEN 'GM001 × FS02'
         ELSE 'GM001 × 其他正极' END AS material_pair,
    COUNT(DISTINCT genealogy.cell_barcode) AS cell_count,
    ROUND(AVG(ccr.discharge_capacity_retention_pct), 1) AS avg_retention_pct
FROM analytics_cell_material_genealogy AS genealogy
JOIN analytics_cell_cycle_result AS ccr
  ON ccr.cell_barcode = genealogy.cell_barcode
JOIN experiment_flow_rawmaterial AS anode
  ON anode.id = genealogy.anode_material_id
JOIN experiment_flow_rawmaterial AS cathode
  ON cathode.id = genealogy.cathode_material_id
WHERE genealogy.research_group_id = :research_group_id
  AND anode.material_code = 'GM001'
  AND ccr.cycle_number IN (1, 100, 200, 300, 400, 500)
GROUP BY ccr.cycle_number, material_pair
ORDER BY ccr.cycle_number, material_pair
LIMIT 100;`,
            columns: [
                { key: "cycle", label: "循环圈数" },
                { key: "fs02", label: "GM001 × FS02" },
                { key: "other", label: "GM001 × 其他正极" },
                { key: "difference", label: "FS02 优势" },
            ],
            rows: [
                { cycle: "第 1 圈", fs02: "100.0%（48 颗）", other: "100.0%（78 颗）", difference: "0.0 pp" },
                { cycle: "第 100 圈", fs02: "96.2%", other: "94.1%", difference: "+2.1 pp" },
                { cycle: "第 300 圈", fs02: "90.8%", other: "85.6%", difference: "+5.2 pp" },
                { cycle: "第 500 圈", fs02: "86.7%", other: "78.9%", difference: "+7.8 pp" },
            ],
            visualizations: [{
                kind: "line",
                title: "GM001 电芯容量保持率",
                x_axis: "循环圈数",
                y_axis: "容量保持率 (%)",
                categories: ["1", "100", "200", "300", "400", "500"],
                y_min: 75,
                y_max: 101,
                summary: "GM001 搭配 FS02 的容量保持率在 100 至 500 圈持续高于其他正极组合，第 500 圈高 7.8 个百分点。",
                series: [
                    { name: "GM001 × FS02（48 颗）", unit: "%", color: "#168a5b", data: [100, 96.2, 93.3, 90.8, 88.7, 86.7] },
                    { name: "GM001 × 其他正极（78 颗）", unit: "%", color: "#8290a3", data: [100, 94.1, 89.6, 85.6, 82.2, 78.9] },
                ],
            }],
            metadata: { row_count: 4, truncated: false, scope: "当前 Team", source: "模拟电化学数据" },
        },
        "gm001-formulas": {
            answer: "FS03 的首圈克容量最高（183.5 mAh/g），但 FS02 的首效最高（90.7%），且 300 圈容量保持率达到 90.8%，分别比 FS01 和 FS03 高 6.0 和 4.7 个百分点。综合初始性能与循环稳定性，FS02 是三组中更均衡的方案。",
            sql: `SELECT
    cathode.material_code AS cathode_code,
    COUNT(DISTINCT genealogy.cell_barcode) AS cell_count,
    ROUND(AVG(fcm.specific_discharge_capacity_mah_g), 1) AS first_capacity_mah_g,
    ROUND(AVG(fcm.first_cycle_efficiency_pct), 1) AS first_efficiency_pct,
    ROUND(AVG(ccr.discharge_capacity_retention_pct), 1) AS cycle_300_retention_pct
FROM analytics_cell_material_genealogy AS genealogy
JOIN experiment_flow_rawmaterial AS anode
  ON anode.id = genealogy.anode_material_id
JOIN experiment_flow_rawmaterial AS cathode
  ON cathode.id = genealogy.cathode_material_id
JOIN analytics_cell_first_cycle_metric AS fcm
  ON fcm.cell_barcode = genealogy.cell_barcode
JOIN analytics_cell_cycle_result AS ccr
  ON ccr.cell_barcode = genealogy.cell_barcode AND ccr.cycle_number = 300
WHERE genealogy.research_group_id = :research_group_id
  AND anode.material_code = 'GM001'
  AND cathode.material_code IN ('FS01', 'FS02', 'FS03')
GROUP BY cathode.material_code
ORDER BY cathode.material_code
LIMIT 100;`,
            columns: [
                { key: "formula", label: "材料组合" },
                { key: "cells", label: "电芯数量" },
                { key: "capacity", label: "首圈克容量" },
                { key: "efficiency", label: "首效" },
                { key: "retention", label: "300 圈保持率" },
            ],
            rows: [
                { formula: "GM001 × FS01", cells: 34, capacity: "178.6 mAh/g", efficiency: "89.4%", retention: "84.8%" },
                { formula: "GM001 × FS02", cells: 48, capacity: "181.2 mAh/g", efficiency: "90.7%", retention: "90.8%" },
                { formula: "GM001 × FS03", cells: 29, capacity: "183.5 mAh/g", efficiency: "88.9%", retention: "86.1%" },
            ],
            visualizations: [
                {
                    kind: "bar",
                    title: "首圈克容量对比",
                    x_axis: "正极配方",
                    y_axis: "首圈克容量 (mAh/g)",
                    categories: ["FS01", "FS02", "FS03"],
                    y_min: 170,
                    y_max: 186,
                    summary: "FS03 的首圈克容量最高，为 183.5 mAh/g；FS02 为 181.2 mAh/g。",
                    series: [{ name: "首圈克容量", unit: "mAh/g", color: "#2f66d0", data: [178.6, 181.2, 183.5] }],
                },
                {
                    kind: "bar",
                    title: "300 圈容量保持率对比",
                    x_axis: "正极配方",
                    y_axis: "容量保持率 (%)",
                    categories: ["FS01", "FS02", "FS03"],
                    y_min: 80,
                    y_max: 93,
                    summary: "FS02 的 300 圈容量保持率最高，为 90.8%。",
                    series: [{ name: "300 圈保持率", unit: "%", color: "#168a5b", data: [84.8, 90.8, 86.1] }],
                },
            ],
            metadata: { row_count: 3, truncated: false, scope: "当前 Team", source: "模拟电化学数据" },
        },
    };

    const questionToDemo = new Map(
        Array.from(document.querySelectorAll(".insights-suggestion")).map((button) => [
            normalizeQuestion(button.dataset.question),
            button.dataset.demoKey,
        ])
    );
    const sessionHistory = [];
    const initialMessages = elements.messages.innerHTML;

    function normalizeQuestion(value) {
        return value.trim().replace(/\s+/g, " ");
    }

    function wait(milliseconds) {
        return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
    }

    async function queryInsights(payload) {
        if (workspace.dataset.queryMode === "mock") {
            await wait(650);
            const demoKey = payload.demo_key || questionToDemo.get(normalizeQuestion(payload.question));
            return demoResponses[demoKey] || { unavailable: true };
        }

        const response = await fetch(workspace.dataset.queryEndpoint, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCookie("csrftoken"),
            },
            body: JSON.stringify(payload),
        });
        if (!response.ok) throw new Error(`Insights request failed (${response.status})`);
        return response.json();
    }

    function getCookie(name) {
        return document.cookie
            .split(";")
            .map((cookie) => cookie.trim())
            .find((cookie) => cookie.startsWith(`${name}=`))
            ?.split("=")
            .slice(1)
            .join("=") || "";
    }

    function setResultState(state) {
        elements.empty.hidden = state !== "empty";
        elements.loading.hidden = state !== "loading";
        elements.unavailable.hidden = state !== "unavailable";
        elements.content.hidden = state !== "content";
        elements.scope.hidden = state !== "content";
        elements.dataSource.hidden = state !== "content";
    }

    function appendMessage(role, text, loading = false) {
        const article = document.createElement("article");
        article.className = `insights-message insights-message-${role}`;
        if (role === "assistant") {
            const avatar = document.createElement("div");
            avatar.className = "message-avatar";
            avatar.setAttribute("aria-hidden", "true");
            avatar.innerHTML = '<i class="bi bi-stars"></i>';
            article.appendChild(avatar);
        }

        const bubble = document.createElement("div");
        bubble.className = loading ? "message-bubble message-bubble-loading" : "message-bubble";
        if (loading) {
            bubble.setAttribute("aria-label", "正在生成回答");
            bubble.innerHTML = "<span></span><span></span><span></span>";
        } else {
            bubble.textContent = text;
        }
        article.appendChild(bubble);
        elements.messages.appendChild(article);
        elements.messages.scrollTop = elements.messages.scrollHeight;
        return article;
    }

    function renderHistory() {
        elements.history.replaceChildren();
        sessionHistory.forEach((item) => {
            const entry = document.createElement("li");
            const button = document.createElement("button");
            button.type = "button";
            button.textContent = item.question;
            button.title = item.question;
            button.addEventListener("click", () => {
                elements.question.value = item.question;
                elements.question.focus();
                renderResult(item.response);
            });
            entry.appendChild(button);
            elements.history.appendChild(entry);
        });
        const hasHistory = sessionHistory.length > 0;
        elements.historyEmpty.hidden = hasHistory;
        elements.clearHistory.disabled = !hasHistory;
    }

    function createSvgElement(name, attributes = {}) {
        const element = document.createElementNS("http://www.w3.org/2000/svg", name);
        Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, String(value)));
        return element;
    }

    function renderVisualization(visualization) {
        const figure = document.createElement("figure");
        figure.className = "insights-chart-card";

        const heading = document.createElement("figcaption");
        heading.className = "insights-chart-heading";
        const headingText = document.createElement("div");
        const title = document.createElement("h4");
        title.textContent = visualization.title;
        const axisDescription = document.createElement("span");
        axisDescription.textContent = `${visualization.x_axis} · ${visualization.y_axis}`;
        headingText.append(title, axisDescription);

        const legend = document.createElement("div");
        legend.className = "insights-chart-legend";
        visualization.series.forEach((series) => {
            const item = document.createElement("span");
            const swatch = document.createElement("i");
            swatch.style.backgroundColor = series.color;
            item.append(swatch, document.createTextNode(series.name));
            legend.appendChild(item);
        });
        heading.append(headingText, legend);
        figure.appendChild(heading);

        const chartScroller = document.createElement("div");
        chartScroller.className = "insights-chart-scroll";
        const svg = createSvgElement("svg", {
            class: "insights-chart",
            viewBox: "0 0 620 260",
            role: "img",
            "aria-label": visualization.summary,
            preserveAspectRatio: "xMidYMid meet",
        });
        const accessibleTitle = createSvgElement("title");
        accessibleTitle.textContent = visualization.summary;
        svg.appendChild(accessibleTitle);

        const width = 620;
        const height = 260;
        const margin = { top: 24, right: 18, bottom: 48, left: 54 };
        const plotWidth = width - margin.left - margin.right;
        const plotHeight = height - margin.top - margin.bottom;
        const allValues = visualization.series.flatMap((series) => series.data);
        const dataMin = Math.min(...allValues);
        const dataMax = Math.max(...allValues);
        const yMin = visualization.y_min ?? Math.min(0, dataMin);
        const yMax = visualization.y_max ?? Math.max(dataMax, yMin + 1);
        const yRange = yMax - yMin || 1;
        const xForIndex = (index) => {
            if (visualization.categories.length === 1) return margin.left + plotWidth / 2;
            return margin.left + (index / (visualization.categories.length - 1)) * plotWidth;
        };
        const categoryX = (index) => visualization.kind === "bar"
            ? margin.left + ((index + 0.5) / visualization.categories.length) * plotWidth
            : xForIndex(index);
        const yForValue = (value) => margin.top + ((yMax - value) / yRange) * plotHeight;

        for (let tick = 0; tick <= 4; tick += 1) {
            const value = yMin + (yRange * tick / 4);
            const y = yForValue(value);
            svg.appendChild(createSvgElement("line", {
                x1: margin.left,
                y1: y,
                x2: width - margin.right,
                y2: y,
                class: "chart-grid-line",
            }));
            const label = createSvgElement("text", {
                x: margin.left - 9,
                y: y + 4,
                class: "chart-axis-label chart-y-label",
                "text-anchor": "end",
            });
            label.textContent = Number.isInteger(value) ? String(value) : value.toFixed(1);
            svg.appendChild(label);
        }

        visualization.categories.forEach((category, index) => {
            const label = createSvgElement("text", {
                x: categoryX(index),
                y: height - 21,
                class: "chart-axis-label chart-x-label",
                "text-anchor": "middle",
            });
            label.textContent = category;
            svg.appendChild(label);
        });

        if (visualization.kind === "line") {
            visualization.series.forEach((series) => {
                const points = series.data.map((value, index) => `${xForIndex(index)},${yForValue(value)}`).join(" ");
                const line = createSvgElement("polyline", {
                    points,
                    fill: "none",
                    stroke: series.color,
                    "stroke-width": 3,
                    "stroke-linecap": "round",
                    "stroke-linejoin": "round",
                    class: "chart-series-line",
                });
                svg.appendChild(line);

                series.data.forEach((value, index) => {
                    const point = createSvgElement("circle", {
                        cx: xForIndex(index),
                        cy: yForValue(value),
                        r: 4.5,
                        fill: "#ffffff",
                        stroke: series.color,
                        "stroke-width": 2.5,
                        class: "chart-data-point",
                    });
                    const tooltip = createSvgElement("title");
                    tooltip.textContent = `${series.name} · ${visualization.categories[index]}：${value} ${series.unit}`;
                    point.appendChild(tooltip);
                    svg.appendChild(point);
                });
            });
        } else if (visualization.kind === "bar") {
            const groupWidth = plotWidth / visualization.categories.length;
            const availableWidth = Math.min(groupWidth * 0.68, 72);
            const barWidth = availableWidth / visualization.series.length;
            visualization.categories.forEach((category, categoryIndex) => {
                visualization.series.forEach((series, seriesIndex) => {
                    const value = series.data[categoryIndex];
                    const x = margin.left + categoryIndex * groupWidth + (groupWidth - availableWidth) / 2 + seriesIndex * barWidth;
                    const y = yForValue(value);
                    const baseline = yForValue(yMin);
                    const bar = createSvgElement("rect", {
                        x,
                        y,
                        width: Math.max(barWidth - 5, 8),
                        height: Math.max(baseline - y, 1),
                        rx: 4,
                        fill: series.color,
                        class: "chart-series-bar",
                    });
                    const tooltip = createSvgElement("title");
                    tooltip.textContent = `${series.name} · ${category}：${value} ${series.unit}`;
                    bar.appendChild(tooltip);
                    svg.appendChild(bar);

                    const valueLabel = createSvgElement("text", {
                        x: x + Math.max(barWidth - 5, 8) / 2,
                        y: y - 7,
                        class: "chart-value-label",
                        "text-anchor": "middle",
                    });
                    valueLabel.textContent = String(value);
                    svg.appendChild(valueLabel);
                });
            });
        }

        chartScroller.appendChild(svg);
        const summary = document.createElement("p");
        summary.className = "visually-hidden";
        summary.textContent = visualization.summary;
        figure.append(chartScroller, summary);
        return figure;
    }

    function renderVisualizations(visualizations = []) {
        elements.visualizations.replaceChildren();
        visualizations.forEach((visualization) => {
            elements.visualizations.appendChild(renderVisualization(visualization));
        });
        elements.visualizationSection.hidden = visualizations.length === 0;
    }

    function renderResult(response) {
        elements.summary.textContent = response.answer;
        elements.scope.lastChild.textContent = ` ${response.metadata.scope}`;
        elements.dataSource.lastChild.textContent = ` ${response.metadata.source || "模拟电化学数据"}`;
        elements.rowCount.textContent = `${response.metadata.row_count} 行${response.metadata.truncated ? " · 已截断" : ""}`;
        elements.sql.textContent = response.sql;
        elements.tableHead.replaceChildren();
        elements.tableBody.replaceChildren();
        renderVisualizations(response.visualizations);

        const headerRow = document.createElement("tr");
        response.columns.forEach((column) => {
            const cell = document.createElement("th");
            cell.scope = "col";
            cell.textContent = column.label;
            headerRow.appendChild(cell);
        });
        elements.tableHead.appendChild(headerRow);

        response.rows.forEach((row) => {
            const tableRow = document.createElement("tr");
            response.columns.forEach((column) => {
                const cell = document.createElement("td");
                cell.textContent = row[column.key] ?? "—";
                tableRow.appendChild(cell);
            });
            elements.tableBody.appendChild(tableRow);
        });
        setResultState("content");
    }

    async function submitQuestion(question, demoKey = "") {
        const normalized = normalizeQuestion(question);
        if (!normalized || elements.submit.disabled) return;

        elements.question.value = "";
        elements.submit.disabled = true;
        elements.messages.setAttribute("aria-busy", "true");
        appendMessage("user", normalized);
        const loadingMessage = appendMessage("assistant", "", true);
        setResultState("loading");

        try {
            const response = await queryInsights({
                question: normalized,
                demo_key: demoKey,
                conversation: sessionHistory.map((item) => ({ question: item.question })),
            });
            loadingMessage.remove();

            if (response.unavailable) {
                appendMessage("assistant", "这个问题还没有演示数据。接入 AI API 后，我会将它转换为受控的只读查询。");
                setResultState("unavailable");
                return;
            }

            appendMessage("assistant", response.answer);
            sessionHistory.push({ question: normalized, response });
            renderHistory();
            renderResult(response);
        } catch (error) {
            loadingMessage.remove();
            appendMessage("assistant", "暂时无法完成分析，请稍后重试。");
            setResultState("unavailable");
            console.error(error);
        } finally {
            elements.submit.disabled = false;
            elements.messages.setAttribute("aria-busy", "false");
            elements.question.focus();
        }
    }

    elements.form.addEventListener("submit", (event) => {
        event.preventDefault();
        submitQuestion(elements.question.value);
    });

    elements.question.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            elements.form.requestSubmit();
        }
    });

    document.querySelectorAll(".insights-suggestion").forEach((button) => {
        button.addEventListener("click", () => {
            submitQuestion(button.dataset.question, button.dataset.demoKey);
        });
    });

    elements.clearHistory.addEventListener("click", () => {
        sessionHistory.length = 0;
        elements.messages.innerHTML = initialMessages;
        renderHistory();
        setResultState("empty");
        elements.question.focus();
    });

    elements.copySql.addEventListener("click", async () => {
        const label = elements.copySql.querySelector("span");
        try {
            await navigator.clipboard.writeText(elements.sql.textContent);
            label.textContent = "已复制";
        } catch {
            label.textContent = "复制失败";
        }
        window.setTimeout(() => { label.textContent = "复制 SQL"; }, 1400);
    });

    renderHistory();
})();
