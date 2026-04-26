# Lex AI - Analisi giurisprudenziale

Da `2.188.1` Lex usa un workflow dedicato quando la richiesta riguarda una
sentenza, una massima, una pronuncia o una ricerca giurisprudenziale.

## Schema risposta

Le risposte giurisprudenziali devono seguire uno schema verificabile:

- Pronuncia individuata
- Organo giudicante
- Oggetto della decisione
- Questione giuridica
- Norma/e coinvolte
- Decisione / dispositivo
- Principio ricavabile
- Impatto pratico per lo studio
- Limiti e verifiche
- Fonti considerate

## Fonti e fallback

Il retrieval passa a Lex metadati strutturati quando disponibili: organo,
numero, anno, sezione, date, norme citate, questione, dispositivo, principio,
massima e URL ufficiali.

Se il provider locale genera una risposta generica o conversazionale, la guardia
`CaseLawAnswerGuard` segnala il problema e Lex sostituisce la bozza con una
risposta deterministica costruita sulle evidenze disponibili.

## Limiti

Lex non deve inventare dispositivo, massima, organo, numero o norme. Se il testo
integrale o la motivazione completa non sono disponibili nelle evidenze, il
limite viene dichiarato nella risposta.
