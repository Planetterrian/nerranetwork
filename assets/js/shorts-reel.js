/**
 * Nerra Network — the homepage Shorts reel (Oct 18 2026).
 *
 * Three jobs, no dependencies, nothing fetched on page load:
 *
 * 1. The rail: prev/next arrows scroll it by a page of cards, the edge fades
 *    turn off at either end, and the arrows hide when nothing overflows.
 * 2. Preview loops: a card whose Short has a muted preview (preview_url,
 *    engine/short_preview.py) plays it only while the card is on screen,
 *    never under prefers-reduced-motion or Save-Data, and never while the
 *    player is open. preload="none" means nothing loads before that.
 * 3. The player: Play opens a <dialog> and only THEN creates the
 *    youtube-nocookie.com embed (facade pattern — no YouTube frame, script
 *    or cookie before a click). Prev/next buttons, the arrow keys and a
 *    swipe move through the reel like a Shorts feed; Esc or the close button
 *    removes the frame (the video stops) and returns focus to the card of
 *    the Short last shown.
 *
 * Data: the JSON blob #lt-reel-data the template renders from the same rows
 * as the cards (index-aligned with each card's data-reel-play).
 */
(function () {
    'use strict';

    var reel = document.querySelector('[data-reel]');
    var track = document.querySelector('[data-reel-track]');
    if (!reel || !track) return;

    var items = [];
    try {
        items = JSON.parse((document.getElementById('lt-reel-data') || {}).textContent || '[]');
    } catch (e) { items = []; }

    var reduceMotion = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;
    var saveData = !!(navigator.connection && navigator.connection.saveData);
    function motionAllowed() { return !(reduceMotion && reduceMotion.matches) && !saveData; }

    function track_event(name, params) {
        try { if (typeof window.gtag === 'function') window.gtag('event', name, params || {}); } catch (e) { /* never block */ }
    }

    // ---- 1. The rail --------------------------------------------------
    var nav = document.querySelector('[data-reel-nav]');
    var prevBtn = document.querySelector('[data-reel-prev]');
    var nextBtn = document.querySelector('[data-reel-next]');

    function updateEdges() {
        var max = track.scrollWidth - track.clientWidth;
        var x = Math.abs(track.scrollLeft);
        var overflow = max > 4;
        reel.toggleAttribute('data-at-start', !overflow || x <= 4);
        reel.toggleAttribute('data-at-end', !overflow || x >= max - 4);
        if (nav) nav.hidden = !overflow;
        if (prevBtn) prevBtn.disabled = !overflow || x <= 4;
        if (nextBtn) nextBtn.disabled = !overflow || x >= max - 4;
    }

    function page(dir) {
        var card = track.querySelector('[data-reel-item]');
        var step = card ? card.getBoundingClientRect().width + 16 : 200;
        var n = Math.max(1, Math.floor(track.clientWidth / step) - 1);
        track.scrollBy({ left: dir * n * step, behavior: motionAllowed() ? 'smooth' : 'auto' });
    }

    if (prevBtn) prevBtn.addEventListener('click', function () { page(-1); });
    if (nextBtn) nextBtn.addEventListener('click', function () { page(1); });
    track.addEventListener('scroll', function () { window.requestAnimationFrame(updateEdges); }, { passive: true });
    window.addEventListener('resize', updateEdges);
    updateEdges();

    // ---- 2. Preview loops ---------------------------------------------
    var previews = Array.prototype.slice.call(track.querySelectorAll('video[data-reel-preview]'));
    var playerOpen = false;
    var visible = typeof Set === 'function' ? new Set() : null;

    function stopPreview(v) {
        try { v.pause(); } catch (e) { /* ignore */ }
        v.classList.remove('is-playing');
        var card = v.closest('[data-reel-item]');
        if (card) card.classList.remove('is-previewing');
    }

    function startPreview(v) {
        if (!motionAllowed() || playerOpen || document.hidden) return;
        v.muted = true;
        var p = v.play();
        if (p && typeof p.catch === 'function') p.catch(function () { stopPreview(v); });
    }

    previews.forEach(function (v) {
        v.muted = true;
        v.addEventListener('playing', function () {
            v.classList.add('is-playing');
            var card = v.closest('[data-reel-item]');
            if (card) card.classList.add('is-previewing');
        });
        v.addEventListener('error', function () { stopPreview(v); });
    });

    function syncPreviews() {
        previews.forEach(function (v) {
            if (visible && visible.has(v) && motionAllowed() && !playerOpen && !document.hidden) startPreview(v);
            else stopPreview(v);
        });
    }

    if (previews.length && 'IntersectionObserver' in window && visible) {
        var io = new IntersectionObserver(function (entries) {
            entries.forEach(function (en) {
                if (en.isIntersecting && en.intersectionRatio >= 0.6) visible.add(en.target);
                else visible.delete(en.target);
            });
            syncPreviews();
        }, { threshold: [0, 0.6, 1] });
        previews.forEach(function (v) { io.observe(v); });
        document.addEventListener('visibilitychange', syncPreviews);
        if (reduceMotion) {
            var onChange = function () { syncPreviews(); };
            if (reduceMotion.addEventListener) reduceMotion.addEventListener('change', onChange);
            else if (reduceMotion.addListener) reduceMotion.addListener(onChange);
        }
    }

    // Show-page clicks are the reel's discovery outcome; measure them.
    track.addEventListener('click', function (ev) {
        var link = ev.target.closest && ev.target.closest('.lt-reel-show');
        if (!link) return;
        track_event('select_short_show', { placement: 'reel', link_url: link.getAttribute('href') || '' });
    });

    // ---- 3. The player ------------------------------------------------
    var dialog = document.querySelector('[data-player]');
    if (!dialog || !items.length) return;
    var frame = dialog.querySelector('[data-player-frame]');
    var elShow = dialog.querySelector('[data-player-show]');
    var elCount = dialog.querySelector('[data-player-count]');
    var elTitle = dialog.querySelector('[data-player-title]');
    var elShowLink = dialog.querySelector('[data-player-show-link]');
    var elPost = dialog.querySelector('[data-player-post]');
    var elWatch = dialog.querySelector('[data-player-watch]');
    var elPrev = dialog.querySelector('[data-player-prev]');
    var elNext = dialog.querySelector('[data-player-next]');
    var elClose = dialog.querySelector('[data-player-close]');

    // Only rows with an embed are in the feed; the others link out.
    var playable = [];
    items.forEach(function (it, i) { if (it && it.embed && it.id) playable.push(i); });
    var current = -1;

    function cardButton(i) { return track.querySelector('[data-reel-play="' + i + '"]'); }

    function render(i) {
        var it = items[i];
        if (!it) return;
        current = i;
        dialog.style.setProperty('--show-color', it.color || '#6B47FF');
        elShow.textContent = it.show || '';
        var pos = playable.indexOf(i);
        elCount.textContent = (pos + 1) + ' of ' + playable.length;
        elTitle.textContent = it.title || '';
        elShowLink.textContent = 'Listen to ' + (it.show || 'the show');
        elShowLink.setAttribute('href', it.show_page || '#');
        if (it.post) { elPost.hidden = false; elPost.setAttribute('href', it.post); }
        else { elPost.hidden = true; elPost.removeAttribute('href'); }
        elWatch.setAttribute('href', it.watch || ('https://www.youtube.com/watch?v=' + it.id));
        elPrev.disabled = pos <= 0;
        elNext.disabled = pos >= playable.length - 1;

        // The facade: the frame exists only while the player is open.
        frame.textContent = '';
        // The episode's own scene sits under the frame while YouTube loads,
        // and behind the "can't play here" panel.
        var poster = /^https:\/\//.test(it.poster || '') ? 'url("' + it.poster.replace(/["\\]/g, '') + '")' : '';
        frame.style.backgroundImage = poster;
        if (fallback) {
            fallback.hidden = true;
            fallback.style.setProperty('--player-poster', poster || 'none');
        }
        if (fallbackWatch) fallbackWatch.setAttribute('href', elWatch.getAttribute('href'));
        if (fallbackNext) fallbackNext.hidden = pos >= playable.length - 1;
        var iframe = document.createElement('iframe');
        var src = it.embed;
        if (/^https?:$/.test(location.protocol)) src += '&origin=' + encodeURIComponent(location.origin);
        iframe.src = src;
        iframe.title = (it.title || 'Short') + ' — ' + (it.show || 'Nerra Network') + ' (YouTube Short)';
        iframe.setAttribute('allow', 'autoplay; encrypted-media; picture-in-picture; fullscreen');
        iframe.setAttribute('referrerpolicy', 'strict-origin-when-cross-origin');
        // Ask the frame for its events (the embed's own postMessage channel,
        // no YouTube script here) so a video that cannot play embedded gets
        // a "Watch on YouTube" panel instead of YouTube's error card.
        iframe.addEventListener('load', function () {
            try {
                iframe.contentWindow.postMessage(JSON.stringify({ event: 'listening', id: it.id, channel: 'widget' }), YT_ORIGIN);
            } catch (e) { /* ignore */ }
        });
        frame.appendChild(iframe);
        track_event('play_short', { show_name: it.show || '', video_id: it.id || '' });
    }

    var YT_ORIGIN = 'https://www.youtube-nocookie.com';
    var fallback = dialog.querySelector('[data-player-fallback]');
    var fallbackWatch = dialog.querySelector('[data-player-fallback-watch]');
    var fallbackNext = dialog.querySelector('[data-player-fallback-next]');
    if (fallbackNext) fallbackNext.addEventListener('click', function () { step(1); if (!elNext.disabled) elNext.focus(); });
    window.addEventListener('message', function (ev) {
        if (ev.origin !== YT_ORIGIN || !playerOpen || !fallback) return;
        var frameEl = frame.querySelector('iframe');
        if (!frameEl || ev.source !== frameEl.contentWindow) return;
        var data = ev.data;
        if (typeof data === 'string') { try { data = JSON.parse(data); } catch (e) { return; } }
        if (!data || !fallback.hidden) return;
        // Two shapes carry a refusal: the onError event (100/101/150), and an
        // infoDelivery whose videoData names an errorCode (e.g. "auth") —
        // YouTube's "Video unavailable" card arrives as the second.
        var vd = data.info && data.info.videoData;
        var code = data.event === 'onError' ? data.info
            : (data.event === 'infoDelivery' && vd && vd.errorCode) ? vd.errorCode : null;
        if (code !== null && code !== undefined && code !== '') {
            fallback.hidden = false;
            track_event('play_short_unavailable', { video_id: (items[current] || {}).id || '', code: String(code) });
        }
    });

    function step(dir) {
        var pos = playable.indexOf(current) + dir;
        if (pos < 0 || pos >= playable.length) return;
        render(playable[pos]);
        // A step button that just became disabled cannot keep focus.
        if (document.activeElement && document.activeElement.disabled) {
            (dir > 0 ? elPrev : elNext).focus();
        }
    }

    function focusables() {
        return Array.prototype.filter.call(
            dialog.querySelectorAll('a[href], button:not([disabled]), iframe, [tabindex]:not([tabindex="-1"])'),
            function (el) { return !el.hidden && el.offsetParent !== null; });
    }

    function open(i) {
        if (playable.indexOf(i) < 0) return;
        playerOpen = true;
        syncPreviews();
        render(i);
        document.body.classList.add('lt-player-open');
        if (typeof dialog.showModal === 'function') {
            if (!dialog.open) dialog.showModal();
        } else {
            dialog.setAttribute('open', '');
        }
        (elClose || dialog).focus();
    }

    function close() {
        if (typeof dialog.close === 'function' && dialog.open) dialog.close();
        else dialog.removeAttribute('open');
    }

    dialog.addEventListener('close', function () {
        frame.textContent = '';  // removes the embed: playback stops, nothing lingers
        playerOpen = false;
        document.body.classList.remove('lt-player-open');
        var back = cardButton(current);
        if (back) {
            var card = back.closest('[data-reel-item]');
            if (card && card.scrollIntoView) card.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'auto' });
            back.focus({ preventScroll: true });
        }
        syncPreviews();
    });
    dialog.addEventListener('cancel', function (ev) { ev.preventDefault(); close(); });

    // A click on the backdrop (the dialog box itself, outside the shell) closes.
    dialog.addEventListener('click', function (ev) { if (ev.target === dialog) close(); });

    track.addEventListener('click', function (ev) {
        var btn = ev.target.closest && ev.target.closest('[data-reel-play]');
        if (!btn) return;
        // The card is a real link to the Short (it works with no script);
        // a modified click still opens YouTube in a new tab.
        if (ev.defaultPrevented || ev.button > 0 || ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey) return;
        ev.preventDefault();
        open(parseInt(btn.getAttribute('data-reel-play'), 10));
    });
    elPrev.addEventListener('click', function () { step(-1); });
    elNext.addEventListener('click', function () { step(1); });
    elClose.addEventListener('click', close);
    elShowLink.addEventListener('click', function () {
        track_event('select_short_show', { placement: 'player', link_url: elShowLink.getAttribute('href') || '' });
    });

    dialog.addEventListener('keydown', function (ev) {
        if (ev.key === 'Escape') { ev.preventDefault(); close(); return; }
        if (ev.key === 'ArrowRight' || ev.key === 'ArrowDown') { ev.preventDefault(); step(1); return; }
        if (ev.key === 'ArrowLeft' || ev.key === 'ArrowUp') { ev.preventDefault(); step(-1); return; }
        if (ev.key === 'Tab') {
            // Keep focus inside the player (showModal makes the page inert;
            // this also covers a browser without <dialog>).
            var f = focusables();
            if (!f.length) return;
            var first = f[0], last = f[f.length - 1];
            if (ev.shiftKey && document.activeElement === first) { ev.preventDefault(); last.focus(); }
            else if (!ev.shiftKey && document.activeElement === last) { ev.preventDefault(); first.focus(); }
        }
    });

    // Swipe (touch, outside the video frame, which keeps its own gestures):
    // left or up = next, right or down = previous.
    var touch = null;
    dialog.addEventListener('touchstart', function (ev) {
        if (ev.touches.length !== 1) { touch = null; return; }
        touch = { x: ev.touches[0].clientX, y: ev.touches[0].clientY, t: Date.now() };
    }, { passive: true });
    dialog.addEventListener('touchend', function (ev) {
        if (!touch || !ev.changedTouches.length) return;
        var dx = ev.changedTouches[0].clientX - touch.x;
        var dy = ev.changedTouches[0].clientY - touch.y;
        var quick = Date.now() - touch.t < 700;
        touch = null;
        if (!quick) return;
        if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.2) { step(dx < 0 ? 1 : -1); return; }
        // A vertical swipe pages only when the player is not itself scrolling.
        var shell = dialog.querySelector('.lt-player-shell');
        var scrolls = shell && shell.scrollHeight > shell.clientHeight + 2;
        if (!scrolls && Math.abs(dy) > 70 && Math.abs(dy) > Math.abs(dx) * 1.2) step(dy < 0 ? 1 : -1);
    }, { passive: true });
})();
