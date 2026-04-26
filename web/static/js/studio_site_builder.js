(function () {
  const frame = document.querySelector("[data-preview-frame]");
  const sizeButtons = document.querySelectorAll("[data-preview-size]");
  if (frame && sizeButtons.length) {
    sizeButtons.forEach((button) => {
      button.addEventListener("click", () => {
        sizeButtons.forEach((item) => item.classList.remove("active"));
        button.classList.add("active");
        frame.classList.remove("is-desktop", "is-tablet", "is-mobile");
        frame.classList.add(`is-${button.dataset.previewSize || "desktop"}`);
      });
    });
  }

  const bodyField = document.querySelector("[data-blocks-json-field]");
  const blockList = document.querySelector("[data-block-editor-list]");
  const addButtons = document.querySelectorAll("[data-block-preset]");

  if (!bodyField || !blockList) {
    return;
  }

  const parseBlocks = () => {
    try {
      const parsed = JSON.parse(bodyField.value || "[]");
      return Array.isArray(parsed) ? parsed : [];
    } catch (_error) {
      return [];
    }
  };

  let blocks = parseBlocks();

  const writeBlocks = () => {
    bodyField.value = JSON.stringify(blocks, null, 2);
  };

  const render = () => {
    blockList.innerHTML = "";
    blocks.forEach((block, index) => {
      const row = document.createElement("article");
      row.className = "studio-block-editor-row";
      row.innerHTML = `
        <div class="studio-block-editor-row__head">
          <strong>${block.title || block.type || "Blocco"}</strong>
          <span>${block.type || ""}</span>
        </div>
        <label>Titolo <input class="form-control form-control-sm" data-field="title" value="${escapeAttr(block.title || "")}"></label>
        <label>Testo <textarea class="form-control form-control-sm" rows="3" data-field="text">${escapeText(block.text || "")}</textarea></label>
        <label>CTA <input class="form-control form-control-sm" data-field="button_text" value="${escapeAttr(block.button_text || "")}"></label>
        <div class="d-flex flex-wrap gap-2">
          <button class="btn btn-sm btn-outline-secondary" type="button" data-action="up">Sposta su</button>
          <button class="btn btn-sm btn-outline-secondary" type="button" data-action="down">Sposta giu</button>
          <button class="btn btn-sm btn-outline-primary" type="button" data-action="duplicate">Duplica</button>
          <button class="btn btn-sm btn-outline-danger" type="button" data-action="delete">Elimina</button>
        </div>
      `;
      row.querySelectorAll("[data-field]").forEach((field) => {
        field.addEventListener("input", () => {
          blocks[index][field.dataset.field] = field.value;
          writeBlocks();
        });
      });
      row.querySelectorAll("[data-action]").forEach((button) => {
        button.addEventListener("click", () => {
          const action = button.dataset.action;
          if (action === "delete") blocks.splice(index, 1);
          if (action === "duplicate") blocks.splice(index + 1, 0, { ...blocks[index] });
          if (action === "up" && index > 0) [blocks[index - 1], blocks[index]] = [blocks[index], blocks[index - 1]];
          if (action === "down" && index < blocks.length - 1) [blocks[index + 1], blocks[index]] = [blocks[index], blocks[index + 1]];
          writeBlocks();
          render();
        });
      });
      blockList.appendChild(row);
    });
    writeBlocks();
  };

  addButtons.forEach((button) => {
    button.addEventListener("click", () => {
      try {
        blocks.push(JSON.parse(button.dataset.blockPreset || "{}"));
      } catch (_error) {
        blocks.push({ type: "rich_text", title: "Nuova sezione", text: "" });
      }
      render();
    });
  });

  function escapeAttr(value) {
    return String(value).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
  }

  function escapeText(value) {
    return String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;");
  }

  render();
})();
