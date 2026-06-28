(function () {
    let cyInstance = null;

    function destroy() {
        if (cyInstance) {
            cyInstance.destroy();
            cyInstance = null;
        }
    }

    function parseGraphData(dataElementId) {
        const graphDataElement = document.getElementById(dataElementId || 'genealogyGraphData');
        if (!graphDataElement) {
            return null;
        }
        return JSON.parse(graphDataElement.textContent);
    }

    function init(options) {
        const config = options || {};
        const container = document.getElementById(config.containerId || 'genealogyCy');
        if (!container) {
            return null;
        }
        if (typeof cytoscape === 'undefined') {
            container.innerHTML = '<div class="alert alert-danger m-3">图谱组件加载失败。</div>';
            return null;
        }

        let graphData;
        try {
            graphData = parseGraphData(config.dataElementId);
        } catch (error) {
            console.error('Error parsing genealogy graph data:', error);
            container.innerHTML = '<div class="alert alert-danger m-3">图谱数据解析失败。</div>';
            return null;
        }
        if (!graphData) {
            return null;
        }

        destroy();

        cyInstance = cytoscape({
            container: container,
            elements: graphData.elements || [],
            wheelSensitivity: 0.22,
            minZoom: 0.25,
            maxZoom: 2.2,
            layout: { name: 'preset', fit: true, padding: 48 },
            style: [
                {
                    selector: 'node',
                    style: {
                        'shape': 'round-rectangle',
                        'width': 190,
                        'height': 86,
                        'background-color': '#ffffff',
                        'border-width': 1,
                        'border-color': '#d8dee4',
                        'label': 'data(label)',
                        'font-family': '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", Arial, sans-serif',
                        'font-size': 12,
                        'font-weight': 700,
                        'color': '#1f2933',
                        'text-wrap': 'wrap',
                        'text-max-width': 160,
                        'text-valign': 'center',
                        'text-halign': 'center',
                        'overlay-opacity': 0,
                        'shadow-blur': 8,
                        'shadow-color': '#1f2933',
                        'shadow-opacity': 0.08,
                        'shadow-offset-x': 0,
                        'shadow-offset-y': 2
                    }
                },
                {
                    selector: 'node.step-node',
                    style: {
                        'cursor': 'pointer'
                    }
                },
                {
                    selector: 'node.current-step',
                    style: {
                        'background-color': '#e9f7f4',
                        'border-color': '#1f9d8a',
                        'border-width': 2
                    }
                },
                {
                    selector: 'node.material-node',
                    style: {
                        'width': 150,
                        'height': 54,
                        'background-color': '#fff9ed',
                        'border-color': '#f4d7a1',
                        'color': '#7a4a12',
                        'font-size': 10,
                        'font-weight': 700,
                        'text-max-width': 128
                    }
                },
                {
                    selector: 'edge',
                    style: {
                        'curve-style': 'taxi',
                        'taxi-direction': 'rightward',
                        'taxi-turn': 42,
                        'line-color': '#b8c2cc',
                        'target-arrow-color': '#b8c2cc',
                        'target-arrow-shape': 'triangle',
                        'arrow-scale': 0.9,
                        'width': 2
                    }
                },
                {
                    selector: 'edge.material-edge',
                    style: {
                        'line-color': '#e1bc75',
                        'target-arrow-color': '#e1bc75',
                        'line-style': 'dashed',
                        'width': 1.5
                    }
                },
                {
                    selector: 'node:selected',
                    style: {
                        'border-color': '#2f66d0',
                        'border-width': 2
                    }
                }
            ]
        });

        cyInstance.on('tap', 'node.step-node', function (evt) {
            const url = evt.target.data('url');
            if (!url) {
                return;
            }
            if (typeof config.onStepTap === 'function') {
                config.onStepTap(url);
            } else {
                window.location.href = url;
            }
        });

        const fitBtn = document.getElementById(config.fitButtonId || 'genealogyFitBtn');
        if (fitBtn) {
            fitBtn.addEventListener('click', function () {
                fit();
            });
        }

        requestAnimationFrame(function () {
            focusCurrent();
            window.setTimeout(focusCurrent, 250);
        });

        return cyInstance;
    }

    function focusCurrent() {
        if (!cyInstance) {
            return;
        }
        cyInstance.resize();
        const currentNode = cyInstance.nodes().filter(function (node) {
            return Boolean(node.data('is_current'));
        }).first();
        if (currentNode && currentNode.length) {
            cyInstance.zoom({
                level: 0.78,
                position: currentNode.position()
            });
            cyInstance.center(currentNode);
        } else {
            fit();
        }
    }

    function fit() {
        if (cyInstance) {
            cyInstance.resize();
            cyInstance.fit(undefined, 48);
            cyInstance.center();
        }
    }

    window.AtlasGenealogyGraph = {
        destroy: destroy,
        fit: fit,
        focusCurrent: focusCurrent,
        init: init,
        instance: function () {
            return cyInstance;
        }
    };

    document.addEventListener('DOMContentLoaded', function () {
        if (document.getElementById('genealogyCy') && document.getElementById('genealogyGraphData')) {
            init();
        }
    });
})();
