(function () {
  'use strict';

  var MAX_FILES = 4;

  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function bytesLabel(value) {
    var size = Number(value || 0);
    if (!size) {
      return '0 B';
    }
    if (size < 1024) {
      return size + ' B';
    }
    if (size < 1024 * 1024) {
      return (size / 1024).toFixed(1).replace('.', ',') + ' KB';
    }
    return (size / (1024 * 1024)).toFixed(1).replace('.', ',') + ' MB';
  }

  function fileToPayload(file) {
    return new Promise(function (resolve, reject) {
      var reader = new FileReader();
      reader.onload = function () {
        var result = String(reader.result || '');
        resolve({
          name: file.name || 'documento',
          mime_type: file.type || '',
          size_bytes: file.size || 0,
          content_base64: result,
        });
      };
      reader.onerror = function () {
        reject(new Error('Lettura del file non riuscita.'));
      };
      reader.readAsDataURL(file);
    });
  }

  function buildPromptBlock(attachments) {
    var items = Array.isArray(attachments) ? attachments.filter(function (item) {
      return item && item.text_excerpt;
    }) : [];
    if (!items.length) {
      return '';
    }

    var lines = [
      '',
      "═══ DOCUMENTI CARICATI DALL'UTENTE ═══",
      'Usa i documenti caricati come contesto operativo aggiuntivo.',
    ];

    items.forEach(function (item, index) {
      var meta = [
        'Documento ' + (index + 1) + ': ' + (item.name || 'Documento'),
        'tipo ' + (item.mime_type || 'n.d.'),
      ];
      if (item.page_count) {
        meta.push('pagine ' + item.page_count);
      }
      lines.push('[' + meta.join(' · ') + ']');
      lines.push(String(item.text_excerpt || '').trim());
      if (item.truncated) {
        lines.push('(Estratto abbreviato per mantenere la risposta rapida.)');
      }
      lines.push('');
    });

    lines.push('═══ FINE DOCUMENTI CARICATI ═══');
    return lines.join('\n').trim();
  }

  function renderAttachmentShelf(container, attachments) {
    if (!container) {
      return;
    }
    var items = Array.isArray(attachments) ? attachments : [];
    container.hidden = items.length === 0;
    if (!items.length) {
      container.innerHTML = '';
      return;
    }
    container.innerHTML = items.map(function (item) {
      return (
        '<div class="pct-ai-attachment">' +
          '<div class="pct-ai-attachment__meta">' +
            '<div class="pct-ai-attachment__title"><i class="bi bi-file-earmark-text"></i><span>' + escapeHtml(item.name) + '</span></div>' +
            '<div class="pct-ai-attachment__detail">' + escapeHtml(item.mime_type || 'documento') + ' · ' + escapeHtml(bytesLabel(item.size_bytes)) + '</div>' +
          '</div>' +
          '<button class="pct-ai-attachment__remove" type="button" data-attachment-id="' + escapeHtml(item.id) + '" title="Rimuovi documento" aria-label="Rimuovi documento">' +
            '<i class="bi bi-x-lg"></i>' +
          '</button>' +
        '</div>'
      );
    }).join('');
  }

  function bindShelfRemoval(container, onRemove) {
    if (!container) {
      return;
    }
    container.addEventListener('click', function (event) {
      var button = event.target.closest('[data-attachment-id]');
      if (!button || typeof onRemove !== 'function') {
        return;
      }
      onRemove(String(button.getAttribute('data-attachment-id') || ''));
    });
  }

  async function parseAttachments(options) {
    var files = Array.prototype.slice.call((options && options.files) || []).slice(0, MAX_FILES);
    if (!files.length) {
      return { attachments: [], errors: [] };
    }

    var payloadFiles = await Promise.all(files.map(fileToPayload));
    if (options && options.remoteHosted) {
      return (options.bridge && options.bridge.parseCompanionAttachments)
        ? options.bridge.parseCompanionAttachments(options.config, { files: payloadFiles })
        : Promise.reject(new Error('Bridge documentale del companion non disponibile.'));
    }
    return (options.bridge && options.bridge.parseServerAttachments)
      ? options.bridge.parseServerAttachments(options.config, { files: payloadFiles })
      : Promise.reject(new Error('Parser documentale del server non disponibile.'));
  }

  function buildDownloadBlob(options) {
    var timestamp = new Date();
    var rows = [
      '# Conversazione Lex',
      '',
      'Generato il: ' + timestamp.toLocaleString('it-IT'),
    ];
    if (options && options.contextLabel) {
      rows.push('Contesto: ' + options.contextLabel);
    }
    rows.push('');

    var attachments = Array.isArray(options && options.attachments) ? options.attachments : [];
    if (attachments.length) {
      rows.push('## Documenti allegati');
      attachments.forEach(function (item) {
        rows.push('- ' + (item.name || 'Documento') + ' (' + (item.mime_type || 'documento') + ')');
      });
      rows.push('');
    }

    var history = Array.isArray(options && options.history) ? options.history : [];
    rows.push('## Conversazione');
    history.forEach(function (item) {
      var role = item && item.role === 'user' ? 'Utente' : 'Lex';
      rows.push('### ' + role);
      rows.push(String((item && item.content) || '').trim());
      rows.push('');
    });

    var blob = new Blob([rows.join('\n')], { type: 'text/markdown;charset=utf-8' });
    var fileName = 'lex-conversazione-' +
      timestamp.toLocaleDateString('it-IT').replace(/\//g, '-') + '-' +
      timestamp.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' }).replace(':', '-') +
      '.md';
    return { blob: blob, fileName: fileName };
  }

  function triggerDownload(options) {
    var payload = buildDownloadBlob(options || {});
    var url = window.URL.createObjectURL(payload.blob);
    var link = document.createElement('a');
    link.href = url;
    link.download = payload.fileName;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(function () {
      window.URL.revokeObjectURL(url);
    }, 1000);
  }

  window.PctLexDocuments = {
    bindShelfRemoval: bindShelfRemoval,
    buildPromptBlock: buildPromptBlock,
    parseAttachments: parseAttachments,
    renderAttachmentShelf: renderAttachmentShelf,
    triggerDownload: triggerDownload,
  };
})();
