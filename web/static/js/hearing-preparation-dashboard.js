(function () {
  const root = document.querySelector("[data-hearing-preparation]");
  if (!root) {
    return;
  }

  const cards = Array.from(root.querySelectorAll("[data-hearing-case-card]"));
  const searchInput = root.querySelector('[data-hearing-filter="search"]');
  const filterMateria = root.querySelector('[data-hearing-filter="materia"]');
  const filterUfficio = root.querySelector('[data-hearing-filter="ufficio"]');
  const filterCliente = root.querySelector('[data-hearing-filter="cliente"]');
  const filterStato = root.querySelector('[data-hearing-filter="stato"]');
  const filterUdienza = root.querySelector('[data-hearing-filter="udienza"]');
  const countNode = root.querySelector("[data-hearing-visible-count]");
  const emptyNode = root.querySelector("[data-hearing-empty]");
  const resetButton = root.querySelector("[data-hearing-reset-filters]");
  const focusButton = root.querySelector("[data-hearing-focus-search]");

  function normalize(value) {
    return String(value || "").trim().toLowerCase();
  }

  function matchesFilter(card) {
    const dataset = card.dataset;
    const query = normalize(searchInput && searchInput.value);

    if (query && !normalize(dataset.search).includes(query)) {
      return false;
    }
    if (filterMateria && filterMateria.value && normalize(dataset.materia) !== normalize(filterMateria.value)) {
      return false;
    }
    if (filterUfficio && filterUfficio.value && normalize(dataset.ufficio) !== normalize(filterUfficio.value)) {
      return false;
    }
    if (filterCliente && filterCliente.value && normalize(dataset.cliente) !== normalize(filterCliente.value)) {
      return false;
    }
    if (filterStato && filterStato.value && normalize(dataset.stato) !== normalize(filterStato.value)) {
      return false;
    }
    if (filterUdienza && filterUdienza.value) {
      const wanted = filterUdienza.value === "true";
      const isImminente = dataset.udienzaImminente === "true";
      if (wanted !== isImminente) {
        return false;
      }
    }
    return true;
  }

  function updateVisibleCount(count) {
    if (countNode) {
      countNode.textContent = count === 1 ? "1 fascicolo visualizzato" : count + " fascicoli visualizzati";
    }
    if (emptyNode) {
      emptyNode.classList.toggle("d-none", count !== 0);
    }
  }

  function applyFilters() {
    let visible = 0;
    cards.forEach(function (card) {
      const show = matchesFilter(card);
      card.hidden = !show;
      card.classList.toggle("d-none", !show);
      if (show) {
        visible += 1;
      }
    });
    updateVisibleCount(visible);
  }

  function resetFilters() {
    [searchInput, filterMateria, filterUfficio, filterCliente, filterStato, filterUdienza].forEach(function (field) {
      if (!field) {
        return;
      }
      field.value = "";
    });
    applyFilters();
  }

  [searchInput, filterMateria, filterUfficio, filterCliente, filterStato, filterUdienza].forEach(function (field) {
    if (!field) {
      return;
    }
    field.addEventListener("input", applyFilters);
    field.addEventListener("change", applyFilters);
  });

  if (resetButton) {
    resetButton.addEventListener("click", resetFilters);
  }

  if (focusButton && searchInput) {
    focusButton.addEventListener("click", function () {
      const searchSection = document.getElementById("hearing-preparation-search");
      if (searchSection) {
        searchSection.scrollIntoView({ behavior: "smooth", block: "start" });
      }
      window.setTimeout(function () {
        searchInput.focus();
      }, 220);
    });
  }

  applyFilters();
})();
