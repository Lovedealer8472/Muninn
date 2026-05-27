(function () {
    var board = document.querySelector('.board');
    if (!board || typeof Sortable === 'undefined') { return; }

    var cfgEl = document.getElementById('board-dnd-config');
    if (!cfgEl) { return; }
    var config;
    try {
        config = JSON.parse(cfgEl.textContent);
    } catch (e) {
        return;
    }

    var statuses = config.statuses || [];
    var isStjori = !!config.isStjori;
    var toastTimer = null;

    function allowedTargetStatus(fromStatus) {
        if (isStjori) {
            return statuses.filter(function (s) { return s !== fromStatus; });
        }
        var idx = statuses.indexOf(fromStatus);
        if (idx < 0 || idx >= statuses.length - 1) { return []; }
        return [statuses[idx + 1]];
    }

    function updateColumnCounts() {
        board.querySelectorAll('.column').forEach(function (col) {
            var cards = col.querySelector('.column-cards');
            var countEl = col.querySelector('.column-header .count');
            if (countEl && cards) {
                countEl.textContent = String(cards.querySelectorAll('.card').length);
            }
        });
    }

    function showToast(message, kind) {
        var existing = document.getElementById('board-dnd-toast');
        if (existing) { existing.remove(); }
        clearTimeout(toastTimer);

        var toast = document.createElement('div');
        toast.id = 'board-dnd-toast';
        toast.className = 'board-dnd-toast board-dnd-toast--' + (kind || 'info');
        toast.setAttribute('role', 'status');
        toast.textContent = message;
        document.body.appendChild(toast);

        toastTimer = setTimeout(function () {
            toast.classList.add('board-dnd-toast--hide');
            setTimeout(function () { toast.remove(); }, 300);
        }, 4500);
    }

    function emailToastMessage(result) {
        if (!result || result === 'skipped') { return null; }
        if (result === 'pending') { return 'Póstur sendist við Komið…'; }
        if (result === 'sent') { return 'Tilkynning send í tölvupósti.'; }
        if (result === 'failed') { return 'Póstur mistókst.'; }
        if (result === 'no_email') { return 'Komið — enginn netfang skráður.'; }
        if (result === 'no_smtp') { return 'Póstur ekki sendur (SMTP).'; }
        return null;
    }

    function postStatusChange(orderId, newStatus) {
        var body = new URLSearchParams({ status: newStatus });
        return fetch('/order/' + encodeURIComponent(orderId) + '/status', {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-Muninn-Board': '1'
            },
            body: body.toString()
        }).then(function (r) {
            return r.json().catch(function () { return {}; }).then(function (data) {
                return { ok: r.ok, status: r.status, data: data };
            });
        });
    }

    function revertMove(evt) {
        var card = evt.item;
        var from = evt.from;
        var children = from.children;
        if (evt.oldIndex >= children.length) {
            from.appendChild(card);
        } else {
            from.insertBefore(card, children[evt.oldIndex]);
        }
        updateColumnCounts();
    }

    board.querySelectorAll('.card').forEach(function (card) {
        card.addEventListener('click', function (e) {
            if (e.target.closest('.card-drag-handle')) { return; }
            var url = card.getAttribute('data-detail-url');
            if (url) { window.location = url; }
        });
    });

    board.querySelectorAll('.column-cards').forEach(function (col) {
        Sortable.create(col, {
            group: 'muninn-board',
            animation: 160,
            handle: '.card-drag-handle',
            draggable: '.card',
            ghostClass: 'card--dragging',
            dragClass: 'card--dragging',
            fallbackOnBody: true,
            swapThreshold: 0.65,
            onMove: function (evt) {
                var fromStatus = evt.from.getAttribute('data-drop-status');
                var toStatus = evt.to.getAttribute('data-drop-status');
                if (fromStatus === toStatus) { return false; }
                var allowed = allowedTargetStatus(fromStatus);
                return allowed.indexOf(toStatus) >= 0;
            },
            onEnd: function (evt) {
                col.classList.remove('column-cards--drag-over');
                if (evt.from === evt.to && evt.oldIndex === evt.newIndex) { return; }

                var card = evt.item;
                var toStatus = evt.to.getAttribute('data-drop-status');
                var fromStatus = card.getAttribute('data-status');
                if (!toStatus || toStatus === fromStatus) {
                    revertMove(evt);
                    return;
                }

                var orderId = card.getAttribute('data-order-id');
                card.setAttribute('data-status', toStatus);
                updateColumnCounts();

                postStatusChange(orderId, toStatus).then(function (res) {
                    if (!res.ok || !res.data.ok) {
                        card.setAttribute('data-status', fromStatus);
                        revertMove(evt);
                        showToast(
                            (res.data && res.data.error) || 'Ekki tókst að uppfæra stöðu.',
                            'error'
                        );
                        return;
                    }
                var msg = emailToastMessage(res.data.email);
                if (msg) {
                    showToast(msg, res.data.email === 'failed' ? 'error' : 'success');
                } else if (res.data.archive_eligible) {
                    showToast('Lokið og greitt — opna pöntun til að geyma.', 'info');
                }
                }).catch(function () {
                    card.setAttribute('data-status', fromStatus);
                    revertMove(evt);
                    showToast('Netvilla — reyndu aftur.', 'error');
                });
            }
        });

        col.addEventListener('mouseenter', function () {
            if (document.querySelector('.card--dragging')) {
                col.classList.add('column-cards--drag-over');
            }
        });
        col.addEventListener('mouseleave', function () {
            col.classList.remove('column-cards--drag-over');
        });
    });
})();
