(() => {
    'use strict';
    if (document.querySelector('.iv-detail')) {
        document.addEventListener('keydown', (event) => {
            if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey ||
                event.target.closest('input, textarea, select, [contenteditable="true"]')) return;
            const target = event.key === 'ArrowLeft' ? 'previous-image' :
                event.key === 'ArrowRight' ? 'next-image' : null;
            const link = target && document.getElementById(target);
            if (link) {
                event.preventDefault();
                window.location.assign(link.href);
            }
        });
    }
    document.querySelectorAll('.iv-thumbnail img, .iv-full-image').forEach((img) => {
        const showError = () => {
            if (img.parentElement.querySelector('.iv-image-error')) return;
            const message = document.createElement('span');
            message.className = 'iv-image-error';
            message.setAttribute('role', 'status');
            message.textContent = '图片加载失败，请刷新重试';
            img.hidden = true;
            img.parentElement.append(message);
        };
        img.addEventListener('error', showError);
        if (img.complete && !img.naturalWidth) showError();
    });
})();
