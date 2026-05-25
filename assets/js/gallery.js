/* Nerra Network image gallery (Phase 2 — client renderer).
 *
 * Loads the static manifest at MANIFEST_URL, renders a thumbnail grid
 * (lazy-loaded), and wires up:
 *   - search (free-text across caption + prompt + tags)
 *   - show filter (single or multi-select; multi when on /gallery)
 *   - sort (newest / oldest)
 *   - lightbox with prev/next, caption, prompt toggle, download button
 *   - email-gate modal STUB. Phase 3 wires this to a Cloudflare Worker
 *     that POSTs to Buttondown + signs the R2 download URL. For now,
 *     submitting the email logs a console message and the download
 *     proceeds straight to the original_url (the bucket policy in
 *     Phase 1 already keeps originals private — the public URL today
 *     resolves to 403 until the Worker exists).
 *
 * Mount: a single root element with [data-nn-gallery]. Optional
 * data attributes:
 *   data-show-slug   — limit to one show (per-show embed)
 *   data-page-size   — initial render size; defaults to 60
 *   data-show-filter — "hide" suppresses the show filter pill row
 *                      (used by per-show embeds — the show is fixed)
 */
(function () {
    'use strict';

    var MANIFEST_URL = (window.NN_GALLERY_MANIFEST_URL ||
        '/site/data/gallery-manifest.json');
    // Worker base URL. Phase 3 deploys the Worker at
    // api.nerranetwork.com; the override exists so local dev
    // (python -m http.server 8080 + wrangler dev) can point at
    // http://127.0.0.1:8787 without editing this file.
    var API_BASE = (window.NN_GALLERY_API_BASE ||
        'https://api.nerranetwork.com').replace(/\/+$/, '');
    var PROMPT_PREFIX_RE = /^[^,]+,\s*photorealistic[^,]*,\s*/i;

    function $(sel, root) { return (root || document).querySelector(sel); }
    function $$(sel, root) {
        return Array.prototype.slice.call((root || document).querySelectorAll(sel));
    }

    function escapeHtml(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function formatDate(s) {
        if (!s) return '';
        try {
            var d = new Date(s.length === 10 ? s + 'T00:00:00Z' : s);
            if (isNaN(d.getTime())) return s;
            return d.toLocaleDateString(undefined, {
                year: 'numeric', month: 'short', day: 'numeric',
                timeZone: 'UTC',
            });
        } catch (_) { return s; }
    }

    function shortPrompt(p) {
        if (!p) return '';
        // The pipeline's prompts often start with the show's curated
        // image query then a long descriptor / framing tail. Strip the
        // boilerplate tail when present so the toggle reveals the
        // human-meaningful subject, not the cookie-cutter cinematic
        // framing instructions that repeat on every image.
        var idx = p.indexOf(', clean photographic');
        if (idx > 12) p = p.slice(0, idx);
        return p;
    }

    // ---------- State ----------

    function GalleryState(images, opts) {
        this.all = images || [];
        this.opts = opts || {};
        this.filter = {
            query: '',
            shows: opts.fixedShowSlug ? [opts.fixedShowSlug] : [],
            sort: 'newest',
        };
        this.visible = this.all.slice();
        this.pageSize = opts.pageSize || 60;
        this.rendered = 0;
    }

    GalleryState.prototype.applyFilter = function () {
        var q = this.filter.query.trim().toLowerCase();
        var shows = this.filter.shows;
        var sort = this.filter.sort;
        var visible = this.all.filter(function (img) {
            if (shows.length && shows.indexOf(img.show_slug) === -1) {
                return false;
            }
            if (!q) return true;
            var hay = [
                img.caption, img.prompt, img.show_name,
                img.episode_title,
                (img.tags || []).join(' '),
            ].join(' ').toLowerCase();
            return hay.indexOf(q) !== -1;
        });
        // The manifest arrives sorted newest-first. Only flip when the
        // user selects oldest.
        if (sort === 'oldest') visible.reverse();
        this.visible = visible;
        this.rendered = 0;
    };

    // ---------- Render ----------

    function renderCard(img) {
        // Per-image card — pure DOM string, hydrated into the grid.
        // Use loading="lazy" on the <img> so off-screen thumbnails
        // don't fetch until the viewer scrolls near them.
        var meta = formatDate(img.episode_date) +
            (img.show_name ? ' · ' + escapeHtml(img.show_name) : '');
        var altText = img.caption || img.episode_title || (
            (img.show_name || 'Nerra Network') + ' image'
        );
        return (
            '<figure class="nn-gallery-card" tabindex="0" ' +
                'data-image-id="' + escapeHtml(img.image_id) + '" ' +
                'aria-label="' + escapeHtml(altText) + '">' +
                '<div class="nn-gallery-card-thumb">' +
                    '<img loading="lazy" decoding="async" ' +
                        'src="' + escapeHtml(img.thumbnail_url) + '" ' +
                        'alt="' + escapeHtml(altText) + '">' +
                '</div>' +
                '<figcaption class="nn-gallery-card-meta">' +
                    '<span class="nn-gallery-card-show">' +
                        escapeHtml(img.show_name || img.show_slug) +
                    '</span>' +
                    '<span class="nn-gallery-card-date">' +
                        escapeHtml(formatDate(img.episode_date)) +
                    '</span>' +
                '</figcaption>' +
            '</figure>'
        );
    }

    function renderShowFilter(grid, state) {
        if (state.opts.suppressShowFilter) return '';
        if (state.opts.shows.length < 2) return '';
        var pills = state.opts.shows.map(function (s) {
            var active = state.filter.shows.indexOf(s.slug) !== -1
                ? ' is-active' : '';
            return (
                '<button type="button" class="nn-gallery-pill' + active + '" ' +
                    'data-show-slug="' + escapeHtml(s.slug) + '">' +
                    escapeHtml(s.name) +
                    ' <span class="nn-gallery-pill-count">' + s.image_count + '</span>' +
                '</button>'
            );
        }).join('');
        return (
            '<div class="nn-gallery-filters-row" role="group" ' +
                'aria-label="Filter by show">' +
                '<button type="button" class="nn-gallery-pill' +
                    (state.filter.shows.length === 0 ? ' is-active' : '') +
                    '" data-show-slug="">All shows</button>' +
                pills +
            '</div>'
        );
    }

    function renderControls(state) {
        if (state.opts.suppressControls) return '';
        return (
            '<div class="nn-gallery-controls">' +
                '<label class="nn-gallery-search">' +
                    '<span class="nn-vh">Search images</span>' +
                    '<input type="search" placeholder="Search captions, prompts, tags…" ' +
                        'class="nn-gallery-search-input">' +
                '</label>' +
                '<label class="nn-gallery-sort">' +
                    '<span class="nn-vh">Sort</span>' +
                    '<select class="nn-gallery-sort-select">' +
                        '<option value="newest">Newest first</option>' +
                        '<option value="oldest">Oldest first</option>' +
                    '</select>' +
                '</label>' +
            '</div>'
        );
    }

    function renderEmptyState(state) {
        if (state.all.length === 0) {
            return (
                '<p class="nn-gallery-empty">No gallery images have ' +
                'been published yet. Check back after the next episode ' +
                'with AI-generated visuals.</p>'
            );
        }
        return (
            '<p class="nn-gallery-empty">No images match the current ' +
            'filters. Clear the search or try a different show.</p>'
        );
    }

    function renderPage(grid, state) {
        var end = Math.min(state.rendered + state.pageSize, state.visible.length);
        var html = '';
        for (var i = state.rendered; i < end; i++) {
            html += renderCard(state.visible[i]);
        }
        if (html) grid.insertAdjacentHTML('beforeend', html);
        state.rendered = end;
    }

    function render(host, state) {
        var controls = renderControls(state);
        var filters = renderShowFilter(null, state);
        host.innerHTML = (
            controls +
            filters +
            '<div class="nn-gallery-status" aria-live="polite"></div>' +
            '<div class="nn-gallery-grid" role="list"></div>' +
            '<div class="nn-gallery-more-wrap">' +
                '<button type="button" class="nn-gallery-more nn-btn">Show more</button>' +
            '</div>'
        );
        var grid = $('.nn-gallery-grid', host);
        var status = $('.nn-gallery-status', host);
        var moreBtn = $('.nn-gallery-more', host);

        function refresh() {
            state.applyFilter();
            grid.innerHTML = '';
            if (state.visible.length === 0) {
                grid.innerHTML = renderEmptyState(state);
                moreBtn.style.display = 'none';
                status.textContent = '';
                return;
            }
            renderPage(grid, state);
            updateMoreButton();
            status.textContent = (
                'Showing ' + Math.min(state.rendered, state.visible.length) +
                ' of ' + state.visible.length + ' image' +
                (state.visible.length === 1 ? '' : 's')
            );
        }

        function updateMoreButton() {
            if (state.rendered >= state.visible.length) {
                moreBtn.style.display = 'none';
            } else {
                moreBtn.style.display = '';
                moreBtn.textContent = (
                    'Show more (' + (state.visible.length - state.rendered) +
                    ' remaining)'
                );
            }
        }

        moreBtn.addEventListener('click', function () {
            renderPage(grid, state);
            updateMoreButton();
            status.textContent = (
                'Showing ' + Math.min(state.rendered, state.visible.length) +
                ' of ' + state.visible.length + ' images'
            );
        });

        var searchInput = $('.nn-gallery-search-input', host);
        if (searchInput) {
            var searchTimer = null;
            searchInput.addEventListener('input', function (e) {
                clearTimeout(searchTimer);
                searchTimer = setTimeout(function () {
                    state.filter.query = e.target.value;
                    refresh();
                }, 120);
            });
        }

        var sortSelect = $('.nn-gallery-sort-select', host);
        if (sortSelect) {
            sortSelect.addEventListener('change', function (e) {
                state.filter.sort = e.target.value;
                refresh();
            });
        }

        host.addEventListener('click', function (e) {
            var pill = e.target.closest && e.target.closest('.nn-gallery-pill');
            if (pill) {
                var slug = pill.getAttribute('data-show-slug');
                if (slug) {
                    var idx = state.filter.shows.indexOf(slug);
                    if (idx === -1) state.filter.shows.push(slug);
                    else state.filter.shows.splice(idx, 1);
                } else {
                    state.filter.shows = [];
                }
                $$('.nn-gallery-pill', host).forEach(function (el) {
                    var elSlug = el.getAttribute('data-show-slug');
                    var on = elSlug ? (state.filter.shows.indexOf(elSlug) !== -1)
                                    : state.filter.shows.length === 0;
                    el.classList.toggle('is-active', on);
                });
                refresh();
                return;
            }
            var card = e.target.closest && e.target.closest('.nn-gallery-card');
            if (card) {
                openLightbox(state, card.getAttribute('data-image-id'));
            }
        });

        host.addEventListener('keydown', function (e) {
            if (e.key !== 'Enter' && e.key !== ' ') return;
            var card = e.target.closest && e.target.closest('.nn-gallery-card');
            if (card) {
                e.preventDefault();
                openLightbox(state, card.getAttribute('data-image-id'));
            }
        });

        refresh();
    }

    // ---------- Lightbox ----------

    function ensureLightbox() {
        var lb = $('.nn-gallery-lightbox');
        if (lb) return lb;
        lb = document.createElement('div');
        lb.className = 'nn-gallery-lightbox';
        lb.setAttribute('aria-hidden', 'true');
        lb.setAttribute('role', 'dialog');
        lb.setAttribute('aria-modal', 'true');
        lb.innerHTML = (
            '<button type="button" class="nn-lb-close" aria-label="Close">×</button>' +
            '<button type="button" class="nn-lb-prev" aria-label="Previous image">‹</button>' +
            '<button type="button" class="nn-lb-next" aria-label="Next image">›</button>' +
            '<figure class="nn-lb-figure">' +
                '<div class="nn-lb-image-wrap"><img class="nn-lb-image" alt=""></div>' +
                '<figcaption class="nn-lb-meta">' +
                    '<div class="nn-lb-title"></div>' +
                    '<div class="nn-lb-sub"></div>' +
                    '<div class="nn-lb-actions">' +
                        '<button type="button" class="nn-lb-prompt-toggle nn-btn nn-btn-ghost">Show prompt</button>' +
                        '<button type="button" class="nn-lb-download nn-btn">Download full size</button>' +
                    '</div>' +
                    '<details class="nn-lb-prompt" hidden>' +
                        '<summary class="nn-vh">Prompt</summary>' +
                        '<pre class="nn-lb-prompt-text"></pre>' +
                    '</details>' +
                    '<div class="nn-lb-license"></div>' +
                '</figcaption>' +
            '</figure>'
        );
        document.body.appendChild(lb);

        lb.addEventListener('click', function (e) {
            if (e.target === lb || e.target.classList.contains('nn-lb-close')) {
                closeLightbox();
            } else if (e.target.classList.contains('nn-lb-prev')) {
                navLightbox(-1);
            } else if (e.target.classList.contains('nn-lb-next')) {
                navLightbox(+1);
            } else if (e.target.classList.contains('nn-lb-prompt-toggle')) {
                var details = $('.nn-lb-prompt', lb);
                var hidden = details.hasAttribute('hidden');
                if (hidden) details.removeAttribute('hidden');
                else details.setAttribute('hidden', '');
                e.target.textContent = hidden ? 'Hide prompt' : 'Show prompt';
            } else if (e.target.classList.contains('nn-lb-download')) {
                handleDownload();
            }
        });
        document.addEventListener('keydown', function (e) {
            if (lb.getAttribute('aria-hidden') === 'true') return;
            if (e.key === 'Escape') closeLightbox();
            else if (e.key === 'ArrowLeft') navLightbox(-1);
            else if (e.key === 'ArrowRight') navLightbox(+1);
        });
        return lb;
    }

    var _lbState = { state: null, index: -1 };

    function openLightbox(state, imageId) {
        var idx = -1;
        for (var i = 0; i < state.visible.length; i++) {
            if (state.visible[i].image_id === imageId) { idx = i; break; }
        }
        if (idx === -1) return;
        _lbState.state = state;
        _lbState.index = idx;
        var lb = ensureLightbox();
        lb.setAttribute('aria-hidden', 'false');
        document.body.classList.add('nn-no-scroll');
        paintLightbox();
    }

    function closeLightbox() {
        var lb = $('.nn-gallery-lightbox');
        if (!lb) return;
        lb.setAttribute('aria-hidden', 'true');
        document.body.classList.remove('nn-no-scroll');
        _lbState.state = null;
        _lbState.index = -1;
    }

    function navLightbox(delta) {
        if (!_lbState.state) return;
        var n = _lbState.state.visible.length;
        _lbState.index = ((_lbState.index + delta) % n + n) % n;
        paintLightbox();
    }

    function paintLightbox() {
        var lb = $('.nn-gallery-lightbox');
        if (!lb || !_lbState.state) return;
        var img = _lbState.state.visible[_lbState.index];
        var imgEl = $('.nn-lb-image', lb);
        imgEl.src = img.thumbnail_url;
        imgEl.alt = img.caption || img.episode_title || (img.show_name || '') + ' image';
        // Phase 3: originals are private (the Worker proxies them
        // through /api/download). The lightbox stays on the 800-px
        // watermarked thumbnail, which is the right size for a modal
        // preview. The "Download full size" button takes the visitor
        // through the email gate to fetch the original.

        $('.nn-lb-title', lb).textContent = img.episode_title || '';
        $('.nn-lb-sub', lb).textContent = [
            img.show_name, formatDate(img.episode_date),
        ].filter(Boolean).join(' · ');

        var promptDetails = $('.nn-lb-prompt', lb);
        var promptToggle = $('.nn-lb-prompt-toggle', lb);
        var promptText = $('.nn-lb-prompt-text', lb);
        var p = shortPrompt(img.prompt);
        if (p) {
            promptText.textContent = p;
            promptToggle.style.display = '';
            promptToggle.textContent = 'Show prompt';
            promptDetails.setAttribute('hidden', '');
        } else {
            promptToggle.style.display = 'none';
            promptDetails.setAttribute('hidden', '');
        }

        var lic = (img.license || 'CC BY-SA 4.0') + ' · ' +
                  (img.attribution || 'Nerra Network');
        if (img.license_url) {
            $('.nn-lb-license', lb).innerHTML = (
                '<a href="' + escapeHtml(img.license_url) +
                '" target="_blank" rel="noopener">' + escapeHtml(lic) + '</a>'
            );
        } else {
            $('.nn-lb-license', lb).textContent = lic;
        }
    }

    // ---------- Download gate (Phase 3 — wired to api.nerranetwork.com) ----------

    function downloadEndpoint(key) {
        return API_BASE + '/api/download?key=' + encodeURIComponent(key);
    }
    function subscribeEndpoint() { return API_BASE + '/api/subscribe'; }
    function loginEndpoint(email) {
        return API_BASE + '/api/login?email=' + encodeURIComponent(email);
    }

    // Programmatic download: fetch the bytes through the Worker so
    // we re-validate the JWT cookie on every download (revocation
    // works) and the browser triggers a real save dialog via
    // <a download>. If the Worker says 401 we open the gate; on any
    // other error we surface a console warning and let the visitor
    // retry. Note: cross-origin <a download> respects
    // Content-Disposition from the Worker.
    function handleDownload() {
        if (!_lbState.state) return;
        var img = _lbState.state.visible[_lbState.index];
        if (!img || !img.original_key) return;
        fetch(downloadEndpoint(img.original_key), {
            method: 'GET',
            credentials: 'include',
        }).then(function (resp) {
            if (resp.status === 401) {
                openGateModal();
                return null;
            }
            if (!resp.ok) {
                throw new Error('download HTTP ' + resp.status);
            }
            return resp.blob().then(function (blob) {
                var url = URL.createObjectURL(blob);
                var a = document.createElement('a');
                a.href = url;
                a.download = img.original_key.split('/').pop() || 'image';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                setTimeout(function () { URL.revokeObjectURL(url); }, 30000);
                if (typeof window.gtag === 'function') {
                    try { window.gtag('event', 'gallery_download', { image_id: img.image_id }); }
                    catch (_) {}
                }
            });
        }).catch(function (err) {
            if (typeof console !== 'undefined') {
                console.warn('[gallery] download failed:', err);
            }
            // Fallback: open the gate so they can sign in / sign up.
            openGateModal();
        });
    }

    function ensureGateModal() {
        var m = $('.nn-gate-modal');
        if (m) return m;
        m = document.createElement('div');
        m.className = 'nn-gate-modal';
        m.setAttribute('aria-hidden', 'true');
        m.setAttribute('role', 'dialog');
        m.setAttribute('aria-modal', 'true');
        m.innerHTML = (
            '<div class="nn-gate-card">' +
                '<button type="button" class="nn-gate-close" aria-label="Close">×</button>' +
                '<h2 class="nn-gate-title">One-time email to download</h2>' +
                '<p class="nn-gate-body">Originals are gated behind a ' +
                    'free email subscription. We&rsquo;ll send you ' +
                    'occasional Nerra Network updates and you can ' +
                    'download any image at full resolution from then on.</p>' +
                '<form class="nn-gate-form" data-mode="subscribe">' +
                    '<label><span class="nn-vh">Email</span>' +
                        '<input type="email" required placeholder="you@example.com" ' +
                            'autocomplete="email" class="nn-gate-input">' +
                    '</label>' +
                    '<button type="submit" class="nn-btn nn-gate-submit">Subscribe &amp; download</button>' +
                '</form>' +
                '<p class="nn-gate-fineprint">By subscribing you agree to ' +
                    'receive emails from Nerra Network. Unsubscribe any time. ' +
                    '<a href="#" class="nn-gate-toggle">Already subscribed? Sign in instead.</a>' +
                '</p>' +
                '<p class="nn-gate-error" hidden></p>' +
                '<p class="nn-gate-success" hidden></p>' +
            '</div>'
        );
        document.body.appendChild(m);
        m.addEventListener('click', function (e) {
            if (e.target === m || e.target.classList.contains('nn-gate-close')) {
                closeGateModal();
                return;
            }
            if (e.target.classList && e.target.classList.contains('nn-gate-toggle')) {
                e.preventDefault();
                toggleGateMode(m);
            }
        });
        m.addEventListener('submit', function (e) {
            e.preventDefault();
            var input = $('.nn-gate-input', m);
            var email = (input && input.value || '').trim();
            if (!email) return;
            var mode = $('.nn-gate-form', m).getAttribute('data-mode');
            if (mode === 'login') submitLogin(email, m);
            else submitSubscribe(email, m);
        });
        return m;
    }

    function toggleGateMode(m) {
        var form = $('.nn-gate-form', m);
        var title = $('.nn-gate-title', m);
        var body = $('.nn-gate-body', m);
        var submit = $('.nn-gate-submit', m);
        var toggle = $('.nn-gate-toggle', m);
        var success = $('.nn-gate-success', m);
        var error = $('.nn-gate-error', m);
        if (success) success.setAttribute('hidden', '');
        if (error) error.setAttribute('hidden', '');
        if (form.getAttribute('data-mode') === 'subscribe') {
            form.setAttribute('data-mode', 'login');
            title.textContent = 'Sign in to download';
            body.textContent = 'Enter the email you previously subscribed with. ' +
                'We’ll send you a one-click sign-in link.';
            submit.textContent = 'Send sign-in link';
            toggle.textContent = 'Don’t have an account? Subscribe instead.';
        } else {
            form.setAttribute('data-mode', 'subscribe');
            title.textContent = 'One-time email to download';
            body.innerHTML = 'Originals are gated behind a ' +
                'free email subscription. We’ll send you ' +
                'occasional Nerra Network updates and you can ' +
                'download any image at full resolution from then on.';
            submit.textContent = 'Subscribe & download';
            toggle.textContent = 'Already subscribed? Sign in instead.';
        }
    }

    function openGateModal() {
        var m = ensureGateModal();
        m.setAttribute('aria-hidden', 'false');
        document.body.classList.add('nn-no-scroll');
        var input = $('.nn-gate-input', m);
        if (input) setTimeout(function () { input.focus(); }, 30);
    }

    function closeGateModal() {
        var m = $('.nn-gate-modal');
        if (!m) return;
        m.setAttribute('aria-hidden', 'true');
        if (!$('.nn-gallery-lightbox[aria-hidden="false"]')) {
            document.body.classList.remove('nn-no-scroll');
        }
    }

    function showGateError(modal, message) {
        var el = $('.nn-gate-error', modal);
        if (!el) return;
        el.textContent = message;
        el.removeAttribute('hidden');
    }

    function showGateSuccess(modal, message) {
        var el = $('.nn-gate-success', modal);
        if (!el) return;
        el.textContent = message;
        el.removeAttribute('hidden');
    }

    function setGateBusy(modal, busy) {
        var submit = $('.nn-gate-submit', modal);
        if (submit) submit.disabled = !!busy;
    }

    function submitSubscribe(email, modal) {
        var errEl = $('.nn-gate-error', modal);
        var okEl = $('.nn-gate-success', modal);
        if (errEl) errEl.setAttribute('hidden', '');
        if (okEl) okEl.setAttribute('hidden', '');
        setGateBusy(modal, true);
        fetch(subscribeEndpoint(), {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: email }),
        }).then(function (resp) {
            if (resp.ok) {
                if (typeof window.gtag === 'function') {
                    try { window.gtag('event', 'gallery_subscribe', { email_domain: email.split('@')[1] || '' }); }
                    catch (_) {}
                }
                closeGateModal();
                // Retry the download — the cookie is now set.
                handleDownload();
                return;
            }
            return resp.json().then(function (body) {
                showGateError(modal,
                    (body && body.error)
                        ? ('Couldn’t subscribe: ' + body.error)
                        : 'Couldn’t subscribe. Please try again in a moment.');
            }, function () {
                showGateError(modal, 'Couldn’t subscribe. Please try again in a moment.');
            });
        }).catch(function () {
            showGateError(modal, 'Network error. Please check your connection and retry.');
        }).then(function () { setGateBusy(modal, false); });
    }

    function submitLogin(email, modal) {
        var errEl = $('.nn-gate-error', modal);
        var okEl = $('.nn-gate-success', modal);
        if (errEl) errEl.setAttribute('hidden', '');
        if (okEl) okEl.setAttribute('hidden', '');
        setGateBusy(modal, true);
        fetch(loginEndpoint(email), {
            method: 'GET',
            credentials: 'include',
        }).then(function (resp) {
            // The API always returns 200 to avoid email enumeration —
            // so we show the same success message regardless of
            // whether the address is actually subscribed.
            if (resp.ok) {
                showGateSuccess(modal,
                    'If that email is subscribed, a sign-in link is on the way. ' +
                    'Check your inbox (and spam folder).');
                if (typeof window.gtag === 'function') {
                    try { window.gtag('event', 'gallery_login_requested'); }
                    catch (_) {}
                }
            } else {
                showGateError(modal, 'Couldn’t send the link. Please try again.');
            }
        }).catch(function () {
            showGateError(modal, 'Network error. Please check your connection and retry.');
        }).then(function () { setGateBusy(modal, false); });
    }

    // ---------- Bootstrap ----------

    function init(host) {
        var fixedShowSlug = host.getAttribute('data-show-slug') || '';
        var pageSize = parseInt(host.getAttribute('data-page-size'), 10);
        var suppressShowFilter = host.getAttribute('data-show-filter') === 'hide';
        var suppressControls = host.getAttribute('data-controls') === 'hide';

        host.classList.add('nn-gallery');
        host.innerHTML = '<p class="nn-gallery-loading">Loading gallery…</p>';

        fetch(MANIFEST_URL, { credentials: 'omit' })
            .then(function (r) {
                if (!r.ok) throw new Error('manifest HTTP ' + r.status);
                return r.json();
            })
            .then(function (manifest) {
                var images = manifest.images || [];
                var shows = manifest.shows || [];
                if (fixedShowSlug) {
                    images = images.filter(function (i) {
                        return i.show_slug === fixedShowSlug;
                    });
                }
                var state = new GalleryState(images, {
                    fixedShowSlug: fixedShowSlug,
                    shows: shows,
                    pageSize: pageSize > 0 ? pageSize : 60,
                    suppressShowFilter: suppressShowFilter || !!fixedShowSlug,
                    suppressControls: suppressControls,
                });
                render(host, state);
            })
            .catch(function (err) {
                host.innerHTML = (
                    '<p class="nn-gallery-empty">Gallery manifest ' +
                    'unavailable: ' + escapeHtml(err.message || err) +
                    '. Try refreshing in a moment.</p>'
                );
            });
    }

    function bootAll() {
        $$('[data-nn-gallery]').forEach(init);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', bootAll);
    } else {
        bootAll();
    }
})();
