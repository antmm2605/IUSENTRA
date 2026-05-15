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
  var UNITS = ['', 'uno', 'due', 'tre', 'quattro', 'cinque', 'sei', 'sette', 'otto', 'nove'];
  var TEENS = ['dieci', 'undici', 'dodici', 'tredici', 'quattordici', 'quindici', 'sedici', 'diciassette', 'diciotto', 'diciannove'];
  var TENS = ['', '', 'venti', 'trenta', 'quaranta', 'cinquanta', 'sessanta', 'settanta', 'ottanta', 'novanta'];

  function text(value) {
    return String(value == null ? '' : value);
  }

  function cleanSpaces(value) {
    return text(value)
      .replace(/[\u2013\u2011\u2014]/g, '-')
      .replace(/[\u201c\u201d]/g, '"')
      .replace(/[\u2018\u2019\u00b4`]/g, "'")
      .replace(/\u2026/g, '...')
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

  function integerToWords(value) {
    var number = Math.floor(Math.abs(Number(value) || 0));
    if (number === 0) {
      return 'zero';
    }
    if (number < 10) {
      return UNITS[number];
    }
    if (number < 20) {
      return TEENS[number - 10];
    }
    if (number < 100) {
      var ten = Math.floor(number / 10);
      var unit = number % 10;
      var word = TENS[ten];
      if (unit === 1 || unit === 8) {
        word = word.slice(0, -1);
      }
      return word + (unit ? UNITS[unit] : '');
    }
    if (number < 1000) {
      var hundreds = Math.floor(number / 100);
      var rest = number % 100;
      var prefix = hundreds === 1 ? 'cento' : UNITS[hundreds] + 'cento';
      if (rest >= 80 && rest < 90) {
        prefix = prefix.slice(0, -1);
        return prefix + integerToWords(rest);
      }
      return rest ? prefix + ' ' + integerToWords(rest) : prefix;
    }
    if (number < 1000000) {
      var thousands = Math.floor(number / 1000);
      var tail = number % 1000;
      var thousandsWord = thousands === 1 ? 'mille' : integerToWords(thousands).replace(/\s+/g, '') + 'mila';
      return tail ? thousandsWord + ' ' + integerToWords(tail) : thousandsWord;
    }
    return String(number);
  }

  function digitsToWords(value) {
    return text(value).split('').map(function (digit) {
      return /\d/.test(digit) ? integerToWords(Number(digit)) : digit;
    }).join(' ');
  }

  function parseItalianInteger(value) {
    var raw = text(value).replace(/\./g, '').replace(/\s/g, '');
    var number = Number(raw);
    return isFinite(number) ? number : null;
  }

  function normalizeMoney(value) {
    function render(amount, cents) {
      var whole = parseItalianInteger(amount);
      var c = cents ? Number(cents) : 0;
      var spokenAmount = whole == null ? amount : integerToWords(whole);
      return spokenAmount + ' euro' + (c ? ' e ' + integerToWords(c) + ' centesimi' : '');
    }
    var clean = text(value);
    clean = clean.replace(/\u20ac\s*(\d{1,3}(?:\.\d{3})*|\d+)(?:,\s*(\d{1,2}))?/g, function (_match, amount, cents) {
      return render(amount, cents);
    });
    clean = clean.replace(/\b(\d{1,3}(?:\.\d{3})*|\d+),\s*(\d{2})\s*\u20ac/g, function (_match, amount, cents) {
      return render(amount, cents);
    });
    clean = clean.replace(/€\s*(\d{1,3}(?:\.\d{3})*|\d+)(?:,\s*(\d{1,2}))?/g, function (_match, amount, cents) {
      return render(amount, cents);
    });
    clean = clean.replace(/\b(\d{1,3}(?:\.\d{3})*|\d+),\s*(\d{2})\s*€/g, function (_match, amount, cents) {
      return render(amount, cents);
    });
    return clean;
  }

  function decimalToWords(whole, decimals) {
    var parsedWhole = parseItalianInteger(whole);
    var wholeText = parsedWhole == null ? text(whole) : integerToWords(parsedWhole);
    return wholeText + ' virgola ' + digitsToWords(text(decimals).replace(/\D/g, ''));
  }

  function normalizeNumbersForSpeech(value, options) {
    options = options || {};
    var clean = text(value);
    clean = clean.replace(/\b([01]?\d|2[0-3])\s*[:.]\s*(\d{2})\b/g, function (_match, hour, minutes) {
      var h = Number(hour);
      var m = Number(minutes);
      if (m === 0) {
        return integerToWords(h);
      }
      var minutesText = m < 10 ? 'zero ' + integerToWords(m) : integerToWords(m);
      return integerToWords(h) + ' e ' + minutesText;
    });
    clean = clean.replace(/\b(\d{1,3}(?:\.\d{3})*|\d+),\s*(\d+)\s*%/g, function (_match, whole, decimals) {
      return decimalToWords(whole, decimals) + ' per cento';
    });
    clean = clean.replace(/\b(\d{1,3}(?:\.\d{3})*|\d+)\s*%/g, function (_match, whole) {
      var parsed = parseItalianInteger(whole);
      return (parsed == null ? whole : integerToWords(parsed)) + ' per cento';
    });
    clean = clean.replace(/\b(\d{1,3}(?:\.\d{3})+),\s*(\d+)\b/g, function (_match, whole, decimals) {
      return decimalToWords(whole, decimals);
    });
    clean = clean.replace(/\b(\d+),\s*(\d+)\b/g, function (_match, whole, decimals) {
      return decimalToWords(whole, decimals);
    });
    clean = clean.replace(/\b\d{1,3}(?:\.\d{3})+\b/g, function (match) {
      var parsed = parseItalianInteger(match);
      return parsed == null ? match : integerToWords(parsed);
    });
    if (options.standalone !== false) {
      clean = clean.replace(/(^|[^\w\/])(\d{1,6})(?=([^\w\/]|$))/g, function (_match, prefix, number) {
        var parsed = parseItalianInteger(number);
        return prefix + (parsed == null ? number : integerToWords(parsed));
      });
    }
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
    clean = normalizeNumbersForSpeech(clean, { standalone: false });
    if (options.legalNormalization !== false) {
      clean = expandLegalAbbreviations(clean);
      clean = normalizeNumbersForSpeech(clean);
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

  function pauseForText(value, pauses) {
    var clean = text(value).trim();
    if (/[?]$/.test(clean)) {
      return Number(pauses.question) || Number(pauses.sentence) || 260;
    }
    if (/[!]$/.test(clean)) {
      return Number(pauses.exclamation) || Number(pauses.sentence) || 240;
    }
    if (/[,]$/.test(clean)) {
      return Number(pauses.comma) || 120;
    }
    return Number(pauses.sentence) || 220;
  }

  function splitSentences(paragraph, pauses, maxChars) {
    var normalized = cleanSpaces(paragraph);
    if (!normalized) {
      return [];
    }
    var pieces = [];
    normalized
      .replace(/([.!?;:])\s+/g, '$1\n')
      .split('\n')
      .map(function (item) { return item.trim(); })
      .filter(Boolean)
      .forEach(function (item) {
        if (item.indexOf(', ') === -1) {
          pieces.push(item);
          return;
        }
        item.replace(/,\s+/g, ',\n')
          .split('\n')
          .map(function (part) { return part.trim(); })
          .filter(Boolean)
          .forEach(function (part) { pieces.push(part); });
      });
    return pieces.map(function (item) {
      return {
        text: item,
        type: /,$/.test(item) ? 'comma' : 'sentence',
        pauseAfterMs: pauseForText(item, pauses || {}),
      };
    });
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
      splitSentences(paragraph, pauses, maxChars).forEach(function (sentence) {
        var pieces = splitOversizedSentence(sentence.text, maxChars);
        pieces.forEach(function (piece, pieceIndex) {
          chunks.push({
            text: piece,
            type: pieceIndex < pieces.length - 1 ? 'phrase' : sentence.type,
            pauseAfterMs: pieceIndex < pieces.length - 1 ? (Number(pauses.comma) || 120) : sentence.pauseAfterMs,
          });
        });
      });
      if (paragraphIndex < paragraphs.length - 1 && chunks.length) {
        chunks[chunks.length - 1].type = 'paragraph';
        chunks[chunks.length - 1].pauseAfterMs = Number(pauses.paragraph) || 420;
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
    integerToWords: integerToWords,
  };
})(typeof window !== 'undefined' ? window : globalThis);
