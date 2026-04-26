(function () {
  const root = document.querySelector("[data-site-builder]");
  if (!root) return;

  const frameWrap = root.querySelector("[data-preview-frame]");
  const frame = frameWrap ? frameWrap.querySelector("iframe") : null;
  const sizeButtons = root.querySelectorAll("[data-preview-size]");
  const bodyField = root.querySelector("[data-blocks-json-field]");
  const blockList = root.querySelector("[data-block-editor-list]");
  const properties = root.querySelector("[data-block-properties]");
  const emptyState = root.querySelector("[data-builder-empty]");
  const statusBox = root.querySelector("[data-builder-status]");
  const blockCount = root.querySelector("[data-block-count]");
  const addButtons = root.querySelectorAll("[data-block-preset]");
  const assetForm = root.querySelector("[data-asset-upload-form]");
  const assetList = root.querySelector("[data-asset-list]");
  let selectedIndex = -1;
  let blocks = parseBlocks();

  sizeButtons.forEach((button) => {
    button.addEventListener("click", () => {
      sizeButtons.forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      frameWrap.classList.remove("is-desktop", "is-tablet", "is-mobile");
      frameWrap.classList.add(`is-${button.dataset.previewSize || "desktop"}`);
    });
  });

  root.querySelectorAll("[data-builder-action]").forEach((button) => {
    button.addEventListener("click", async () => {
      const action = button.dataset.builderAction;
      if (action === "save") await saveBlocks(root.dataset.saveUrl, "Bozza salvata.");
      if (action === "publish") await saveBlocks(root.dataset.publishUrl, "Modifiche pubblicate.");
      if (action === "refresh-preview") refreshPreview();
    });
  });

  root.querySelectorAll("[data-restore-revision]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const response = await fetch(form.action, { method: "POST", headers: { Accept: "application/json" } });
      const result = await response.json();
      showStatus(result.message || "Revisione ripristinata.", result.ok ? "success" : "danger");
      if (result.ok) window.location.reload();
    });
  });

  addButtons.forEach((button) => {
    button.addEventListener("click", () => {
      try {
        blocks.push(JSON.parse(button.dataset.blockPreset || "{}"));
      } catch (_error) {
        blocks.push({ type: "rich_text", title: "Nuova sezione", text: "" });
      }
      selectedIndex = blocks.length - 1;
      writeBlocks();
      render();
      showStatus("Blocco aggiunto alla pagina selezionata.", "success");
    });
  });

  if (assetForm) {
    assetForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const formData = new FormData(assetForm);
      const response = await fetch("/sito-studio/api/assets/upload", {
        method: "POST",
        body: formData,
        headers: { Accept: "application/json" },
      });
      const result = await response.json();
      if (!result.ok) {
        showStatus(result.error || "Caricamento immagine non riuscito.", "danger");
        return;
      }
      appendAssetButton(result.asset);
      assetForm.reset();
      showStatus(result.message || "Immagine caricata.", "success");
    });
  }

  if (assetList) {
    assetList.addEventListener("click", (event) => {
      const button = event.target.closest("[data-asset-url]");
      if (!button || selectedIndex < 0 || !blocks[selectedIndex]) return;
      blocks[selectedIndex].image_url = button.dataset.assetUrl || "";
      blocks[selectedIndex].image_alt = button.dataset.assetAlt || "";
      writeBlocks();
      render();
      showStatus("Immagine collegata al blocco selezionato.", "success");
    });
  }

  function parseBlocks() {
    if (!bodyField) return [];
    try {
      const parsed = JSON.parse(bodyField.value || "[]");
      return Array.isArray(parsed) ? parsed : [];
    } catch (_error) {
      return [];
    }
  }

  function writeBlocks() {
    if (bodyField) bodyField.value = JSON.stringify(blocks, null, 2);
    if (blockCount) blockCount.textContent = String(blocks.length);
  }

  function render() {
    if (!blockList) return;
    blockList.innerHTML = "";
    if (emptyState) emptyState.hidden = blocks.length > 0;
    blocks.forEach((block, index) => {
      const row = document.createElement("article");
      row.className = `studio-block-editor-row${index === selectedIndex ? " is-selected" : ""}`;
      row.innerHTML = `
        <button class="studio-block-select" type="button" data-action="select">
          <span>
            <strong>${escapeHtml(block.title || block.type || "Blocco")}</strong>
            <small>${escapeHtml(block.type || "")}</small>
          </span>
          <span class="badge text-bg-light">${index + 1}</span>
        </button>
        <div class="studio-block-editor-actions">
          <button class="btn btn-sm btn-outline-secondary" type="button" data-action="up">Su</button>
          <button class="btn btn-sm btn-outline-secondary" type="button" data-action="down">Giu</button>
          <button class="btn btn-sm btn-outline-primary" type="button" data-action="duplicate">Duplica</button>
          <button class="btn btn-sm btn-outline-danger" type="button" data-action="delete">Elimina</button>
        </div>
      `;
      row.querySelectorAll("[data-action]").forEach((button) => {
        button.addEventListener("click", () => handleRowAction(button.dataset.action, index));
      });
      blockList.appendChild(row);
    });
    renderProperties();
    writeBlocks();
  }

  function handleRowAction(action, index) {
    if (action === "select") selectedIndex = index;
    if (action === "delete") {
      blocks.splice(index, 1);
      selectedIndex = Math.min(blocks.length - 1, index);
    }
    if (action === "duplicate") {
      blocks.splice(index + 1, 0, JSON.parse(JSON.stringify(blocks[index])));
      selectedIndex = index + 1;
    }
    if (action === "up" && index > 0) {
      [blocks[index - 1], blocks[index]] = [blocks[index], blocks[index - 1]];
      selectedIndex = index - 1;
    }
    if (action === "down" && index < blocks.length - 1) {
      [blocks[index + 1], blocks[index]] = [blocks[index], blocks[index + 1]];
      selectedIndex = index + 1;
    }
    render();
  }

  function renderProperties() {
    if (!properties) return;
    const block = selectedIndex >= 0 ? blocks[selectedIndex] : null;
    if (!block) {
      properties.innerHTML = '<div class="text-muted">Nessun blocco selezionato.</div>';
      return;
    }
    properties.innerHTML = `
      <div class="studio-block-properties-grid">
        ${inputField("type", "Tipo blocco", block.type || "", true)}
        ${inputField("title", "Titolo", block.title || "")}
        ${inputField("subtitle", "Sottotitolo", block.subtitle || "")}
        ${textareaField("text", "Testo", block.text || "")}
        ${inputField("image_url", "URL immagine", block.image_url || "")}
        ${inputField("image_alt", "Testo alternativo", block.image_alt || "")}
        ${inputField("button_text", "Testo pulsante", block.button_text || "")}
        ${inputField("button_url", "URL pulsante", block.button_url || "")}
        ${selectField("background", "Sfondo", block.background || "default", ["default", "muted", "dark", "accent"])}
        ${selectField("spacing", "Spaziatura", block.spacing || "standard", ["compact", "standard", "wide"])}
        ${selectField("alignment", "Allineamento", block.alignment || "start", ["start", "center", "end"])}
        ${selectField("animation", "Animazione", block.animation || "fade-up", ["fade-up", "soft-reveal", "none"])}
        ${inputField("style_variant", "Variante stile", block.style_variant || "default")}
      </div>
      <div class="studio-block-visibility mt-3">
        <strong>Visibilit&agrave;</strong>
        ${visibilityCheck("desktop", "Desktop", block)}
        ${visibilityCheck("tablet", "Tablet", block)}
        ${visibilityCheck("mobile", "Mobile", block)}
      </div>
      <div class="studio-block-items mt-3">
        <div class="d-flex justify-content-between align-items-center gap-2 mb-2">
          <strong>Elementi interni</strong>
          <button class="btn btn-sm btn-outline-primary" type="button" data-item-action="add">Aggiungi elemento</button>
        </div>
        <div data-items-list></div>
      </div>
    `;
    properties.querySelectorAll("[data-prop]").forEach((field) => {
      field.addEventListener("input", () => {
        blocks[selectedIndex][field.dataset.prop] = field.type === "checkbox" ? field.checked : field.value;
        if (field.dataset.visibility) {
          blocks[selectedIndex].visibility = blocks[selectedIndex].visibility || {};
          blocks[selectedIndex].visibility[field.dataset.visibility] = field.checked;
        }
        writeBlocks();
      });
    });
    const addItem = properties.querySelector("[data-item-action='add']");
    if (addItem) addItem.addEventListener("click", () => addBlockItem());
    renderItems();
  }

  function renderItems() {
    const list = properties ? properties.querySelector("[data-items-list]") : null;
    const block = selectedIndex >= 0 ? blocks[selectedIndex] : null;
    if (!list || !block) return;
    const items = Array.isArray(block.items) ? block.items : [];
    list.innerHTML = "";
    items.forEach((item, itemIndex) => {
      const box = document.createElement("div");
      box.className = "studio-block-item-editor";
      box.innerHTML = `
        ${inputField(`item-title-${itemIndex}`, "Titolo elemento", item.title || "")}
        ${textareaField(`item-text-${itemIndex}`, "Testo elemento", item.text || "")}
        ${inputField(`item-image-${itemIndex}`, "URL immagine", item.image_url || "")}
        ${inputField(`item-alt-${itemIndex}`, "Alt immagine", item.image_alt || "")}
        ${inputField(`item-button-${itemIndex}`, "Testo pulsante", item.button_text || "")}
        ${inputField(`item-url-${itemIndex}`, "URL pulsante", item.button_url || "")}
        <div class="d-flex flex-wrap gap-2">
          <button class="btn btn-sm btn-outline-secondary" type="button" data-item-action="up">Su</button>
          <button class="btn btn-sm btn-outline-secondary" type="button" data-item-action="down">Giu</button>
          <button class="btn btn-sm btn-outline-primary" type="button" data-item-action="duplicate">Duplica</button>
          <button class="btn btn-sm btn-outline-danger" type="button" data-item-action="delete">Elimina</button>
        </div>
      `;
      bindItemFields(box, itemIndex);
      list.appendChild(box);
    });
    if (!items.length) {
      list.innerHTML = '<div class="text-muted small">Questo blocco non ha elementi interni.</div>';
    }
  }

  function bindItemFields(box, itemIndex) {
    const map = [
      ["item-title", "title"],
      ["item-text", "text"],
      ["item-image", "image_url"],
      ["item-alt", "image_alt"],
      ["item-button", "button_text"],
      ["item-url", "button_url"],
    ];
    map.forEach(([prefix, key]) => {
      const field = box.querySelector(`[data-prop="${prefix}-${itemIndex}"]`);
      if (!field) return;
      field.addEventListener("input", () => {
        blocks[selectedIndex].items[itemIndex][key] = field.value;
        writeBlocks();
      });
    });
    box.querySelectorAll("[data-item-action]").forEach((button) => {
      button.addEventListener("click", () => handleItemAction(button.dataset.itemAction, itemIndex));
    });
  }

  function addBlockItem() {
    const block = blocks[selectedIndex];
    block.items = Array.isArray(block.items) ? block.items : [];
    block.items.push({ title: "Nuovo elemento", text: "", image_url: "", image_alt: "" });
    writeBlocks();
    renderProperties();
  }

  function handleItemAction(action, itemIndex) {
    const items = blocks[selectedIndex].items || [];
    if (action === "delete") items.splice(itemIndex, 1);
    if (action === "duplicate") items.splice(itemIndex + 1, 0, JSON.parse(JSON.stringify(items[itemIndex])));
    if (action === "up" && itemIndex > 0) [items[itemIndex - 1], items[itemIndex]] = [items[itemIndex], items[itemIndex - 1]];
    if (action === "down" && itemIndex < items.length - 1) [items[itemIndex + 1], items[itemIndex]] = [items[itemIndex], items[itemIndex + 1]];
    writeBlocks();
    renderProperties();
  }

  async function saveBlocks(url, fallbackMessage) {
    if (!url || url.endsWith("/0/blocks") || url.endsWith("/0/publish")) {
      showStatus("Seleziona una pagina valida prima di salvare.", "danger");
      return;
    }
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ blocks }),
    });
    const result = await response.json();
    showStatus(result.message || result.error || fallbackMessage, result.ok ? "success" : "danger");
    if (result.ok) refreshPreview();
  }

  function refreshPreview() {
    if (!frame) return;
    const base = root.dataset.previewUrl || frame.src;
    const joiner = base.includes("?") ? "&" : "?";
    frame.src = `${base}${joiner}_=${Date.now()}`;
  }

  function appendAssetButton(asset) {
    if (!assetList || !asset) return;
    const button = document.createElement("button");
    button.className = "studio-asset-item";
    button.type = "button";
    button.dataset.assetUrl = asset.url || "";
    button.dataset.assetAlt = asset.alt_text || "";
    button.innerHTML = `<span>${escapeHtml(asset.title || asset.original_filename || "Immagine")}</span><small>${escapeHtml(asset.alt_text || "")}</small>`;
    assetList.prepend(button);
  }

  function inputField(name, label, value, readonly) {
    return `<label class="form-label">${label}<input class="form-control form-control-sm" data-prop="${name}" value="${escapeAttr(value)}" ${readonly ? "readonly" : ""}></label>`;
  }

  function textareaField(name, label, value) {
    return `<label class="form-label">${label}<textarea class="form-control form-control-sm" rows="3" data-prop="${name}">${escapeHtml(value)}</textarea></label>`;
  }

  function selectField(name, label, value, options) {
    return `<label class="form-label">${label}<select class="form-select form-select-sm" data-prop="${name}">${options.map((option) => `<option value="${escapeAttr(option)}" ${option === value ? "selected" : ""}>${escapeHtml(option)}</option>`).join("")}</select></label>`;
  }

  function visibilityCheck(name, label, block) {
    const visible = !block.visibility || block.visibility[name] !== false;
    return `<label class="form-check"><input class="form-check-input" type="checkbox" data-prop="visibility_${name}" data-visibility="${name}" ${visible ? "checked" : ""}> ${label}</label>`;
  }

  function showStatus(message, tone) {
    if (!statusBox) return;
    statusBox.textContent = message || "";
    statusBox.className = `studio-builder-status is-${tone || "info"}`;
    window.clearTimeout(showStatus.timer);
    showStatus.timer = window.setTimeout(() => {
      statusBox.textContent = "";
      statusBox.className = "studio-builder-status";
    }, 4200);
  }

  function escapeAttr(value) {
    return String(value || "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
  }

  function escapeHtml(value) {
    return String(value || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  render();
})();
