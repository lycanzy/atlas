(function () {
    'use strict';

    function initExperimentDescriptionSourcePicker(options) {
        const searchInput = document.getElementById(options.searchInputId);
        const resultList = document.getElementById(options.resultListId);
        const status = document.getElementById(options.statusId);
        const loadMore = document.getElementById(options.loadMoreId);
        const selectedCard = document.getElementById(options.selectedCardId);
        const selectedCode = document.getElementById(options.selectedCodeId);
        const selectedMeta = document.getElementById(options.selectedMetaId);
        const selectedPreview = document.getElementById(options.selectedPreviewId);
        const copyButton = document.getElementById(options.copyButtonId);
        const descriptionInput = document.getElementById(options.descriptionInputId);
        const sourceIdInput = document.getElementById(options.sourceIdInputId);
        if (!searchInput || !resultList || !status || !loadMore || !selectedCard ||
            !selectedCode || !selectedMeta || !selectedPreview || !copyButton ||
            !descriptionInput || !sourceIdInput) return null;

        let currentQuery = '';
        let currentPage = 1;
        let selectedSource = null;
        let debounceTimer = null;
        let searchController = null;
        let detailController = null;

        function setStatus(message, isError) {
            status.textContent = message;
            status.classList.toggle('text-danger', Boolean(isError));
            status.classList.toggle('text-muted', !isError);
        }

        function clearResults() {
            resultList.replaceChildren();
            resultList.classList.add('d-none');
            loadMore.classList.add('d-none');
        }

        function createResult(source) {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'copy-source-option';
            button.setAttribute('role', 'option');

            const heading = document.createElement('span');
            heading.className = 'd-flex align-items-center gap-2';
            const code = document.createElement('span');
            code.className = 'fw-semibold font-monospace';
            code.textContent = source.code;
            heading.appendChild(code);
            if (source.is_current_project) {
                const badge = document.createElement('span');
                badge.className = 'badge rounded-pill text-bg-primary-subtle text-primary-emphasis';
                badge.textContent = '当前项目';
                heading.appendChild(badge);
            }

            const preview = document.createElement('span');
            preview.className = 'copy-source-description';
            preview.textContent = source.preview;
            const stepCount = document.createElement('span');
            stepCount.className = 'copy-source-meta';
            stepCount.textContent = `${source.step_count} 个步骤`;
            button.append(heading, stepCount, preview);
            button.addEventListener('click', function () {
                selectSource(source);
            });
            return button;
        }

        async function search(page, append) {
            const query = searchInput.value.trim();
            if (query.length < 2) {
                currentQuery = '';
                currentPage = 1;
                clearResults();
                setStatus('输入至少 2 个字符，搜索实验编号、项目编号或描述。');
                return;
            }

            if (searchController) searchController.abort();
            searchController = new AbortController();
            setStatus(page > 1 ? '正在加载更多结果…' : '正在搜索…');
            loadMore.disabled = true;
            try {
                const url = new URL(options.searchUrl, window.location.origin);
                url.searchParams.set('q', query);
                url.searchParams.set('page', page);
                const response = await fetch(url, {
                    headers: {'X-Requested-With': 'XMLHttpRequest'},
                    signal: searchController.signal
                });
                const data = await response.json();
                if (!response.ok) throw new Error(data.error || '搜索失败，请重试。');
                if (query !== searchInput.value.trim()) return;

                if (!append) resultList.replaceChildren();
                data.results.forEach(source => resultList.appendChild(createResult(source)));
                currentQuery = query;
                currentPage = page;
                const totalShown = resultList.children.length;
                resultList.classList.toggle('d-none', totalShown === 0);
                loadMore.classList.toggle('d-none', !data.pagination.more);
                loadMore.disabled = false;
                setStatus(totalShown ? `已显示 ${totalShown} 个匹配实验` : '未找到匹配的实验。');
            } catch (error) {
                if (error.name === 'AbortError') return;
                clearResults();
                setStatus(error.message || '搜索失败，请重试。', true);
            }
        }

        async function selectSource(source) {
            if (detailController) detailController.abort();
            detailController = new AbortController();
            setStatus(`正在读取 ${source.code} 的描述…`);
            try {
                const detailUrl = options.detailUrlTemplate.replace('__SOURCE_ID__', source.id);
                const response = await fetch(detailUrl, {
                    headers: {'X-Requested-With': 'XMLHttpRequest'},
                    signal: detailController.signal
                });
                const data = await response.json();
                if (!response.ok) throw new Error(data.error || '无法读取该实验描述。');
                selectedSource = data;
                selectedCode.textContent = data.code;
                selectedMeta.textContent = `${data.step_count} 个步骤 · 包含谱系`;
                selectedPreview.textContent = data.description;
                selectedCard.classList.remove('d-none');
                resultList.classList.add('d-none');
                loadMore.classList.add('d-none');
                updateCopyButton();
                setStatus('已选择来源。确认后再复制到描述框。');
                copyButton.focus();
            } catch (error) {
                if (error.name === 'AbortError') return;
                setStatus(error.message || '无法读取该实验描述。', true);
            }
        }

        function updateCopyButton() {
            if (!selectedSource) return;
            const willReplace = descriptionInput.value.trim() &&
                descriptionInput.value.trim() !== selectedSource.description.trim();
            copyButton.textContent = willReplace ? '替换描述并选择' : '选择并复制';
            copyButton.classList.toggle('btn-warning', Boolean(willReplace));
            copyButton.classList.toggle('btn-primary', !willReplace);
        }

        searchInput.addEventListener('input', function () {
            window.clearTimeout(debounceTimer);
            if (searchInput.value.trim().length < 2) {
                search(1, false);
                return;
            }
            setStatus('准备搜索…');
            debounceTimer = window.setTimeout(() => search(1, false), 250);
        });
        searchInput.addEventListener('keydown', function (event) {
            if (event.key === 'Enter') {
                event.preventDefault();
                window.clearTimeout(debounceTimer);
                search(1, false);
            } else if (event.key === 'Escape' && options.closePanel) {
                options.closePanel();
            }
        });
        loadMore.addEventListener('click', function () {
            if (currentQuery === searchInput.value.trim()) search(currentPage + 1, true);
        });
        descriptionInput.addEventListener('input', updateCopyButton);
        copyButton.addEventListener('click', function () {
            if (!selectedSource) return;
            descriptionInput.value = selectedSource.description;
            sourceIdInput.value = selectedSource.id;
            updateCopyButton();
            if (options.onCopied) options.onCopied(selectedSource);
            descriptionInput.dispatchEvent(new Event('input', {bubbles: true}));
            descriptionInput.focus();
        });

        setStatus('输入至少 2 个字符，搜索实验编号、项目编号或描述。');
        return {
            reset: function () {
                window.clearTimeout(debounceTimer);
                if (searchController) searchController.abort();
                if (detailController) detailController.abort();
                searchInput.value = '';
                selectedSource = null;
                sourceIdInput.value = '';
                selectedCard.classList.add('d-none');
                clearResults();
                setStatus('输入至少 2 个字符，搜索实验编号、项目编号或描述。');
            }
        };
    }

    window.initExperimentDescriptionSourcePicker = initExperimentDescriptionSourcePicker;
})();
