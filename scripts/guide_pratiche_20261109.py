#!/usr/bin/env python3
"""Guide pratiche del 09/11/2026 per i fascicoli dello studio rimasti senza guida.

- precetto (artt. 474-481 c.p.c.), anche contro le amministrazioni (art. 14 D.L. 669/1996): guida nuova;
- silenzio del Ministero sul riconoscimento di un titolo conseguito all'estero (D.Lgs. 206/2007; artt. 31, 117 c.p.a.):
  guida nuova;
- ottemperanza al giudicato del giudice ordinario davanti al TAR (artt. 112-114 c.p.a.): guida completata (allegati,
  competenza, rito camerale, contributo).

Norme lette il 09/11/2026 sul testo vigente dell'archivio Normattiva del software (D.L. 669/1996 su normattiva.it).
Uso dalla root: python scripts/guide_pratiche_20261109.py && python scripts/merge_legal_kb_modules.py
"""

from __future__ import annotations

import json
from pathlib import Path

MODULI = Path(__file__).resolve().parents[1] / "pct" / "data" / "legal_knowledge_base_modules"
VERIFICA = "2026-11-09"


def _campo(ident: str, label: str, tipo: str = "string") -> dict:
    return {"id": ident, "label": label, "required": True, "type": tipo}


PRECETTO = {
    "codice": "GUIDA_PRECETTO_ANCHE_CONTRO_PA",
    "denominazione": "Atto di precetto (artt. 479-481 c.p.c.), anche contro la pubblica amministrazione (art. 14 D.L. 669/1996)",
    "categoria": "Esecuzione forzata – atto di precetto",
    "materia": "Esecuzioni forzate",
    "rito": "Atto stragiudiziale notificato: precede l'esecuzione forzata (non si deposita)",
    "competenza": ("Nel precetto si indica il giudice competente per l'esecuzione (art. 480, terzo comma, c.p.c.); "
                   "le eventuali opposizioni si propongono davanti a quel giudice"),
    "verificato_il": VERIFICA,
    "normativa": [
        {"fonte": "c.p.c.", "articolo": "474", "descrizione": "Titolo esecutivo per un diritto certo, liquido ed esigibile"},
        {"fonte": "c.p.c.", "articolo": "475", "descrizione": "Titolo giudiziale in copia attestata conforme all'originale o in duplicato informatico"},
        {"fonte": "c.p.c.", "articolo": "479", "descrizione": "Notificazione del titolo (duplicato informatico o copia attestata conforme) e del precetto alla parte personalmente; il precetto può seguire il titolo"},
        {"fonte": "c.p.c.", "articolo": "480", "descrizione": "Contenuto a pena di nullità: parti, data di notifica del titolo, termine non minore di 10 giorni, avvertimenti (anche sovraindebitamento), giudice competente, residenza o domicilio digitale"},
        {"fonte": "c.p.c.", "articolo": "481", "descrizione": "Inefficacia se l'esecuzione non inizia entro 90 giorni dalla notificazione"},
        {"fonte": "c.p.c.", "articolo": "431", "descrizione": "Sentenze di condanna a favore del lavoratore provvisoriamente esecutive, anche con la sola copia del dispositivo"},
        {"fonte": "D.L. 669/1996", "articolo": "14", "descrizione": "Amministrazioni dello Stato ed enti pubblici non economici: 120 giorni dalla notificazione del titolo esecutivo prima di procedere a esecuzione forzata; precetto presso la struttura territoriale dell'ente (comma 1-bis)"},
        {"fonte": "R.D. 1611/1933", "articolo": "11", "descrizione": "Notifiche alle amministrazioni dello Stato presso l'Avvocatura distrettuale per gli atti dei giudizi e le sentenze"},
    ],
    "obbligo_mediazione": {"obbligatoria": False},
    "atto_principale": {
        "tipo_atto": "precetto",
        "denominazione": "Atto di precetto",
        "campi_chiave": [
            _campo("titolo_esecutivo", "Titolo esecutivo (sentenza, decreto ingiuntivo esecutivo, ordinanza) con data e numero"),
            _campo("data_notifica_titolo", "Data di notificazione del titolo, se notificato separatamente", "date"),
            _campo("somme_intimate", "Somme intimate: capitale, interessi, rivalutazione, spese liquidate e spese del precetto"),
            _campo("termine_adempimento", "Termine per adempiere (non meno di 10 giorni)"),
            _campo("giudice_esecuzione", "Giudice competente per l'esecuzione"),
            _campo("domicilio_digitale", "Elezione di domicilio o indirizzo PEC dai pubblici elenchi"),
        ],
        "campi_obbligatori": [
            _campo("titolo_esecutivo", "Titolo esecutivo (sentenza, decreto ingiuntivo esecutivo, ordinanza) con data e numero"),
            _campo("somme_intimate", "Somme intimate: capitale, interessi, rivalutazione, spese liquidate e spese del precetto"),
            _campo("giudice_esecuzione", "Giudice competente per l'esecuzione"),
        ],
        "avvertimenti_obbligatori": [
            "Avvertimento che, in mancanza di adempimento nel termine, si procederà a esecuzione forzata (art. 480, primo comma, c.p.c.)",
            "Avvertimento sulla composizione della crisi da sovraindebitamento con l'ausilio di un OCC o di un professionista (art. 480, secondo comma, c.p.c.)",
        ],
    },
    "allegati_obbligatori": [
        {"id": "titolo_esecutivo", "label": "Titolo esecutivo in duplicato informatico o copia attestata conforme (artt. 475 e 479 c.p.c.)", "required": True},
        {"id": "relata_titolo", "label": "Relata di notificazione del titolo, se notificato prima del precetto", "required": False},
        {"id": "conteggio", "label": "Conteggio delle somme (capitale, interessi legali, rivalutazione per i crediti di lavoro, spese)", "required": True},
    ],
    "adempimenti_propedeutici": [
        {"step": 1, "azione": "Verificare che il titolo sia esecutivo: per il lavoratore la condanna è provvisoriamente esecutiva (art. 431 c.p.c.)", "obbligatorio": True},
        {"step": 2, "azione": "Notificare il titolo esecutivo alla parte personalmente (art. 479 c.p.c.); il precetto può seguire nello stesso atto", "obbligatorio": True},
        {"step": 3, "azione": ("Contro le amministrazioni dello Stato e gli enti pubblici non economici: notificare il titolo e attendere 120 giorni "
                               "prima del precetto e dell'esecuzione (art. 14, comma 1, D.L. 669/1996)"), "obbligatorio": True},
        {"step": 4, "azione": ("Individuare dove notificare all'amministrazione: per gli enti territoriali la struttura territoriale (art. 14, comma 1-bis); "
                               "per i ministeri verificare l'organo che rappresenta l'amministrazione e, per prudenza, notificare anche all'Avvocatura distrettuale "
                               "(l'art. 11 R.D. 1611/1933 riguarda gli atti dei giudizi e le sentenze)"), "obbligatorio": True},
        {"step": 5, "azione": "Iniziare l'esecuzione entro 90 giorni dalla notificazione del precetto, a pena di inefficacia (art. 481 c.p.c.)", "obbligatorio": True},
    ],
    "termini_processuali": [
        {"termine": "Attesa dopo la notifica del titolo all'amministrazione", "decorrenza": "notificazione del titolo esecutivo", "natura": "dilatorio", "norma": "art. 14, comma 1, D.L. 669/1996", "giorni": 120},
        {"termine": "Termine per adempiere indicato nel precetto", "decorrenza": "notificazione del precetto", "natura": "minimo", "norma": "art. 480, primo comma, c.p.c.", "giorni": 10},
        {"termine": "Efficacia del precetto", "decorrenza": "notificazione del precetto", "natura": "decadenza", "norma": "art. 481 c.p.c.", "giorni": 90},
    ],
    "adempimenti_fiscali_telematici": {
        "contributo_unificato": "Non dovuto per il precetto: atto stragiudiziale; il contributo si versa con l'iscrizione a ruolo dell'esecuzione",
        "notifica": "A mezzo PEC ai sensi della L. 53/1994 oppure tramite ufficiale giudiziario",
    },
    "avvertenze_redazionali": [
        "Le spese del precetto si calcolano secondo i parametri forensi vigenti e non sono ripetibili se il precetto è notificato prima dei 120 giorni contro l'amministrazione",
        "Indicare con esattezza le somme già pagate dall'amministrazione per evitare l'opposizione",
    ],
    "guida_interna_non_depositabile": True,
    "depositabile": False,
    "codice_deposito_automatico": False,
    "parole_chiave": ["precetto", "atto di precetto", "esecuzione contro la pa", "titolo esecutivo", "120 giorni"],
    "_quality_hint": "operativa_curata",
}

SILENZIO_TITOLO_ESTERO = {
    "codice": "GUIDA_AMMINISTRATIVO_SILENZIO_RICONOSCIMENTO_TITOLO_ESTERO",
    "denominazione": "Silenzio del Ministero sul riconoscimento di un titolo professionale conseguito all'estero (D.Lgs. 206/2007; artt. 31 e 117 c.p.a.)",
    "categoria": "Processo amministrativo – silenzio",
    "materia": "Diritto amministrativo e appalti",
    "rito": "Rito camerale del silenzio davanti al TAR (artt. 87, comma 2, lett. b, e 117 c.p.a.), processo amministrativo telematico",
    "competenza": "TAR del Lazio, sede di Roma, per i provvedimenti dei ministeri con effetti sull'intero territorio nazionale; verificare la competenza territoriale sul caso",
    "uffici_destinatari": ["Processo amministrativo telematico"],
    "verificato_il": VERIFICA,
    "normativa": [
        {"fonte": "D.Lgs. 206/2007", "articolo": "5", "descrizione": "Autorità competente: il Ministero dell'istruzione per i docenti delle scuole"},
        {"fonte": "D.Lgs. 206/2007", "articolo": "16", "descrizione": "Domanda, verifica della completezza entro 30 giorni, provvedimento entro tre mesi dalla documentazione completa (quattro mesi per i capi II e III)"},
        {"fonte": "L. 241/1990", "articolo": "2", "descrizione": "Obbligo di concludere il procedimento con provvedimento espresso"},
        {"fonte": "D.Lgs. 104/2010 (c.p.a.)", "articolo": "31", "descrizione": "Azione avverso il silenzio finché dura l'inadempimento e non oltre un anno dalla scadenza del termine"},
        {"fonte": "D.Lgs. 104/2010 (c.p.a.)", "articolo": "117", "descrizione": "Ricorso anche senza diffida, notificato all'amministrazione e ad almeno un controinteressato; sentenza in forma semplificata; commissario ad acta"},
        {"fonte": "D.Lgs. 104/2010 (c.p.a.)", "articolo": "87", "descrizione": "Camera di consiglio e termini dimezzati, salvo quelli di notifica del ricorso"},
        {"fonte": "D.P.R. 115/2002", "articolo": "13, comma 6-bis, lett. a", "descrizione": "Contributo unificato di euro 300 per i ricorsi dell'art. 117 c.p.a."},
    ],
    "obbligo_mediazione": {"obbligatoria": False},
    "atto_principale": {
        "tipo_atto": "ricorso",
        "denominazione": "Ricorso avverso il silenzio (art. 117 c.p.a.)",
        "campi_chiave": [
            _campo("istanza", "Domanda di riconoscimento: data di presentazione e protocollo"),
            _campo("documentazione_completa", "Data in cui la documentazione è risultata completa (o integrazioni richieste)", "date"),
            _campo("titolo_estero", "Titolo o abilitazione conseguiti all'estero e Stato di rilascio"),
            _campo("scadenza_termine", "Scadenza del termine per provvedere (tre o quattro mesi, art. 16, comma 6)", "date"),
            _campo("domanda", "Accertamento dell'obbligo di provvedere e, se l'attività è vincolata, della fondatezza (art. 31, comma 3)"),
        ],
        "campi_obbligatori": [
            _campo("istanza", "Domanda di riconoscimento: data di presentazione e protocollo"),
            _campo("scadenza_termine", "Scadenza del termine per provvedere (tre o quattro mesi, art. 16, comma 6)", "date"),
        ],
        "avvertimenti_obbligatori": [
            "Proporre il ricorso entro un anno dalla scadenza del termine per provvedere (art. 31, comma 2, c.p.a.)",
            "Se il Ministero provvede nel corso del giudizio, il provvedimento si impugna con motivi aggiunti (art. 117, comma 5, c.p.a.)",
        ],
    },
    "allegati_obbligatori": [
        {"id": "istanza", "label": "Domanda di riconoscimento con ricevuta di presentazione", "required": True},
        {"id": "documentazione", "label": "Documentazione del titolo estero e prova della sua completezza o delle integrazioni", "required": True},
        {"id": "eventuale_diffida", "label": "Eventuale diffida o sollecito (non necessari, art. 117, comma 1)", "required": False},
        {"id": "procura", "label": "Procura alle liti", "required": True},
    ],
    "adempimenti_propedeutici": [
        {"step": 1, "azione": "Calcolare la scadenza: tre mesi (quattro per i capi II e III) dalla documentazione completa (art. 16, comma 6, D.Lgs. 206/2007)", "obbligatorio": True},
        {"step": 2, "azione": "Notificare il ricorso al Ministero presso l'Avvocatura dello Stato e ad almeno un controinteressato, se esiste (art. 117, comma 1, c.p.a.; art. 11 R.D. 1611/1933)", "obbligatorio": True},
        {"step": 3, "azione": "Depositare il ricorso al TAR nei termini del rito camerale (dimezzati, art. 87, comma 3, c.p.a.)", "obbligatorio": True},
    ],
    "termini_processuali": [
        {"termine": "Termine per il Ministero", "decorrenza": "documentazione completa", "natura": "procedimentale", "norma": "art. 16, comma 6, D.Lgs. 206/2007", "mesi": 3},
        {"termine": "Proposizione del ricorso", "decorrenza": "scadenza del termine per provvedere", "natura": "decadenza", "norma": "art. 31, comma 2, c.p.a.", "anni": 1},
    ],
    "adempimenti_fiscali_telematici": {
        "contributo_unificato": "Euro 300 (art. 13, comma 6-bis, lett. a, D.P.R. 115/2002)",
    },
    "avvertenze_redazionali": [
        "Il giudice decide sulla fondatezza della pretesa solo se l'attività è vincolata o non residua discrezionalità (art. 31, comma 3, c.p.a.)",
    ],
    "guida_interna_non_depositabile": True,
    "depositabile": False,
    "codice_deposito_automatico": False,
    "parole_chiave": ["silenzio", "titolo estero", "riconoscimento titolo", "abilitazione estera", "qualifica professionale", "silenzio ministero"],
    "_quality_hint": "operativa_curata",
}


def _ottemperanza_completata(scheda: dict) -> dict:
    scheda["competenza"] = ("Giudice che ha emesso il provvedimento (art. 113, comma 1, c.p.a.); per le sentenze del giudice ordinario "
                            "il TAR nella cui circoscrizione ha sede il giudice che ha emesso la sentenza (art. 113, comma 2)")
    scheda["rito"] = "Camera di consiglio con termini dimezzati, salvo la notifica del ricorso (art. 87, commi 2, lett. d, e 3, c.p.a.); processo amministrativo telematico"
    scheda["verificato_il"] = VERIFICA
    norme = {(n["fonte"], n["articolo"]) for n in scheda["normativa"]}
    for voce in (
        {"fonte": "D.Lgs. 104/2010 (c.p.a.)", "articolo": "87", "descrizione": "Ottemperanza in camera di consiglio, termini dimezzati"},
        {"fonte": "disp. att. c.p.c.", "articolo": "124", "descrizione": "Certificato del cancelliere di passaggio in giudicato"},
        {"fonte": "D.P.R. 115/2002", "articolo": "13, comma 6-bis, lett. a", "descrizione": "Contributo unificato di euro 300 per l'ottemperanza"},
        {"fonte": "D.L. 669/1996", "articolo": "14", "descrizione": "Crediti di denaro verso lo Stato: 120 giorni dalla notifica del titolo"},
    ):
        if (voce["fonte"], voce["articolo"]) not in norme:
            scheda["normativa"].append(voce)
    scheda["allegati_obbligatori"] = [
        {"id": "sentenza", "label": "Sentenza o provvedimento da eseguire in copia autentica (art. 114, comma 2, c.p.a.)", "required": True},
        {"id": "giudicato", "label": "Prova del passaggio in giudicato: certificato del cancelliere (art. 124 disp. att. c.p.c.) per le sentenze del giudice ordinario", "required": True},
        {"id": "notifica_titolo", "label": "Relata della notifica della sentenza all'amministrazione", "required": True},
        {"id": "procura", "label": "Procura alle liti", "required": True},
    ]
    scheda["adempimenti_propedeutici"] = [
        {"step": 1, "azione": "Per i crediti di denaro contro lo Stato verificare il decorso dei 120 giorni dalla notifica del titolo (art. 14 D.L. 669/1996)", "obbligatorio": True},
        {"step": 2, "azione": "Notificare il ricorso all'amministrazione e a tutte le altre parti del giudizio definito dalla sentenza, anche senza previa diffida (art. 114, comma 1, c.p.a.)", "obbligatorio": True},
        {"step": 3, "azione": "Chiedere, se utile, la nomina del commissario ad acta e la somma per ogni ritardo (art. 114, comma 4, lett. d ed e)", "obbligatorio": False},
        {"step": 4, "azione": "Interessi e rivalutazione maturati dopo il giudicato si chiedono nello stesso giudizio (art. 112, comma 3)", "obbligatorio": False},
    ]
    scheda["adempimenti_fiscali_telematici"] = {"contributo_unificato": "Euro 300 (art. 13, comma 6-bis, lett. a, D.P.R. 115/2002)"}
    parole = list(scheda.get("parole_chiave") or [])
    for p in ("ricorso per l'ottemperanza", "ottemperanza giudicato giudice ordinario", "ottemperanza sentenza lavoro"):
        if p not in parole:
            parole.append(p)
    scheda["parole_chiave"] = parole
    return scheda


def _oggetto_in_testo(testo: str, codice: str) -> tuple[int, int]:
    """Inizio e fine nel testo dell'oggetto JSON con quel codice (per non riformattare il resto del modulo)."""
    chiave = testo.index(f'"codice": "{codice}"')
    inizio = testo.rindex("{", 0, chiave)
    _valore, fine = json.JSONDecoder().raw_decode(testo, inizio)
    return inizio, fine


def _rientro(blocco: dict, spazi: int) -> str:
    righe = json.dumps(blocco, ensure_ascii=False, indent=2).splitlines()
    return "\n".join(" " * spazi + r if i else r for i, r in enumerate(righe))


def _salva(nome: str, schede_nuove: list[dict], ritocchi: dict | None = None) -> None:
    percorso = MODULI / nome
    testo = percorso.read_text(encoding="utf-8")
    for codice, funzione in (ritocchi or {}).items():
        inizio, fine = _oggetto_in_testo(testo, codice)
        riga = testo.rfind("\n", 0, inizio) + 1
        testo = testo[:inizio] + _rientro(funzione(json.loads(testo[inizio:fine])), inizio - riga) + testo[fine:]
    for nuova in schede_nuove:
        if f'"codice": "{nuova["codice"]}"' in testo:
            inizio, fine = _oggetto_in_testo(testo, nuova["codice"])
            riga = testo.rfind("\n", 0, inizio) + 1
            testo = testo[:inizio] + _rientro(nuova, inizio - riga) + testo[fine:]
            continue
        # In coda all'elenco «codici_materia» (non all'ultimo elenco del modulo).
        apertura = testo.index("[", testo.index('"codici_materia"'))
        _elenco, fine_elenco = json.JSONDecoder().raw_decode(testo, apertura)
        chiusura = fine_elenco - 1
        ultimo = testo.rindex("}", 0, chiusura)
        inizio_ultimo = testo.rfind("\n", 0, testo.rindex("{", 0, ultimo)) + 1
        spazi = len(testo[inizio_ultimo:]) - len(testo[inizio_ultimo:].lstrip(" "))
        testo = testo[:ultimo + 1] + ",\n" + " " * spazi + _rientro(nuova, spazi) + testo[ultimo + 1:]
    json.loads(testo)  # il modulo resta JSON valido
    percorso.write_text(testo, encoding="utf-8")


if __name__ == "__main__":
    _salva("kb_12_esecuzioni_forzate.json", [PRECETTO])
    _salva("kb_26_amministrativo_procedura_guide_pratiche.json", [SILENZIO_TITOLO_ESTERO],
           {"GUIDA_AMMINISTRATIVO_OTTEMPERANZA": _ottemperanza_completata})
    print("guide aggiornate")
