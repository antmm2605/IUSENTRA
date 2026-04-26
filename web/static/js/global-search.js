(function () {
  const page = document.querySelector('[data-global-search-page]');
  if (!page) return;

  const input = page.querySelector('[data-global-search-input]');
  const form = page.querySelector('[data-global-search-form]');
  const resultsBox = page.querySelector('[data-global-search-results]');
  const countBox = page.querySelector('[data-global-search-count]');
  const filters = page.querySelector('[data-global-search-filters]');
  const reindexButton = page.querySelector('[data-global-search-reindex]');
  let activeType = new URLSearchParams(window.location.search).get('type') || 'tutto';
  let selectedIndex = -1;
  let timer = null;

  function escapeHtml(value) {
    return String(value || '').replace(/[&<>"']/g, function (char) {
      return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char];
    });
  }

  function skeleton() {
    resultsBox.innerHTML = Array.from({length: 4}).map(function () {
      return '<div class="global-search-skeleton"><span></span><div><b></b><p></p><p></p></div></div>';
    }).join('');
  }

  function resultCard(item) {
    const badges = (item.badges || []).map(function (badge) {
      return '<span>' + escapeHtml(badge) + '</span>';
    }).join('');
    const actions = (item.actions || [{label: 'Apri', url: item.source_url || item.url || '#'}]).map(function (action, index) {
      return '<a class="btn btn-sm ' + (index === 0 ? 'btn-primary' : 'btn-outline-primary') + '" href="' + escapeHtml(action.url || '#') + '">' + escapeHtml(action.label || 'Apri') + '</a>';
    }).join('');
    return '<article class="global-search-result" tabindex="0" data-result-url="' + escapeHtml(item.source_url || item.url || '#') + '">' +
      '<div class="global-search-result-icon"><i class="bi ' + escapeHtml(item.icon || item.icona || 'bi-search') + '"></i></div>' +
      '<div class="global-search-result-body">' +
      '<div class="global-search-result-head"><div><h2>' + escapeHtml(item.title || item.titolo) + '</h2><p>' + escapeHtml(item.subtitle || item.sottotitolo || '') + '</p></div>' +
      (item.date ? '<time>' + escapeHtml(item.date) + '</time>' : '') + '</div>' +
      (item.snippet ? '<div class="global-search-snippet">' + item.snippet + '</div>' : '') +
      '<div class="global-search-badges">' + badges + '</div>' +
      '<div class="global-search-actions">' + actions + '</div>' +
      '</div></article>';
  }

  function emptyState(query) {
    return '<div class="global-search-empty"><i class="bi bi-search-heart"></i>' +
      '<h2>' + (query ? 'Nessun risultato trovato' : 'Inizia da una parola chiave') + '</h2>' +
      '<p>' + (query ? 'Prova con RG, codice fiscale, nome cliente, controparte, numero fattura o parola contenuta nei documenti.' : 'Cerca in fascicoli, clienti, documenti, scadenze, agenda, economia e comunicazioni.') + '</p>' +
      '</div>';
  }

  function render(payload) {
    const results = payload.results || [];
    if (countBox) countBox.textContent = String(payload.total || results.length || 0);
    if (!results.length) {
      resultsBox.innerHTML = emptyState(input.value.trim());
    } else {
      resultsBox.innerHTML = results.map(resultCard).join('');
    }
    selectedIndex = -1;
  }

  function searchNow() {
    const query = input.value.trim();
    const url = new URL('/api/global-search', window.location.origin);
    url.searchParams.set('q', query);
    url.searchParams.set('limit', '30');
    if (activeType && activeType !== 'tutto') url.searchParams.set('type', activeType);
    if (!query) {
      render({results: [], total: 0});
      return;
    }
    skeleton();
    fetch(url.toString(), {headers: {'Accept': 'application/json'}})
      .then(function (response) { return response.json(); })
      .then(render)
      .catch(function () { resultsBox.innerHTML = emptyState(query); });
  }

  function debouncedSearch() {
    window.clearTimeout(timer);
    timer = window.setTimeout(searchNow, 250);
  }

  function setSelected(index) {
    const cards = Array.from(resultsBox.querySelectorAll('.global-search-result'));
    cards.forEach(function (card) { card.classList.remove('is-selected'); });
    if (!cards.length) return;
    selectedIndex = Math.max(0, Math.min(index, cards.length - 1));
    cards[selectedIndex].classList.add('is-selected');
    cards[selectedIndex].scrollIntoView({block: 'nearest'});
  }

  input.addEventListener('input', debouncedSearch);
  form.addEventListener('submit', function (event) {
    event.preventDefault();
    searchNow();
  });

  if (filters) {
    filters.addEventListener('click', function (event) {
      const chip = event.target.closest('[data-type]');
      if (!chip) return;
      event.preventDefault();
      activeType = chip.dataset.type || 'tutto';
      filters.querySelectorAll('.global-search-chip').forEach(function (item) { item.classList.remove('is-active'); });
      chip.classList.add('is-active');
      searchNow();
    });
  }

  resultsBox.addEventListener('click', function (event) {
    const action = event.target.closest('a,button');
    if (action) return;
    const card = event.target.closest('.global-search-result');
    if (card && card.dataset.resultUrl) window.location.href = card.dataset.resultUrl;
  });

  document.addEventListener('keydown', function (event) {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      input.focus();
      input.select();
      return;
    }
    if (document.activeElement !== input && !page.contains(document.activeElement)) return;
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setSelected(selectedIndex + 1);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setSelected(selectedIndex - 1);
    } else if (event.key === 'Enter' && selectedIndex >= 0) {
      const card = resultsBox.querySelectorAll('.global-search-result')[selectedIndex];
      if (card && card.dataset.resultUrl) window.location.href = card.dataset.resultUrl;
    }
  });

  if (reindexButton) {
    reindexButton.addEventListener('click', function () {
      reindexButton.disabled = true;
      reindexButton.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Reindicizzo';
      fetch('/api/global-search/reindex', {method: 'POST', headers: {'Accept': 'application/json'}})
        .then(function (response) { return response.json(); })
        .then(function () { searchNow(); })
        .finally(function () {
          reindexButton.disabled = false;
          reindexButton.innerHTML = '<i class="bi bi-arrow-repeat"></i> Reindicizza';
        });
    });
  }
})();
