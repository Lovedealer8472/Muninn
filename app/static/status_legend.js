(function () {
    var openBtn = document.getElementById('status-legend-open-btn');
    var modal = document.getElementById('status-legend-modal');
    if (!openBtn || !modal) { return; }

    function closeModal() {
        modal.hidden = true;
        modal.setAttribute('aria-hidden', 'true');
        document.body.classList.remove('qr-modal-open');
    }

    function openModal() {
        modal.hidden = false;
        modal.setAttribute('aria-hidden', 'false');
        document.body.classList.add('qr-modal-open');
    }

    openBtn.addEventListener('click', openModal);
    modal.querySelectorAll('[data-status-legend-close]').forEach(function (el) {
        el.addEventListener('click', closeModal);
    });
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && !modal.hidden) { closeModal(); }
    });
})();
