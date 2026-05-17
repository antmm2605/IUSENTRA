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
        resolve({
          name: file.name || 'documento',
          mime_type: file.type || '',
          size_bytes: file.size || 0,
          content_base64: String(reader.result || ''),
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
      "=== DOCUMENTI CARICATI DALL'UTENTE ===",
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
      lines.push('[' + meta.join(' - ') + ']');
      lines.push(String(item.text_excerpt || '').trim());
      if (item.truncated) {
        lines.push('(Estratto abbreviato per mantenere la risposta rapida.)');
      }
      lines.push('');
    });

    lines.push('=== FINE DOCUMENTI CARICATI ===');
    return lines.join('\n').trim();
  }

  function stripMarkdown(value) {
    return String(value || '')
      .replace(/```[\s\S]*?```/g, ' ')
      .replace(/^#{1,6}\s+/gm, '')
      .replace(/^\s*[-*]\s+/gm, '')
      .replace(/^\s*\d+[.)]\s+/gm, '')
      .replace(/\*\*(.*?)\*\*/g, '$1')
      .replace(/`([^`]+)`/g, '$1')
      .replace(/\[(.*?)\]\((.*?)\)/g, '$1')
      .replace(/[_>*#]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function sanitizeTitle(value) {
    var title = stripMarkdown(value || '').replace(/[\\/:*?"<>|]+/g, ' ').replace(/\s+/g, ' ').trim();
    return title || 'Documento generato da Lex';
  }

  function slugifyTitle(value, fallbackExtension) {
    var slug = sanitizeTitle(value)
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '');
    return (slug || 'documento-generato-da-lex') + '.' + fallbackExtension;
  }

  function suggestGeneratedTitle(options) {
    var explicit = sanitizeTitle(options && options.title);
    if (explicit !== 'Documento generato da Lex') {
      return explicit;
    }

    var answer = String((options && options.answer) || '');
    var lines = answer.split(/\r?\n/);
    for (var i = 0; i < lines.length; i += 1) {
      var line = sanitizeTitle(lines[i].replace(/^#{1,6}\s+/, ''));
      if (line && line !== 'Documento generato da Lex') {
        return line.slice(0, 96);
      }
    }

    var question = sanitizeTitle(options && options.question);
    if (question !== 'Documento generato da Lex') {
      return question.slice(0, 96);
    }
    return explicit;
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
            '<div class="pct-ai-attachment__detail">' + escapeHtml(item.mime_type || 'documento') + ' - ' + escapeHtml(bytesLabel(item.size_bytes)) + '</div>' +
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

  function buildGeneratedDocumentActions(options) {
    var title = escapeHtml(suggestGeneratedTitle(options || {}));
    var editorImportUrl = String((options && options.editorImportUrl) || '').trim();
    var titleMarkup = editorImportUrl
      ? (
        '<button class="pct-ai-generated-btn pct-ai-generated-title" type="button" data-generated-open-editor="true" title="Apri nell\'editor professionale">' +
          '<span>' + title + '</span>' +
        '</button>'
      )
      : '<span>' + title + '</span>';
    var openEditorButton = editorImportUrl
      ? (
        '<button class="pct-ai-generated-btn pct-ai-generated-btn--primary" type="button" data-generated-open-editor="true">' +
          '<i class="bi bi-pencil-square"></i><span>Apri nell\'editor</span>' +
        '</button>'
      )
      : '';
    var docxClass = editorImportUrl ? 'pct-ai-generated-btn' : 'pct-ai-generated-btn pct-ai-generated-btn--primary';
    return (
      '<div class="pct-ai-generated-actions" data-generated-document-actions="true">' +
        '<div class="pct-ai-generated-actions__meta">' +
          '<i class="bi bi-file-earmark-richtext"></i>' +
          titleMarkup +
        '</div>' +
        '<div class="pct-ai-generated-actions__buttons">' +
          openEditorButton +
          '<button class="' + docxClass + '" type="button" data-generated-download="docx">' +
            '<i class="bi bi-file-earmark-word"></i><span>Scarica Word</span>' +
          '</button>' +
          '<button class="pct-ai-generated-btn" type="button" data-generated-download="md">' +
            '<i class="bi bi-file-earmark-text"></i><span>Scarica Markdown</span>' +
          '</button>' +
        '</div>' +
      '</div>'
    );
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

  function buildConversationBlob(options) {
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

    return {
      blob: new Blob([rows.join('\n')], { type: 'text/markdown;charset=utf-8' }),
      fileName: 'lex-conversazione-' +
        timestamp.toLocaleDateString('it-IT').replace(/\//g, '-') + '-' +
        timestamp.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' }).replace(':', '-') +
        '.md',
    };
  }

  function buildGeneratedMarkdownBlob(options) {
    var title = suggestGeneratedTitle(options || {});
    var rows = [
      '# ' + title,
      '',
      'Generato da Lex il: ' + new Date().toLocaleString('it-IT'),
    ];
    if (options && options.contextLabel) {
      rows.push('Contesto: ' + options.contextLabel);
    }
    if (options && options.question) {
      rows.push('');
      rows.push('## Richiesta iniziale');
      rows.push(String(options.question || '').trim());
    }
    rows.push('');
    rows.push('## Contenuto generato');
    rows.push(String((options && options.answer) || '').trim());

    var citations = Array.isArray(options && options.citations) ? options.citations.filter(Boolean) : [];
    if (citations.length) {
      rows.push('');
      rows.push('## Fonti');
      citations.forEach(function (item) {
        rows.push('- ' + item);
      });
    }

    return {
      blob: new Blob([rows.join('\n')], { type: 'text/markdown;charset=utf-8' }),
      fileName: slugifyTitle(title, 'md'),
    };
  }

  function triggerBlobDownload(payload) {
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

  function triggerDownload(options) {
    triggerBlobDownload(buildConversationBlob(options || {}));
  }

  function downloadGeneratedMarkdown(options) {
    triggerBlobDownload(buildGeneratedMarkdownBlob(options || {}));
  }

  async function openGeneratedInEditor(options) {
    var editorImportUrl = String((options && options.editorImportUrl) || '').trim();
    if (!editorImportUrl) {
      throw new Error('Apri la bozza da un fascicolo per salvarla nell\'editor professionale.');
    }
    var response = await fetch(editorImportUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: suggestGeneratedTitle(options || {}),
        question: String((options && options.question) || ''),
        answer: String((options && options.answer) || ''),
        citations: Array.isArray(options && options.citations) ? options.citations : [],
        context_label: String((options && options.contextLabel) || ''),
      }),
    });

    var payload = null;
    try {
      payload = await response.json();
    } catch (error) {
      payload = null;
    }
    if (!response.ok) {
      throw new Error(String((payload && (payload.detail || payload.errore)) || 'Apertura nell\'editor non riuscita.'));
    }
    if (!payload || !payload.open_url) {
      throw new Error('Il documento è stato creato ma il collegamento all\'editor non è disponibile.');
    }
    window.location.assign(String(payload.open_url));
    return payload;
  }

  async function downloadGeneratedDocx(options) {
    var response = await fetch(String((options && options.exportUrl) || ''), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: suggestGeneratedTitle(options || {}),
        question: String((options && options.question) || ''),
        answer: String((options && options.answer) || ''),
        citations: Array.isArray(options && options.citations) ? options.citations : [],
        context_label: String((options && options.contextLabel) || ''),
      }),
    });

    if (!response.ok) {
      throw new Error('Export Word non disponibile in questo momento.');
    }

    var contentType = String(response.headers.get('content-type') || '');
    if (contentType.indexOf('application/json') >= 0) {
      var payload = await response.json();
      throw new Error(String((payload && payload.errore) || 'Export Word non riuscito.'));
    }

    var blob = await response.blob();
    var disposition = String(response.headers.get('content-disposition') || '');
    var match = disposition.match(/filename="?([^"]+)"?/i);
    triggerBlobDownload({
      blob: blob,
      fileName: match ? match[1] : slugifyTitle(suggestGeneratedTitle(options || {}), 'docx'),
    });
  }

  window.PctLexDocuments = {
    bindShelfRemoval: bindShelfRemoval,
    buildGeneratedDocumentActions: buildGeneratedDocumentActions,
    buildPromptBlock: buildPromptBlock,
    downloadGeneratedDocx: downloadGeneratedDocx,
    downloadGeneratedMarkdown: downloadGeneratedMarkdown,
    openGeneratedInEditor: openGeneratedInEditor,
    parseAttachments: parseAttachments,
    renderAttachmentShelf: renderAttachmentShelf,
    suggestGeneratedTitle: suggestGeneratedTitle,
    triggerDownload: triggerDownload,
  };
})();
