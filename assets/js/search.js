/**
 * Global site search powered by the static Content Lake index.
 *
 * Robustness & UX features:
 * - Debounced input + localStorage cache (12h TTL) for instant repeat visits
 *   and tolerance of transient fetch issues during deploys/index rebuilds
 * - Loading / error / empty states with actionable guidance
 * - Keyboard navigation (arrows, Enter, Escape, '/' to focus)
 * - ARIA roles for screen readers (combobox + listbox + live region)
 * - Match highlighting + improved scoring (title, hook, summary, entities, recency, episode #)
 * - Clear (×) button, result caps, indexed count footer
 * - Graceful fallback when index empty or unavailable
 */

(function () {
  const input = document.getElementById('nn-global-search-input');
  const resultsBox = document.getElementById('nn-global-search-results');
  if (!input || !resultsBox) return;

  let cached = null; // { episodes: [...] }
  let isLoading = false;
  let selectedIndex = -1;

  const INDEX_URL = '/site/data/search-index.json';

  // Legacy fallback kept for safety during transition
  const LEGACY_ENDPOINTS = [
    '/api/tesla.json', '/api/models_agents.json', '/api/fascinating_frontiers.json',
    '/api/omni_view.json', '/api/planetterrian.json', '/api/modern_investing.json',
    '/api/env_intel.json', '/api/finansy_prosto.json', '/api/privet_russian.json',
    '/api/unintended_consequences.json'
  ];

  function norm(s) { return (s || '').toLowerCase().trim(); }

  function debounce(fn, delay) {
    let timeout;
    return function (...args) {
      clearTimeout(timeout);
      timeout = setTimeout(() => fn.apply(this, args), delay);
    };
  }

  function scoreItem(it, q) {
    const t = norm(it.title);
    const h = norm(it.hook);
    const sum = norm(it.summary);
    const s = norm(it.show_name || it.show_slug);
    const ents = (it.entities || []).join(' ').toLowerCase();
    const topics = (it.topics || []).join(' ').toLowerCase();
    const epNum = String(it.episode_num || '').toLowerCase();

    let score = 0;

    // Title (highest weight)
    if (t === q) score += 220;
    else if (t.startsWith(q)) score += 140;
    else if (t.includes(q)) score += 95;
    else if (q.length > 3 && t.split(/\s+/).some(w => w.startsWith(q))) score += 60; // word start

    // Hook + summary (core content)
    if (h.includes(q)) score += 45;
    if (sum.includes(q)) score += 40;
    if (h.includes(q) && sum.includes(q)) score += 10; // both

    if (ents.includes(q)) score += 30;
    if (topics.includes(q)) score += 22;
    if (s.includes(q)) score += 12;

    // Direct episode number match (very useful for "ep 461")
    if (epNum && (epNum === q || epNum.includes(q))) score += 85;

    // Recency (days-based, favors last ~90 days)
    if (it.date) {
      const d = new Date(it.date);
      if (!isNaN(d.getTime())) {
        const days = Math.max(0, (Date.now() - d.getTime()) / 86400000);
        score += Math.max(0, 28 - Math.min(days / 3.5, 28));
      }
    }

    return score;
  }

  function highlight(text, query) {
    if (!text || !query) return text || '';
    const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const regex = new RegExp(`(${escaped})`, 'gi');
    return text.replace(regex, '<mark>$1</mark>');
  }

  const CACHE_KEY = 'nn_search_index_v1';
  const CACHE_TTL_MS = 12 * 60 * 60 * 1000; // 12h — robust to brief deploys / rebuilds

  function readCache() {
    try {
      const raw = localStorage.getItem(CACHE_KEY);
      if (!raw) return null;
      const obj = JSON.parse(raw);
      if (obj && obj.t && (Date.now() - obj.t) < CACHE_TTL_MS && obj.data && Array.isArray(obj.data.episodes)) {
        return { episodes: obj.data.episodes };
      }
    } catch (_) {}
    return null;
  }

  function writeCache(episodes) {
    try {
      localStorage.setItem(CACHE_KEY, JSON.stringify({
        t: Date.now(),
        data: { episodes: episodes }
      }));
    } catch (_) { /* quota or private mode */ }
  }

  async function loadIndex() {
    if (cached) return cached;

    // Fast path: recent localStorage cache (robustness + instant UX)
    const fromCache = readCache();
    if (fromCache && fromCache.episodes && fromCache.episodes.length > 0) {
      cached = fromCache;
      // Background refresh (non-blocking)
      refreshIndexInBackground();
      return cached;
    }

    if (isLoading) return null;
    isLoading = true;
    showLoading();

    try {
      const res = await fetch(INDEX_URL, { credentials: 'same-origin' });
      if (res.ok) {
        const data = await res.json();
        const eps = data.episodes || [];
        cached = { episodes: eps };
        writeCache(eps);
        hideLoading();
        isLoading = false;
        return cached;
      }
    } catch (e) {
      // fall through to legacy + cache
    }

    // Legacy fallback (kept for extreme robustness during transition)
    try {
      const items = [];
      for (const endpoint of LEGACY_ENDPOINTS) {
        try {
          const r = await fetch(endpoint, { credentials: 'same-origin' });
          if (!r.ok) continue;
          const d = await r.json();
          const eps = d.episodes || d || [];
          for (const e of eps) {
            items.push({
              title: e.title || e.episode_title || '',
              hook: e.hook || e.summary || '',
              show_slug: (d.slug || endpoint.split('/').pop().replace('.json', '')),
              show_name: d.name || '',
              url: e.url || ('/' + (d.slug || '') + '.html'),
              date: e.date || '',
              entities: e.entities || [],
              topics: e.topics || [],
              episode_num: e.episode_num || null
            });
          }
        } catch (_) {}
      }
      if (items.length > 0) {
        cached = { episodes: items };
        writeCache(items);
      }
      hideLoading();
      isLoading = false;
      return cached || { episodes: [] };
    } catch (e) {
      hideLoading();
      isLoading = false;
      // Last resort: stale cache even if expired
      const stale = readCache();
      if (stale) return stale;
      showError("Search is temporarily unavailable. Please try again later.");
      return { episodes: [] };
    }
  }

  async function refreshIndexInBackground() {
    try {
      const res = await fetch(INDEX_URL, { credentials: 'same-origin' });
      if (res.ok) {
        const data = await res.json();
        const eps = data.episodes || [];
        if (eps.length > 0) {
          cached = { episodes: eps };
          writeCache(eps);
        }
      }
    } catch (_) {}
  }

  // Live region for screen readers (robust a11y)
  let liveRegion = null;
  function ensureLiveRegion() {
    if (liveRegion) return liveRegion;
    liveRegion = document.createElement('div');
    liveRegion.setAttribute('aria-live', 'polite');
    liveRegion.setAttribute('aria-atomic', 'true');
    liveRegion.className = 'sr-only';
    liveRegion.style.cssText = 'position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0;';
    document.body.appendChild(liveRegion);
    return liveRegion;
  }

  function announce(msg) {
    const lr = ensureLiveRegion();
    lr.textContent = msg;
  }

  function showLoading() {
    resultsBox.innerHTML = '<div style="padding:8px 12px;color:var(--nn-text-muted);">Loading search index...</div>';
    resultsBox.style.display = 'block';
    resultsBox.setAttribute('aria-busy', 'true');
  }

  function hideLoading() {
    resultsBox.setAttribute('aria-busy', 'false');
  }

  function showError(msg) {
    resultsBox.innerHTML = `<div style="padding:8px 12px;color:#ef4444;">${msg}</div>`;
    resultsBox.style.display = 'block';
    announce(msg);
  }

  function renderResults(matches, query) {
    selectedIndex = -1;

    const totalIndexed = (cached && cached.episodes) ? cached.episodes.length : 0;

    if (!matches.length) {
      const emptyMsg = totalIndexed > 0
        ? `No matches for “${query}”. Index covers ${totalIndexed} episodes — try a show name, topic, or fewer words.`
        : 'Search index is updating (refreshes after every episode). Try again shortly or browse shows directly.';
      resultsBox.innerHTML = `
        <div style="padding:10px 12px;color:var(--nn-text-muted);">
          ${emptyMsg}
        </div>`;
      announce(`No matches for ${query}. ${totalIndexed} episodes indexed.`);
    } else {
      const total = matches.length;
      const shown = Math.min(14, total); // a few more now that scoring is richer

      let html = matches.slice(0, shown).map((m, i) => {
        const primary = (m.title || m.hook || '').substring(0, 92);
        const label = highlight(primary, query);
        const ep = m.episode_num ? `Ep ${m.episode_num}` : '';
        const metaParts = [
          m.show_name || m.show_slug || '',
          ep,
          m.date || ''
        ].filter(Boolean);
        const meta = metaParts.join(' · ');

        const entities = (m.entities || []).slice(0, 2).join(', ');
        const sub = (m.hook && m.hook.length > 12 ? m.hook : (m.summary || '')).substring(0, 110);
        const subLabel = sub ? highlight(sub, query) : '';

        const fullMeta = meta + (entities ? ` · ${entities}` : '');

        return `
          <a href="${m.url || '#'}" 
             class="search-result" 
             data-index="${i}"
             role="option"
             style="display:block;padding:8px 12px;text-decoration:none;color:inherit;border-bottom:1px solid var(--nn-border);">
            <div><strong>${label}</strong></div>
            ${subLabel ? `<div style="font-size:0.8em;opacity:0.75;margin:2px 0 1px;">${subLabel}</div>` : ''}
            <small style="opacity:0.65">${fullMeta}</small>
          </a>`;
      }).join('');

      if (total > shown) {
        html += `<div style="padding:6px 12px;font-size:0.75rem;color:var(--nn-text-muted);background:var(--nn-bg);">
          Showing ${shown} of ${total} matches
        </div>`;
      }
      if (totalIndexed > 0) {
        html += `<div style="padding:4px 12px;font-size:0.7rem;color:var(--nn-text-muted);opacity:0.6;border-top:1px solid var(--nn-border);">
          ${totalIndexed} episodes indexed • updates after every episode
        </div>`;
      }

      resultsBox.innerHTML = html;
      announce(`${total} results for ${query}.`);
    }

    resultsBox.style.display = 'block';

    // Hover + keyboard selection sync
    const links = resultsBox.querySelectorAll('.search-result');
    links.forEach(link => {
      link.addEventListener('mouseenter', () => {
        links.forEach(l => l.style.background = '');
        link.style.background = 'var(--nn-surface)';
        selectedIndex = parseInt(link.dataset.index || '-1', 10);
      });
      link.addEventListener('mouseleave', () => {
        link.style.background = '';
      });
    });

    // Update ARIA
    input.setAttribute('aria-expanded', 'true');
    resultsBox.setAttribute('aria-activedescendant', '');
  }

  function selectResult(index) {
    const links = resultsBox.querySelectorAll('.search-result');
    links.forEach(l => l.style.background = '');

    if (index >= 0 && index < links.length) {
      const link = links[index];
      link.style.background = 'var(--nn-surface)';
      link.scrollIntoView({ block: 'nearest' });
      selectedIndex = index;
    }
  }

  const debouncedSearch = debounce(async function () {
    const q = norm(input.value.trim());
    if (q.length < 2) {
      resultsBox.style.display = 'none';
      return;
    }

    const idx = await loadIndex();
    if (!idx || !idx.episodes || idx.episodes.length === 0) {
      showError("Search index not available yet. It updates after every episode.");
      return;
    }

    const scored = idx.episodes
      .map(e => ({ item: e, score: scoreItem(e, q) }))
      .filter(x => x.score > 0)
      .sort((a, b) => b.score - a.score)
      .map(x => x.item);

    renderResults(scored, q);
  }, 120);

  // Wire ARIA + clear button + hotkeys
  input.setAttribute('role', 'combobox');
  input.setAttribute('aria-autocomplete', 'list');
  input.setAttribute('aria-controls', 'nn-global-search-results');
  input.setAttribute('aria-expanded', 'false');
  resultsBox.setAttribute('role', 'listbox');
  resultsBox.setAttribute('aria-label', 'Search results');

  // Clear (×) button — injected once
  let clearBtn = null;
  function ensureClearButton() {
    if (clearBtn) return clearBtn;
    clearBtn = document.createElement('button');
    clearBtn.type = 'button';
    clearBtn.setAttribute('aria-label', 'Clear search');
    clearBtn.textContent = '×';
    clearBtn.style.cssText = 'position:absolute;right:6px;top:50%;transform:translateY(-50%);width:18px;height:18px;border:0;background:transparent;color:var(--nn-text-muted);font-size:16px;line-height:1;cursor:pointer;opacity:0.6;display:none;';
    clearBtn.addEventListener('click', (ev) => {
      ev.preventDefault();
      input.value = '';
      resultsBox.style.display = 'none';
      input.setAttribute('aria-expanded', 'false');
      clearBtn.style.display = 'none';
      input.focus();
    });
    // Position relative to the search container if possible
    const container = input.parentElement;
    if (container) {
      if (getComputedStyle(container).position === 'static') container.style.position = 'relative';
      container.appendChild(clearBtn);
    } else {
      input.parentNode.insertBefore(clearBtn, input.nextSibling);
    }
    return clearBtn;
  }

  function updateClearVisibility() {
    const btn = ensureClearButton();
    btn.style.display = input.value.trim() ? 'block' : 'none';
  }

  input.addEventListener('focus', () => {
    loadIndex(); // warm
    updateClearVisibility();
  });

  input.addEventListener('input', () => {
    debouncedSearch();
    updateClearVisibility();
    if (input.value.trim().length === 0) {
      resultsBox.style.display = 'none';
      input.setAttribute('aria-expanded', 'false');
    }
  });

  input.addEventListener('keydown', function (e) {
    const links = resultsBox.querySelectorAll('.search-result');
    const open = resultsBox.style.display !== 'none' && links.length > 0;

    if (e.key === 'ArrowDown') {
      if (!open) { debouncedSearch(); return; }
      e.preventDefault();
      selectedIndex = Math.min(selectedIndex + 1, links.length - 1);
      selectResult(selectedIndex);
    } else if (e.key === 'ArrowUp') {
      if (!open) return;
      e.preventDefault();
      selectedIndex = Math.max(selectedIndex - 1, 0);
      selectResult(selectedIndex);
    } else if (e.key === 'Enter' && selectedIndex >= 0 && open) {
      e.preventDefault();
      const link = links[selectedIndex];
      if (link) window.location.href = link.getAttribute('href');
    } else if (e.key === 'Escape') {
      if (open) {
        resultsBox.style.display = 'none';
        input.setAttribute('aria-expanded', 'false');
      }
      input.blur();
    }
  });

  // Global '/' focuses the search (standard docs-site pattern, ignore when typing in fields)
  document.addEventListener('keydown', function (e) {
    if (e.key === '/' && document.activeElement === document.body) {
      const activeTag = (document.activeElement && document.activeElement.tagName) || '';
      if (!/INPUT|TEXTAREA|SELECT/.test(activeTag)) {
        e.preventDefault();
        input.focus();
        input.select();
      }
    }
  });

  document.addEventListener('click', function (e) {
    if (!resultsBox.contains(e.target) && e.target !== input) {
      resultsBox.style.display = 'none';
      input.setAttribute('aria-expanded', 'false');
    }
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && resultsBox.style.display !== 'none') {
      resultsBox.style.display = 'none';
      input.setAttribute('aria-expanded', 'false');
      input.blur();
    }
  });

  // Keep aria-expanded in sync
  function closeResults() {
    resultsBox.style.display = 'none';
    input.setAttribute('aria-expanded', 'false');
  }

  // Patch selectResult to manage aria-activedescendant
  const _origSelect = selectResult;
  selectResult = function (index) {
    _origSelect(index);
    const links = resultsBox.querySelectorAll('.search-result');
    const link = links[index];
    if (link) {
      input.setAttribute('aria-activedescendant', link.id || '');
      // ensure it has an id for aria
      if (!link.id) link.id = 'nn-search-opt-' + index;
      input.setAttribute('aria-activedescendant', link.id);
    }
  };

  // Expose for debugging / operator smoke tests
  window.NerraSearch = {
    loadIndex,
    clearCache: () => { cached = null; try { localStorage.removeItem(CACHE_KEY); } catch(_) {} },
    refresh: refreshIndexInBackground
  };
})();
