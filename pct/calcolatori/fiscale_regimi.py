"""Regime forfettario, fattura dell'agente e prestazione occasionale.

Base normativa:
- Regime forfettario: art. 1, cc. 54-89, L. 190/2014 (soglia ricavi
  85.000 euro dall'art. 1, c. 54, L. 197/2022): reddito imponibile =
  ricavi × coefficiente di redditività per gruppo ATECO (allegato 4),
  meno i contributi previdenziali obbligatori versati; imposta
  sostitutiva 15%, ridotta al 5% per i primi cinque anni di nuova
  attività (c. 65).
- Fattura dell'agente di commercio: ritenuta d'acconto ex art. 25-bis
  D.P.R. 600/1973 sul 50% delle provvigioni (sul 20% se l'agente si
  avvale in via continuativa di dipendenti o terzi, previa
  dichiarazione); contributo Enasarco a carico dell'agente pari alla
  metà dell'aliquota complessiva del 17% (Regolamento istituzionale
  Fondazione Enasarco, vigente dal 2020), entro i massimali
  provvigionali annui fissati dalla Fondazione.
- Ricevuta per prestazione occasionale (redditi diversi ex art. 67,
  c. 1, lett. l, TUIR): ritenuta d'acconto 20% ex art. 25 D.P.R.
  600/1973 se il committente è sostituto d'imposta; imposta di bollo di
  2 euro sulle ricevute di importo superiore a 77,47 euro (D.P.R.
  642/1972, Tariffa all. A, art. 13).
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping

from pct.calcolatori._base import clean_text, safe_float, safe_int

_FONTE_FORFETTARIO = {
    "code": "l_190_2014_forfettario",
    "title": "Art. 1, cc. 54-89, L. 190/2014 — regime forfettario",
    "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:2014-12-23;190",
}
_FONTE_25BIS = {
    "code": "dpr_600_1973_art25bis",
    "title": "Art. 25-bis D.P.R. 600/1973 — ritenuta sulle provvigioni",
    "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.del.presidente.della.repubblica:1973-09-29;600",
}
_FONTE_25 = {
    "code": "dpr_600_1973_art25",
    "title": "Art. 25 D.P.R. 600/1973 — ritenuta sui compensi di lavoro autonomo anche occasionale",
    "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.del.presidente.della.repubblica:1973-09-29;600",
}
_FONTE_ENASARCO = {
    "code": "enasarco_regolamento",
    "title": "Fondazione Enasarco — Regolamento delle attività istituzionali (aliquote e massimali)",
    "url": "https://www.enasarco.it/",
}
_FONTE_BOLLO = {
    "code": "dpr_642_1972_bollo",
    "title": "D.P.R. 642/1972, Tariffa all. A, art. 13 — imposta di bollo sulle quietanze",
    "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.del.presidente.della.repubblica:1972-10-26;642",
}

_SOGLIA_RICAVI_FORFETTARIO = 85_000.0
_SOGLIA_BOLLO = 77.47
_BOLLO = 2.0
_ALIQUOTA_ENASARCO_TOTALE = 17.0  # meta' a carico agente, meta' preponente

# Allegato 4 L. 190/2014 — coefficienti di redditività per gruppo ATECO.
_COEFFICIENTI: List[Dict[str, Any]] = [
    {"value": "alimentari", "label": "Industrie alimentari e delle bevande (10-11)", "coeff": 40.0},
    {"value": "commercio", "label": "Commercio all'ingrosso e al dettaglio (45, 46.2-46.9, 47.1-47.7, 47.9)", "coeff": 40.0},
    {"value": "ambulante_alimentari", "label": "Commercio ambulante di alimentari e bevande (47.81)", "coeff": 40.0},
    {"value": "ambulante_altri", "label": "Commercio ambulante di altri prodotti (47.82, 47.89)", "coeff": 54.0},
    {"value": "costruzioni", "label": "Costruzioni e attività immobiliari (41-43, 68)", "coeff": 86.0},
    {"value": "intermediari", "label": "Intermediari del commercio (46.1)", "coeff": 62.0},
    {"value": "alloggio_ristorazione", "label": "Servizi di alloggio e ristorazione (55-56)", "coeff": 40.0},
    {"value": "professionali", "label": "Attività professionali, scientifiche, tecniche, sanitarie, istruzione, servizi finanziari e assicurativi (64-66, 69-75, 85-88)", "coeff": 78.0},
    {"value": "altri_servizi", "label": "Altre attività economiche", "coeff": 67.0},
]


def calcola_forfettario(payload: Mapping[str, Any]) -> Dict[str, Any]:
    ricavi = safe_float(payload.get("forf_ricavi"))
    gruppo = clean_text(payload.get("forf_gruppo")) or "professionali"
    contributi = safe_float(payload.get("forf_contributi"))
    startup = clean_text(payload.get("forf_startup")) == "1"

    if ricavi <= 0:
        raise ValueError("Inserisci i ricavi o compensi incassati nell'anno.")
    voce = next((v for v in _COEFFICIENTI if v["value"] == gruppo), None)
    if voce is None:
        raise ValueError("Gruppo ATECO non riconosciuto.")
    if contributi < 0:
        raise ValueError("I contributi non possono essere negativi.")

    warnings: List[str] = []
    regime_applicabile = True
    if ricavi > 100_000:
        regime_applicabile = False
        warnings.append(
            "Ricavi oltre 100.000 euro: fuoriuscita IMMEDIATA dal regime nell'anno "
            "stesso (art. 1, c. 71, secondo periodo, L. 190/2014): l'imposta "
            "sostitutiva NON è applicabile, l'intero reddito dell'anno è soggetto a "
            "IRPEF ordinaria e addizionali e l'IVA è dovuta dall'operazione che ha "
            "comportato il superamento. Il calcolo è mostrato a solo titolo "
            "comparativo."
        )
    elif ricavi > _SOGLIA_RICAVI_FORFETTARIO:
        warnings.append(
            "Ricavi oltre 85.000 euro (ma entro 100.000): il regime resta "
            "applicabile per l'anno in corso e cessa dall'anno successivo "
            "(art. 1, c. 71, L. 190/2014)."
        )

    coeff = float(voce["coeff"])
    reddito_lordo = ricavi * coeff / 100.0
    contributi_dedotti = min(contributi, reddito_lordo)
    imponibile = reddito_lordo - contributi_dedotti
    aliquota = 5.0 if startup else 15.0
    imposta = round(imponibile * aliquota / 100.0, 2)

    if contributi > reddito_lordo:
        warnings.append(
            "I contributi eccedono il reddito forfettario: l'eccedenza è deducibile "
            "dal reddito complessivo (art. 1, c. 64, L. 190/2014)."
        )

    return {
        "ricavi": round(ricavi, 2),
        "gruppo": voce["label"],
        "coefficiente": coeff,
        "regime_applicabile": regime_applicabile,
        "reddito_forfettario": round(reddito_lordo, 2),
        "contributi_dedotti": round(contributi_dedotti, 2),
        "imponibile": round(imponibile, 2),
        "aliquota": aliquota,
        "imposta_sostitutiva": imposta,
        "netto_indicativo": round(ricavi - contributi_dedotti - imposta, 2),
        "notes": [
            "Reddito = ricavi × coefficiente di redditività (allegato 4 L. 190/2014) "
            "meno i contributi previdenziali obbligatori versati nell'anno.",
            "Aliquota 5% per i primi cinque anni di nuova attività alle condizioni "
            "del c. 65; 15% negli altri casi. Niente IVA né ritenute; resta dovuta "
            "la contribuzione previdenziale propria.",
            "I gruppi seguono i codici della classificazione ATECO 2007 dell'allegato "
            "4: per i codici ricodificati in ATECO 2025 usare le tavole di "
            "corrispondenza ufficiali ISTAT/Agenzia delle Entrate.",
        ],
        "warnings": warnings,
        "sources": [_FONTE_FORFETTARIO],
    }


def calcola_fattura_agente(payload: Mapping[str, Any]) -> Dict[str, Any]:
    provvigioni = safe_float(payload.get("age_provvigioni"))
    con_collaboratori = clean_text(payload.get("age_collaboratori")) == "1"
    # L'aliquota e' fissata per legge al primo scaglione IRPEF (art. 25-bis,
    # c. 1, D.P.R. 600/1973): non e' un parametro discrezionale. 23% per gli
    # anni versionati 2024-2026 (art. 11 TUIR).
    aliquota_irpef = 23.0

    if provvigioni <= 0:
        raise ValueError("Inserisci le provvigioni imponibili della fattura.")

    iva = round(provvigioni * 0.22, 2)
    base_ritenuta_percent = 20.0 if con_collaboratori else 50.0
    base_ritenuta = provvigioni * base_ritenuta_percent / 100.0
    ritenuta = round(base_ritenuta * aliquota_irpef / 100.0, 2)
    enasarco_agente = round(provvigioni * (_ALIQUOTA_ENASARCO_TOTALE / 2.0) / 100.0, 2)
    netto = round(provvigioni + iva - ritenuta - enasarco_agente, 2)

    return {
        "provvigioni": round(provvigioni, 2),
        "iva": iva,
        "base_ritenuta_percent": base_ritenuta_percent,
        "ritenuta_acconto": ritenuta,
        "enasarco_agente": enasarco_agente,
        "aliquota_enasarco_totale": _ALIQUOTA_ENASARCO_TOTALE,
        "netto_a_pagare": netto,
        "notes": [
            f"Ritenuta d'acconto ex art. 25-bis D.P.R. 600/1973 sul "
            f"{base_ritenuta_percent:g}% delle provvigioni"
            + (
                " (base ridotta al 20% per l'avvalimento continuativo di dipendenti "
                "o terzi, previa comunicazione al committente)."
                if con_collaboratori
                else " (base ordinaria del 50%)."
            ),
            "Contributo Enasarco complessivo 17% ripartito a metà tra agente e "
            "preponente: in fattura si trattiene la quota agente dell'8,5%, entro "
            "minimali e massimali provvigionali annui della Fondazione (da "
            "verificare per l'anno in corso).",
        ],
        "warnings": [
            "Enasarco si applica agli agenti operanti in forma individuale o di "
            "società di persone; il calcolo non gestisce massimali, FIRR e "
            "indennità di fine rapporto.",
        ],
        "sources": [_FONTE_25BIS, _FONTE_ENASARCO],
    }


def calcola_prestazione_occasionale(payload: Mapping[str, Any]) -> Dict[str, Any]:
    compenso = safe_float(payload.get("occ_compenso"))
    rimborso_spese = safe_float(payload.get("occ_rimborsi"))
    committente_sostituto = clean_text(payload.get("occ_sostituto", "1")) != "0"
    anticipazioni_escluse = clean_text(payload.get("occ_anticipazioni")) == "1"

    if compenso <= 0:
        raise ValueError("Inserisci il compenso lordo pattuito.")
    if rimborso_spese < 0:
        raise ValueError("I rimborsi non possono essere negativi.")

    lordo = compenso + rimborso_spese
    # I rimborsi spese concorrono alla base della ritenuta (art. 25 D.P.R.
    # 600/1973: "compensi comunque denominati"); restano escluse le sole
    # anticipazioni documentate in nome e per conto del committente
    # (R.M. 49/E/2013).
    base_ritenuta = compenso if anticipazioni_escluse else lordo
    ritenuta = round(base_ritenuta * 0.20, 2) if committente_sostituto else 0.0
    bollo = _BOLLO if lordo > _SOGLIA_BOLLO else 0.0
    netto = round(lordo - ritenuta - bollo, 2)

    notes = [
        "Redditi diversi ex art. 67, c. 1, lett. l, TUIR: prestazione senza "
        "abitualità né coordinamento, fuori campo IVA per mancanza del "
        "presupposto soggettivo (art. 5 D.P.R. 633/1972).",
        "Imposta di bollo di 2 euro sulle ricevute di importo superiore a 77,47 "
        "euro (D.P.R. 642/1972, Tariffa, art. 13).",
    ]
    if committente_sostituto:
        if anticipazioni_escluse:
            notes.append(
                "Ritenuta d'acconto 20% sul solo compenso: i rimborsi indicati sono "
                "anticipazioni documentate in nome e per conto del committente, "
                "escluse dalla base (R.M. 49/E/2013)."
            )
        else:
            notes.append(
                "Ritenuta d'acconto 20% su compenso e rimborsi (art. 25 D.P.R. "
                "600/1973: i rimborsi concorrono alla base; le spese inerenti si "
                "deducono in dichiarazione ex art. 71, c. 2, TUIR)."
            )
        notes.append("Il committente sostituto versa la ritenuta con F24 e rilascia la CU.")
    else:
        notes.append(
            "Committente privato non sostituto d'imposta: nessuna ritenuta; il "
            "compenso va dichiarato dal prestatore."
        )

    return {
        "compenso": round(compenso, 2),
        "rimborsi": round(rimborso_spese, 2),
        "lordo": round(lordo, 2),
        "base_ritenuta": round(base_ritenuta if committente_sostituto else 0.0, 2),
        "ritenuta_acconto": ritenuta,
        "bollo": bollo,
        "netto_percepito": netto,
        "notes": notes,
        "warnings": [
            "Oltre 5.000 euro annui complessivi di compensi occasionali scatta "
            "l'obbligo di iscrizione alla gestione separata INPS con contributi "
            "sulla quota eccedente, anche per prestazioni genuinamente occasionali "
            "(art. 44, c. 2, D.L. 269/2003; ripartizione 1/3 prestatore, 2/3 "
            "committente).",
            "Prestazioni ripetute e organizzate possono configurare attività "
            "abituale con obbligo di partita IVA o collaborazione coordinata: "
            "valutare la qualificazione col professionista.",
        ],
        "sources": [_FONTE_25, _FONTE_BOLLO],
    }


def opzioni_gruppi_forfettario() -> list[dict]:
    return [{"value": v["value"], "label": f"{v['label']} — {v['coeff']:g}%"} for v in _COEFFICIENTI]
