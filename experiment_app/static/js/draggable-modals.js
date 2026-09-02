(function () {
    'use strict';

    const dragMediaQuery = window.matchMedia('(hover: hover) and (pointer: fine)');
    const viewportMargin = 8;
    const minimumVisibleWidth = 80;

    function initializeDraggableModal(modal) {
        const dialog = modal.querySelector('.modal-dialog');
        const content = modal.querySelector('.modal-content');
        const handle = modal.querySelector('[data-modal-drag-handle]');

        if (!dialog || !content || !handle) return;

        let offsetX = 0;
        let offsetY = 0;
        let activePointerId = null;
        let pointerStartX = 0;
        let pointerStartY = 0;
        let dragStartX = 0;
        let dragStartY = 0;

        function applyOffset(x, y) {
            offsetX = x;
            offsetY = y;
            dialog.style.transform = `translate(${x}px, ${y}px)`;
        }

        function getConstrainedOffset(proposedX, proposedY) {
            const contentRect = content.getBoundingClientRect();
            const handleRect = handle.getBoundingClientRect();
            const baseLeft = contentRect.left - offsetX;
            const baseRight = contentRect.right - offsetX;
            const viewportWidth = document.documentElement.clientWidth;
            const viewportHeight = document.documentElement.clientHeight;

            let minX;
            let maxX;
            if (contentRect.width <= viewportWidth - (viewportMargin * 2)) {
                minX = viewportMargin - baseLeft;
                maxX = viewportWidth - viewportMargin - baseRight;
            } else {
                minX = minimumVisibleWidth - baseRight;
                maxX = viewportWidth - minimumVisibleWidth - baseLeft;
            }

            // Keep the complete drag handle reachable, while allowing the body
            // of short and tall dialogs alike to move beyond the viewport.
            const baseHandleTop = handleRect.top - offsetY;
            const baseHandleBottom = handleRect.bottom - offsetY;
            const minY = viewportMargin - baseHandleTop;
            const maxY = viewportHeight - viewportMargin - baseHandleBottom;

            return {
                x: Math.min(Math.max(proposedX, minX), maxX),
                y: Math.min(Math.max(proposedY, minY), maxY),
            };
        }

        function stopDragging() {
            if (activePointerId === null) return;

            if (handle.hasPointerCapture(activePointerId)) {
                handle.releasePointerCapture(activePointerId);
            }
            activePointerId = null;
            modal.classList.remove('is-modal-dragging');
        }

        handle.addEventListener('pointerdown', function (event) {
            if (!dragMediaQuery.matches || event.pointerType === 'touch') return;
            if (event.button !== 0) return;
            if (event.target.closest('button, a, input, select, textarea, [role="button"]')) return;

            activePointerId = event.pointerId;
            pointerStartX = event.clientX;
            pointerStartY = event.clientY;
            dragStartX = offsetX;
            dragStartY = offsetY;
            handle.setPointerCapture(activePointerId);
            modal.classList.add('is-modal-dragging');
            event.preventDefault();
        });

        handle.addEventListener('pointermove', function (event) {
            if (event.pointerId !== activePointerId) return;

            const constrained = getConstrainedOffset(
                dragStartX + event.clientX - pointerStartX,
                dragStartY + event.clientY - pointerStartY
            );
            applyOffset(constrained.x, constrained.y);
        });

        handle.addEventListener('pointerup', stopDragging);
        handle.addEventListener('pointercancel', stopDragging);

        modal.addEventListener('hidden.bs.modal', function () {
            stopDragging();
            offsetX = 0;
            offsetY = 0;
            dialog.style.removeProperty('transform');
        });

        window.addEventListener('resize', function () {
            if (!modal.classList.contains('show') || (offsetX === 0 && offsetY === 0)) return;

            const constrained = getConstrainedOffset(offsetX, offsetY);
            applyOffset(constrained.x, constrained.y);
        });
    }

    document.querySelectorAll('[data-draggable-modal]').forEach(initializeDraggableModal);
}());
