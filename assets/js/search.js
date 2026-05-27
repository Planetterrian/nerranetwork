/**
 * Global site search powered by the static Content Lake index.
 *
 * Improvements for robustness and UX:
 * - Debounced input
 * - Loading state while fetching index
 * - Clear error/empty states
 * - Keyboard navigation (arrows + enter)
 * - Simple match highlighting
 * - Result count indicator
 * - Graceful handling when index is missing or empty
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
    const s = norm(it.show_name || it.show_slug);
    const ents = (it.entities || []).join(' ').toLowerCase();
    const topics = (it.topics || []).join(' ').toLowerCase();

    let score = 0;

    // Stronger title matching
    if (t === q) score += 200;
    else if (t.startsWith(q)) score += 120;
    else if (t.includes(q)) score += 80;

    if (h.includes(q)) score += 35;
    if (ents.includes(q)) score += 25;
    if (topics.includes(q)) score += 20;
    if (s.includes(q)) score += 10;

    // Recency boost
    if (it.date) {
      const y = parseInt(it.date.slice(0, 4), 10) || 2020;
      score += Math.max(0, (y - 2022) * 1.5);
    }

    return score;
  }

  function highlight(text, query) {
    if (!text || !query) return text || '';
    const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const regex = new RegExp(`(${escaped})`, 'gi');
    return text.replace(regex, '<mark>$1</mark>');
  }

  async function loadIndex() {
    if (cached) return cached;
    if (isLoading) return null;

    isLoading = true;
    showLoading();

    try {
      const res = await fetch(INDEX_URL, { credentials: 'same-origin' });
      if (res.ok) {
        const data = await res.json();
        cached = { episodes: data.episodes || [] };
        hideLoading();
        isLoading = false;
        return cached;
      }
    } catch (e) {
      // fall through to legacy
    }

    // Legacy fallback
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
              topics: e.topics || []
            });
          }
        } catch (_) {}
      }
      cached = { episodes: items };
      hideLoading();
      isLoading = false;
      return cached;
    } catch (e) {
      hideLoading();
      isLoading = false;
      showError("Search is temporarily unavailable. Please try again later.");
      return { episodes: [] };
    }
  }

  function showLoading() {
    resultsBox.innerHTML = '<div style="padding:8px 12px;color:var(--nn-text-muted);">Loading search index...</div>';
    resultsBox.style.display = 'block';
  }

  function hideLoading() {
    // Will be overwritten by renderResults
  }

  function showError(msg) {
    resultsBox.innerHTML = `<div style="padding:8px 12px;color:#ef4444;">${msg}</div>`;
    resultsBox.style.display = 'block';
  }

  function renderResults(matches, query) {
    selectedIndex = -1;

    if (!matches.length) {
      resultsBox.innerHTML = `
        <div style="padding:8px 12px;color:var(--nn-text-muted);">
          No matches found.
          <br><small>The search index is refreshed after every episode and nightly.</small>
        </div>`;
    } else {
      const total = matches.length;
      const shown = Math.min(12, total);

      let html = matches.slice(0, shown).map((m, i) => {
        const label = highlight((m.title || m.hook || '').substring(0, 85), query);
        const meta = [
          m.show_name || m.show_slug || '',
          m.date || ''
        ].filter(Boolean).join(' · ');

        const entities = (m.entities || []).slice(0, 2).join(', ');
        const fullMeta = meta + (entities ? ` · ${entities}` : '');

        return `
          <a href="${m.url || '#'}" 
             class="search-result" 
             data-index="${i}"
             style="display:block;padding:8px 12px;text-decoration:none;color:inherit;border-bottom:1px solid var(--nn-border);">
            <div><strong>${label}</strong></div>
            <small style="opacity:0.7">${fullMeta}</small>
          </a>`;
      }).join('');

      if (total > shown) {
        html += `<div style="padding:6px 12px;font-size:0.75rem;color:var(--nn-text-muted);background:var(--nn-bg);">
          Showing ${shown} of ${total} results
        </div>`;
      }

      resultsBox.innerHTML = html;
    }

    resultsBox.style.display = 'block';

    // Add hover/selection styles for keyboard nav
    const links = resultsBox.querySelectorAll('.search-result');
    links.forEach(link => {
      link.addEventListener('mouseenter', () => {
        links.forEach(l => l.style.background = '');
        link.style.background = 'var(--nn-surface)';
        selectedIndex = parseInt(link.dataset.index);
      });
    });
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

  function debounce(fn, delay) {
    let timeout;
    return function (...args) {
      clearTimeout(timeout);
      timeout = setTimeout(() => fn.apply(this, args), delay);
    };
  }

  // Event listeners
  input.addEventListener('focus', () => {
    loadIndex(); // warm the cache
  });

  input.addEventListener('input', debouncedSearch);

  input.addEventListener('keydown', function (e) {
    const links = resultsBox.querySelectorAll('.search-result');
    if (!links.length || resultsBox.style.display === 'none') return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      selectedIndex = Math.min(selectedIndex + 1, links.length - 1);
      selectResult(selectedIndex);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      selectedIndex = Math.max(selectedIndex - 1, 0);
      selectResult(selectedIndex);
    } else if (e.key === 'Enter' && selectedIndex >= 0) {
      e.preventDefault();
      const link = links[selectedIndex];
      if (link) window.location.href = link.getAttribute('href');
    }
  });

  document.addEventListener('click', function (e) {
    if (!resultsBox.contains(e.target) && e.target !== input) {
      resultsBox.style.display = 'none';
    }
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && resultsBox.style.display !== 'none') {
      resultsBox.style.display = 'none';
      input.blur();
    }
  });

  // Expose for debugging if needed
  window.NerraSearch = { loadIndex, clearCache: () => { cached = null; } };
})();
