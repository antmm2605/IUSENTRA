# Giustizia Map - uffici giudiziari competenti per Comune

Consultazione: 25 maggio 2026.

## Fonte

- Fonte primaria: Ministero della Giustizia, `Giustizia Map`, pagina pubblica `https://www.giustizia.it/giustizia/it/mg_form_view.wp?uid=G_MAP`.
- Invio ricerca: form pubblico `https://www.giustizia.it/giustizia/it/mg_form_submit.page` con `uid=G_MAP`, `_pagina_=2`, `cerca_comune`, `_xml_=xml`.
- Ambito: ricerca degli uffici giudiziari collegati a un Comune, con recapiti e blocchi informativi pubblicati dalla fonte ministeriale.

## Regola software

IUSENTRA usa la fonte ministeriale in modalità read-only e senza cache locale per la funzione `Uffici competenti per Comune` negli Strumenti Forensi. Il risultato viene normalizzato per la UI, ma i dati restano attribuiti alla fonte ministeriale.

La funzione non modifica procedure telematiche, fascicoli, depositi o notifiche: espone solo schede operative e collegamenti di lavoro verso le superfici esistenti.

## Campi normalizzati

- Ufficio, tipologia e priorità operativa.
- Indirizzo, Comune, CAP e codice ISTAT quando presenti.
- Telefono, fax, email, PEC, sito web, codice fiscale e patrono quando presenti.
- Assistenza depositi telematici e casellario quando la fonte li espone.
- Note informative pubblicate dalla fonte.

## Uso in Componi PEC

Dal 26 maggio 2026 la stessa funzione alimenta anche il pannello di ricerca in
`/email/scrivi`: l'avvocato può filtrare gli uffici per tipologia e chiedere
solo risultati con PEC pubblicata, poi inserire il recapito nel destinatario del
messaggio. Il filtro non cambia la fonte e non salva cache locale.

Filtri applicativi:

- `tipo_ufficio`: limita i risultati alle tipologie normalizzate richieste
  (`giudice_pace`, `tribunale`, `procura`, `unep`, `corte_appello`,
  `procura_generale`, `assise_appello`, `assise`, `procura_minorenni`,
  `tribunale_minorenni`).
- `solo_pec`: mostra solo gli uffici per cui la fonte pubblica un indirizzo PEC.

## Limiti

La competenza territoriale restituita dalla ricerca deve essere verificata dall'avvocato in base a materia, rito, valore, foro applicabile e norme speciali. La funzione non sostituisce una valutazione professionale e non produce automatismi bloccanti quando la fonte non risponde o restituisce dati incompleti.
