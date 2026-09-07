/* Progressive enhancement: links still render a complete homepage without JS. */
(() => {
    let pending;
    async function loadBoard(href, focusKey, showDetails = false) {
        const board = document.querySelector('[data-activity-board]');
        if (!board) return;
        if (pending) pending.abort();
        const controller = new AbortController();
        pending = controller;
        board.setAttribute('aria-busy', 'true');
        const url = new URL(href, window.location.href);
        url.searchParams.set('activity_fragment', '1');
        try {
            const response = await fetch(url, {signal: controller.signal, headers: {'X-Requested-With': 'XMLHttpRequest'}});
            if (!response.ok || response.redirected) throw new Error('Activity unavailable');
            const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
            const replacement = doc.querySelector('[data-activity-board]');
            if (!replacement || controller.signal.aborted) throw new Error('Invalid response');
            board.replaceWith(replacement);
            url.searchParams.delete('activity_fragment');
            history.replaceState(null, '', url);
            if (showDetails) replacement.querySelector('details').open = true;
            const target = Array.from(replacement.querySelectorAll('[data-focus]')).find(item => item.dataset.focus === focusKey);
            if (target) target.focus({preventScroll: true});
            replacement.querySelector('[role="status"]').textContent = '实验活动已更新';
        } catch (error) {
            if (error.name === 'AbortError' || controller.signal.aborted) return;
            const feedback = board.querySelector('[role="status"]');
            feedback.classList.remove('visually-hidden');
            feedback.textContent = '活动加载失败，请重试或刷新页面。';
        } finally {
            if (pending === controller) {
                pending = null;
                board.removeAttribute('aria-busy');
            }
        }
    }
    document.addEventListener('click', event => {
        const link = event.target.closest('[data-activity-link]');
        if (!link || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        loadBoard(link.href, link.dataset.focus, Boolean(link.dataset.date) || ['previous', 'next'].includes(link.dataset.focus));
    });
    document.addEventListener('change', event => {
        if (event.target.matches('[data-activity-year]')) loadBoard(event.target.value, 'year');
    });
    document.addEventListener('keydown', event => {
        const day = event.target.closest('[data-date]');
        const offset = {ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7}[event.key];
        if (!day || offset === undefined) return;
        event.preventDefault();
        const days = Array.from(day.closest('[data-activity-board]').querySelectorAll('[data-date]'));
        const target = days[days.indexOf(day) + offset];
        if (target) target.focus();
    });
})();
