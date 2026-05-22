(function () {
    var openBtn = document.getElementById('qr-open-btn');
    var modal = document.getElementById('qr-modal');
    if (!openBtn || !modal) { return; }

    var wrap = document.getElementById('qr-canvas-wrap');
    var trackUrl = openBtn.getAttribute('data-track-url') || '';
    var qrInstance = null;

    function closeModal() {
        modal.hidden = true;
        modal.setAttribute('aria-hidden', 'true');
        document.body.classList.remove('qr-modal-open');
    }

    function openModal() {
        if (!trackUrl || typeof QRCode === 'undefined') { return; }
        wrap.innerHTML = '';
        qrInstance = new QRCode(wrap, {
            text: trackUrl,
            width: 220,
            height: 220,
            colorDark: '#172b4d',
            colorLight: '#ffffff',
            correctLevel: QRCode.CorrectLevel.M,
        });
        modal.hidden = false;
        modal.setAttribute('aria-hidden', 'false');
        document.body.classList.add('qr-modal-open');
    }

    openBtn.addEventListener('click', openModal);
    modal.querySelectorAll('[data-qr-close]').forEach(function (el) {
        el.addEventListener('click', closeModal);
    });
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && !modal.hidden) { closeModal(); }
    });
})();
