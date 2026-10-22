(() => {
    'use strict';
    const form = document.getElementById('characterization-upload');
    if (!form) return;
    const byId = id => document.getElementById(id);
    const dialog = byId('upload-dialog');
    const searchInput = byId('upload-search');
    const results = byId('sample-results');
    const searchStatus = byId('sample-search-status');
    const more = byId('more-samples');
    const testType = byId('upload-test-type');
    const filesInput = byId('upload-files');
    const folderInput = byId('upload-folder');
    const submit = byId('submit-upload');
    const configured = !submit.disabled;
    let selected = null;
    let cursor = null;
    let searchedQuery = '';
    let controller = null;
    let busy = false;

    const mode = () => form.querySelector('input[name="mode"]:checked').value;
    const allFiles = () => Array.from((mode() === 'folder' ? folderInput : filesInput).files);
    const pathFor = file => mode() === 'folder' ? file.webkitRelativePath : file.name;
    const selectedFiles = () => allFiles().filter(file => !pathFor(file).split('/').some(part => part.startsWith('.')));
    const sizeLabel = bytes => bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(1)} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
    function destination() {
        byId('upload-destination').textContent = selected && testType.value ? `${testType.value} / ${selected.name} /` : '请选择 Sample 和测试项目';
    }
    function showError(message) {
        byId('upload-error').textContent = message;
        byId('upload-error').hidden = false;
        byId('upload-error').focus();
    }
    function updateFiles() {
        const files = selectedFiles();
        const skipped = allFiles().length - files.length;
        byId('file-selection').textContent = files.length ? `${files.length} 个文件 · ${sizeLabel(files.reduce((sum, file) => sum + file.size, 0))}${skipped ? `（忽略 ${skipped} 个隐藏文件）` : ''}` : (skipped ? '所选内容只有隐藏文件，请选择数据文件。' : '尚未选择文件');
    }
    byId('open-upload').addEventListener('click', () => {
        dialog.showModal();
        searchInput.focus();
    });
    function close() { if (!busy) dialog.close(); }
    byId('close-upload').addEventListener('click', close);
    byId('cancel-upload').addEventListener('click', close);
    dialog.addEventListener('cancel', event => { if (busy) event.preventDefault(); });
    window.addEventListener('beforeunload', event => { if (busy) { event.preventDefault(); event.returnValue = ''; } });
    function invalidateSearch() {
        controller?.abort();
        cursor = null;
        selected = null;
        more.hidden = true;
        results.replaceChildren();
        byId('selected-sample').textContent = '尚未选择 Sample';
        searchStatus.textContent = '输入样品编号后点击搜索。';
        destination();
    }
    searchInput.addEventListener('input', invalidateSearch);
    async function search(append = false) {
        const query = searchInput.value.trim();
        if (query.length < 2) { searchStatus.textContent = '请至少输入 2 个字符。'; return; }
        controller?.abort();
        if (!append) invalidateSearch();
        const active = new AbortController();
        controller = active;
        const params = new URLSearchParams({q: query});
        if (append && cursor && query === searchedQuery) params.set('cursor', cursor);
        more.hidden = true;
        searchStatus.textContent = '正在搜索…';
        try {
            const response = await fetch(`${form.dataset.searchUrl}?${params}`, {signal: active.signal, headers: {'Accept': 'application/json'}});
            if (response.redirected) throw new Error('登录已过期，请刷新页面后重试。');
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || '搜索失败，请重试。');
            if (active.signal.aborted) return;
            searchedQuery = query;
            data.results.forEach(sample => {
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'cu-sample-option';
                button.setAttribute('aria-pressed', 'false');
                const name = document.createElement('strong');
                name.textContent = sample.name;
                const detail = document.createElement('small');
                detail.textContent = `${sample.experiment} · ${sample.step_label || sample.step} · ${sample.date}`;
                button.append(name, detail);
                button.addEventListener('click', () => {
                    selected = sample;
                    results.querySelectorAll('button').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
                    byId('selected-sample').textContent = `已选择：${sample.name}`;
                    destination();
                });
                results.append(button);
            });
            cursor = data.next_cursor;
            more.hidden = !cursor;
            searchStatus.textContent = results.children.length ? `找到 ${results.children.length} 个样品${cursor ? '，可加载更多' : ''}，请选择一个。` : '没有匹配的样品，请检查编号。';
        } catch (error) {
            if (error.name !== 'AbortError' && !active.signal.aborted) searchStatus.textContent = error.message || '搜索失败，请重试。';
        }
    }
    byId('search-samples').addEventListener('click', () => search());
    more.addEventListener('click', () => search(true));
    searchInput.addEventListener('keydown', event => { if (event.key === 'Enter') { event.preventDefault(); search(); } });
    testType.addEventListener('change', destination);
    form.querySelectorAll('input[name="mode"]').forEach(input => input.addEventListener('change', () => {
        filesInput.hidden = mode() !== 'files';
        filesInput.disabled = mode() !== 'files';
        folderInput.hidden = mode() !== 'folder';
        folderInput.disabled = mode() !== 'folder';
        updateFiles();
    }));
    filesInput.addEventListener('change', updateFiles);
    folderInput.addEventListener('change', updateFiles);

    function setBusy(value) {
        busy = value;
        byId('upload-fields').disabled = value;
        byId('close-upload').disabled = value;
        byId('cancel-upload').disabled = value;
        submit.disabled = value || !configured;
        submit.textContent = value ? '正在上传…' : '开始上传';
    }
    form.addEventListener('submit', event => {
        event.preventDefault();
        if (busy) return;
        byId('upload-error').hidden = true;
        if (!configured) { showError('请联系管理员配置数据目录。'); return; }
        if (!selected) { showError('请先搜索并选择 Sample。'); return; }
        const files = selectedFiles();
        if (!files.length) { showError('请选择文件或包含数据的文件夹。'); return; }
        if (files.length > Number(form.dataset.maxFiles)) { showError(`单次最多上传 ${form.dataset.maxFiles} 个文件，请分批上传。`); return; }
        if (files.reduce((sum, file) => sum + file.size, 0) > Number(form.dataset.maxBytes)) { showError('数据大小超过单次上传限制，请分批上传。'); return; }
        const body = new FormData();
        body.append('csrfmiddlewaretoken', form.elements.csrfmiddlewaretoken.value);
        body.append('sample_id', selected.id);
        body.append('test_type', testType.value);
        body.append('mode', mode());
        body.append('paths', JSON.stringify(files.map(pathFor)));
        files.forEach(file => body.append('files', file, file.name));
        controller?.abort();
        setBusy(true);
        byId('upload-progress-wrap').hidden = false;
        byId('upload-progress').value = 0;
        byId('upload-status').textContent = '正在上传，请保持页面打开。';
        const xhr = new XMLHttpRequest();
        xhr.open('POST', form.action);
        xhr.setRequestHeader('Accept', 'application/json');
        xhr.upload.addEventListener('progress', progress => {
            if (!progress.lengthComputable) return;
            const percent = Math.round(progress.loaded / progress.total * 100);
            byId('upload-progress').value = percent;
            byId('upload-status').textContent = percent === 100 ? '传输完成，服务器正在保存…' : `正在上传 ${percent}%`;
        });
        xhr.addEventListener('load', () => {
            setBusy(false);
            byId('upload-progress-wrap').hidden = true;
            let data;
            try { data = JSON.parse(xhr.responseText); } catch (_) { showError('服务器未返回上传结果，请检查登录状态或联系管理员确认数据是否已保存。'); return; }
            if (xhr.status !== 201) { showError(data.error || '上传失败，请重试。'); return; }
            byId('upload-result').textContent = `已上传 ${data.file_count} 个文件，保存至 ${data.destination}。`;
            byId('upload-result').hidden = false;
            filesInput.value = '';
            folderInput.value = '';
            updateFiles();
            dialog.close();
        });
        xhr.addEventListener('error', () => {
            setBusy(false);
            byId('upload-progress-wrap').hidden = true;
            showError('连接中断，无法确认保存结果。请联系管理员检查后重试；已有同名文件不会被覆盖。');
        });
        xhr.send(body);
    });
})();
