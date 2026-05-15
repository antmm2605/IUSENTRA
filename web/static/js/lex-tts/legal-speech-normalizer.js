(function (root) {
  'use strict';

  var MONTHS = [
    '',
    'gennaio',
    'febbraio',
    'marzo',
    'aprile',
    'maggio',
    'giugno',
    'luglio',
    'agosto',
    'settembre',
    'ottobre',
    'novembre',
    'dicembre',
  ];

  function text(value) {
    return String(value == null ? '' : value);
  }

  function cleanSpaces(value) {
    return text(value)
      .replace(/[ \t\r\f\v]+/g, ' ')
      .replace(/\s+([,.;:!?])/g, '$1')
      .replace(/([,;:!?])([^\s])/g, '$1 $2')
      .replace(/\s+\./g, '.')
      .replace(/\.{3,}/g, '...')
      .trim();
  }

  function sentenceJoin(value) {
    return text(value)
      .replace(/\r\n/g, '\n')
      .replace(/\n{2,}/g, '. ')
      .replace(/\n/g, ' ');
  }

  function sanitizeSpeechMarkdown(value) {
    var clean = text(value);
    clean = clean.replace(/```[\s\S]*?```/g, ' ');
    clean = clean.replace(/`([^`\n]+)`/g, '$1');
    clean = clean.replace(/!\[([^\]]*)\]\([^)]+\)/g, '$1');
    clean = clean.replace(/\[([^\]]+)\]\((?:https?:\/\/|\/)[^)]+\)/g, '$1');
    clean = clean.replace(/https?:\/\/\S+/gi, 'link disponibile nella risposta scritta');
    clean = clean.replace(/^\s{0,3}#{1,6}\s*/gm, '');
    clean = clean.replace(/^\s{0,3}>\s?/gm, '');
    clean = clean.replace(/^\s*[-*+]\s+/gm, '');
    clean = clean.replace(/\*\*([^*]+)\*\*/g, '$1');
    clean = clean.replace(/\*([^*\n]+)\*/g, '$1');
    clean = clean.replace(/__([^_]+)__/g, '$1');
    clean = clean.replace(/_([^_\n]+)_/g, '$1');
    clean = clean.replace(/<\/?[^>]+>/g, ' ');
    clean = clean.replace(/\|[^\n]*\|/g, function (row) {
      return row.length > 120 ? ' tabella disponibile nella risposta scritta ' : row.replace(/\|/g, ' ');
    });
    return cleanSpaces(sentenceJoin(clean));
  }

  function reduceSensitiveSequences(value) {
    var clean = text(value);
    clean = clean.replace(/\b[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]\b/gi, 'codice fiscale omesso');
    clean = clean.replace(/\bIT\d{2}[A-Z0-9]{1,30}\b/gi, 'iban omesso');
    clean = clean.replace(/\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/gi, 'codice identificativo omesso');
    clean = clean.replace(/\b[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b/g, 'riferimento tecnico omesso');
    clean = clean.replace(/\b[0-9a-f]{32,}\b/gi, 'riferimento tecnico omesso');
    clean = clean.replace(/\b\d{12,}\b/g, 'numero lungo omesso');
    clean = clean.replace(/https?:\/\/\S+/gi, 'link disponibile nella risposta scritta');
    return cleanSpaces(clean);
  }

  function expandLegalAbbreviations(value) {
    var clean = text(value);
    var rules = [
      [/\bdisp\.\s*att\.\s*c\.p\.c\./gi, 'disposizioni di attuazione del codice di procedura civile'],
      [/\bCass\.\s*civ\./g, 'Cassazione civile'],
      [/\bCass\.\s*pen\./g, 'Cassazione penale'],
      [/\bSez\.\s*Un\./g, 'Sezioni Unite'],
      [/\bCons\.\s*Stato\b/g, 'Consiglio di Stato'],
      [/\bCorte\s+App\./g, "Corte d'appello"],
      [/\bD\.Lgs\./g, 'decreto legislativo'],
      [/\bD\.P\.R\./g, 'decreto del Presidente della Repubblica'],
      [/\bD\.L\./g, 'decreto legge'],
      [/\bc\.p\.p\./gi, 'codice di procedura penale'],
      [/\bc\.p\.c\./gi, 'codice di procedura civile'],
      [/\bc\.c\./gi, 'codice civile'],
      [/\bc\.p\./gi, 'codice penale'],
      [/\bCass\./g, 'Cassazione'],
      [/\bTrib\./g, 'Tribunale'],
      [/\bCost\./g, 'Costituzione'],
      [/\bartt\./gi, 'articoli'],
      [/\bart\./gi, 'articolo'],
      [/\bco\./gi, 'comma'],
      [/\bnn\./gi, 'numeri'],
      [/\bn\.\s*(\d+)\s*\/\s*(\d{4})/gi, 'numero $1 del $2'],
      [/\bn\.\s*(\d+)/gi, 'numero $1'],
      [/\bL\.\s*(\d+)\s*\/\s*(\d{4})/g, 'legge $1 del $2'],
      [/\bR\.G\.N\.R\./gi, 'registro generale notizie di reato'],
      [/\bR\.G\./gi, 'ruolo generale'],
      [/\bRG\b/g, 'ruolo generale'],
      [/\bPEC\b/g, 'pec'],
      [/\bPCT\b/g, 'processo civile telematico'],
      [/\bPST\b/g, 'portale dei servizi telematici'],
      [/\bPAT\b/g, 'processo amministrativo telematico'],
      [/\bPTT\b/g, 'processo tributario telematico'],
      [/\bTAR\b/g, 'Tar'],
      [/\bCNF\b/g, 'Consiglio Nazionale Forense'],
      [/\bCEDU\b/g, "Convenzione europea dei diritti dell'uomo"],
    ];
    rules.forEach(function (rule) {
      clean = clean.replace(rule[0], rule[1]);
    });
    clean = clean.replace(/\b(articolo|articoli)\s+(\d+)\s+(codice)\b/gi, '$1 $2 del $3');
    return cleanSpaces(clean);
  }

  function normalizeDate(value) {
    return text(value).replace(/\b(\d{1,2})[\/-](\d{1,2})[\/-](\d{4})\b/g, function (match, day, month, year) {
      var d = Number(day);
      var m = Number(month);
      if (d < 1 || d > 31 || m < 1 || m > 12) {
        return match;
      }
      return String(d) + ' ' + MONTHS[m] + ' ' + String(year);
    });
  }

  function normalizeMoney(value) {
    function render(amount, cents) {
      var c = cents ? Number(cents) : 0;
      return amount + ' euro' + (c ? ' e ' + c + ' centesimi' : '');
    }
    var clean = text(value);
    clean = clean.replace(/€\s*(\d{1,3}(?:\.\d{3})*|\d+)(?:,(\d{1,2}))?/g, function (_match, amount, cents) {
      return render(amount, cents);
    });
    clean = clean.replace(/\b(\d{1,3}(?:\.\d{3})*|\d+),(\d{2})\s*€/g, function (_match, amount, cents) {
      return render(amount, cents);
    });
    return clean;
  }

  function trimLongAnswer(value, options) {
    var clean = text(value).trim();
    var limit = Math.max(360, Number(options && options.maxAutoReadChars) || 1800);
    if (clean.length <= limit) {
      return clean;
    }
    var slice = clean.slice(0, limit);
    var boundary = Math.max(slice.lastIndexOf('. '), slice.lastIndexOf('; '), slice.lastIndexOf(': '));
    if (boundary > 220) {
      slice = slice.slice(0, boundary + 1);
    }
    return cleanSpaces(slice) + ' Risposta lunga: lettura limitata alla sintesi.';
  }

  function normalizeLegalSpeechText(value, options) {
    options = options || {};
    var clean = sanitizeSpeechMarkdown(value);
    clean = reduceSensitiveSequences(clean);
    clean = normalizeDate(clean);
    clean = normalizeMoney(clean);
    if (options.legalNormalization !== false) {
      clean = expandLegalAbbreviations(clean);
    }
    if (options.mode === 'citations_light') {
      clean = clean.replace(/\b(fonti|citazioni)\s*:\s*.+$/i, 'Le fonti sono disponibili nella risposta scritta.');
    }
    clean = cleanSpaces(clean);
    if (clean && !/[.!?]$/.test(clean)) {
      clean += '.';
    }
    return trimLongAnswer(clean, options);
  }

  function splitSentences(paragraph) {
    var normalized = cleanSpaces(paragraph);
    if (!normalized) {
      return [];
    }
    return normalized
      .replace(/([.!?;:])\s+/g, '$1\n')
      .split('\n')
      .map(function (item) { return item.trim(); })
      .filter(Boolean);
  }

  function splitOversizedSentence(sentence, maxChars) {
    var value = cleanSpaces(sentence);
    if (value.length <= maxChars) {
      return [value];
    }
    var words = value.split(/\s+/);
    var chunks = [];
    var current = '';
    words.forEach(function (word) {
      if (!current) {
        current = word;
        return;
      }
      if ((current + ' ' + word).length <= maxChars) {
        current += ' ' + word;
        return;
      }
      chunks.push(current);
      current = word;
    });
    if (current) {
      chunks.push(current);
    }
    return chunks;
  }

  function splitLegalSpeechChunks(value, options) {
    options = options || {};
    var maxChars = Math.max(120, Number(options.maxChunkChars) || 280);
    var pauses = options.pauseMs || {};
    var textValue = cleanSpaces(value);
    if (!textValue) {
      return [];
    }
    var paragraphs = text(value).split(/\n\s*\n+/).map(cleanSpaces).filter(Boolean);
    if (!paragraphs.length) {
      paragraphs = [textValue];
    }
    var chunks = [];
    paragraphs.forEach(function (paragraph, paragraphIndex) {
      var current = '';
      splitSentences(paragraph).forEach(function (sentence) {
        splitOversizedSentence(sentence, maxChars).forEach(function (piece) {
          if (!current) {
            current = piece;
            return;
          }
          if ((current + ' ' + piece).length <= maxChars) {
            current += ' ' + piece;
            return;
          }
          chunks.push({
            text: current,
            type: 'sentence',
            pauseAfterMs: Number(pauses.sentence) || 180,
          });
          current = piece;
        });
      });
      if (current) {
        chunks.push({
          text: current,
          type: paragraphIndex < paragraphs.length - 1 ? 'paragraph' : 'sentence',
          pauseAfterMs: paragraphIndex < paragraphs.length - 1 ? (Number(pauses.paragraph) || 420) : (Number(pauses.sentence) || 180),
        });
      }
    });
    return chunks;
  }

  root.IusentraLegalSpeechNormalizer = {
    normalizeLegalSpeechText: normalizeLegalSpeechText,
    sanitizeSpeechMarkdown: sanitizeSpeechMarkdown,
    expandLegalAbbreviations: expandLegalAbbreviations,
    reduceSensitiveSequences: reduceSensitiveSequences,
    splitLegalSpeechChunks: splitLegalSpeechChunks,
  };
})(typeof window !== 'undefined' ? window : globalThis);
