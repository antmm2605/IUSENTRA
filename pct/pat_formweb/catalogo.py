"""Catalogo del Formweb PAT: sedi, depositi, schede e liste ufficiali.

Fonti, tutte consultate in sola lettura il 25/09/2026:

- Portale dell'Avvocato v. 1.15.0 (menu «Nuovo deposito», elenco sedi TAR con
  la scrittura del portale, passi iniziali di ogni tipo di deposito);
- Manuale Portali Esterni nuovo SIGA-PAT, cap. 5-8;
- video ufficiale «Form Web» (giustizia-amministrativa.it, «Istruzioni sintetiche
  e video»): schede del deposito ricorso e flusso Genera riepilogo → firma →
  Invia deposito;
- moduli ministeriali XFA (Ricorso e Atto 4.02, Istanza, Richieste segreteria e
  Rimborso 4.01) già archiviati in ``pct/data/pat_moduli``: le liste di scelta
  (tipi di ricorso, esenzioni, materie, organi, modalità di notifica) con i
  codici SIGA si leggono da lì, non si copiano a mano.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

PORTALE = "https://pe.prod.cloud.giustizia-amministrativa.it"
FONTE = {
    "portale": "Portale dell'Avvocato v. 1.15.0",
    "consultatoIl": "2026-09-25",
    "manuale": f"{PORTALE}/assets/pdf/Manuale_Avvocato.pdf",
    "video": "https://www.giustizia-amministrativa.it/web/guest/pillole-e-video",
    "moduli": "Moduli di deposito XFA 4.02/4.01 (documentazione operativa e modulistica)",
}

# codice ufficio del bundle IUSENTRA → (codice sede SIGA del modulo, scrittura del Portale dell'Avvocato)
SEDI: dict[str, tuple[str, str]] = {
    "T010000": ("tar_to", "TAR PIEMONTE - TORINO"), "T010001": ("tar_to", "TAR PIEMONTE - TORINO"),
    "T020000": ("tar_ao", "TAR VALLE D'AOSTA - AOSTA"), "T030000": ("tar_mi", "TAR LOMBARDIA - MILANO"),
    "T030001": ("tar_bs", "TAR LOMBARDIA - BRESCIA"), "T040000": ("tar_ge", "TAR LIGURIA - GENOVA"),
    "T050000": ("tar_tn", "TAR TRENTINO ALTO ADIGE - TRENTO"),
    "T050001": ("tar_bz", "TAR TRENTINO ALTO ADIGE - BOLZANO"), "T060000": ("tar_ve", "TAR VENETO - VENEZIA"),
    "T070000": ("tar_ts", "TAR FRIULI VENEZIA GIULIA - TRIESTE"),
    "T080000": ("tar_bo", "TAR EMILIA-ROMAGNA - BOLOGNA"), "T080001": ("tar_pr", "TAR EMILIA-ROMAGNA - PARMA"),
    "T090000": ("tar_fi", "TAR TOSCANA - FIRENZE"), "T100000": ("tar_pg", "TAR UMBRIA - PERUGIA"),
    "T110000": ("tar_an", "TAR MARCHE - ANCONA"), "T120000": ("tar_rm", "TAR LAZIO - ROMA"),
    "T120001": ("tar_rm", "TAR LAZIO - ROMA"), "T120002": ("tar_lt", "TAR LAZIO - LATINA"),
    "T130000": ("tar_aq", "TAR ABRUZZO - L'AQUILA"), "T130001": ("tar_pe", "TAR ABRUZZO - PESCARA"),
    "T140000": ("tar_cb", "TAR MOLISE - CAMPOBASSO"), "T150000": ("tar_na", "TAR CAMPANIA - NAPOLI"),
    "T150001": ("tar_sa", "TAR CAMPANIA - SALERNO"), "T160000": ("tar_pz", "TAR BASILICATA - POTENZA"),
    "T170000": ("tar_cz", "TAR CALABRIA - CATANZARO"), "T170001": ("tar_rc", "TAR CALABRIA - REGGIO CALABRIA"),
    "T180000": ("tar_pa", "TAR SICILIA - PALERMO"), "T180001": ("tar_ct", "TAR SICILIA - CATANIA"),
    "T190000": ("tar_ca", "TAR SARDEGNA - CAGLIARI"), "T200000": ("tar_ba", "TAR PUGLIA - BARI"),
    "T200001": ("tar_le", "TAR PUGLIA - LECCE"),
    "CDS000000": ("cds", "Consiglio di Stato"), "CGARS0000": ("cgagiur", "CGARS"),
}


def ambito(codice_sede: str) -> str:
    """TAR, CDS o CGARS: la prima scelta della maschera «Autorità giurisdizionale»."""
    return {"cds": "CDS", "cgagiur": "CGARS"}.get(codice_sede, "TAR" if codice_sede.startswith("tar_") else "")


# Tipi di deposito del menu «Nuovo deposito» (manuale § 6.2) con il percorso del portale.
DEPOSITI: tuple[dict[str, Any], ...] = (
    {"id": "ricorso", "nome": "Ricorso", "percorso": "depositi/nuovo/ricorso", "modulo": "deposito_ricorso",
     "passi": ("Depositanti", "Difensore", "Autorità giurisdizionale e ricorrente", "Informazioni generali"),
     "nrg": False},
    {"id": "atto-successivo", "nome": "Atto successivo", "percorso": "depositi/nuovo/atto-successivo",
     "modulo": "deposito_atto", "passi": ("Depositanti", "Difensore", "Autorità giurisdizionale e NRG"), "nrg": True},
    {"id": "documento-successivo", "nome": "Documento successivo", "percorso": "depositi/nuovo/documento-successivo",
     "modulo": "deposito_atto", "passi": ("Depositanti", "Difensore", "Autorità giurisdizionale e NRG"), "nrg": True},
    {"id": "istanze-giudice", "nome": "Istanze al giudice", "percorso": "depositi/nuovo/istanze-giudice",
     "modulo": "deposito_atto", "passi": ("Depositanti", "Difensore", "Autorità giurisdizionale e NRG"), "nrg": True},
    {"id": "richieste-segreteria", "nome": "Richieste alla segreteria", "percorso": "depositi/nuovo/richieste-segreteria",
     "modulo": "richieste_segreteria", "passi": ("Depositanti", "Autorità giurisdizionale e NRG"), "nrg": True},
    {"id": "succ-contr-unificato", "nome": "Successivo contributo unificato",
     "percorso": "depositi/nuovo/succ-contr-unificato", "modulo": "deposito_atto",
     "passi": ("Depositanti", "Difensore", "Autorità giurisdizionale e NRG"), "nrg": True},
    {"id": "succ-notifiche", "nome": "Successivo notifiche", "percorso": "depositi/nuovo/succ-notifiche",
     "modulo": "deposito_atto", "passi": ("Depositanti", "Difensore", "Autorità giurisdizionale e NRG"), "nrg": True},
    {"id": "rimborso", "nome": "Deposito rimborso contributo unificato", "percorso": "depositi/nuovo/rimborso",
     "modulo": "rimborso_contributo_unificato", "passi": ("Depositanti", "Richiedente", "Autorità giurisdizionale"),
     "nrg": True},
)

# Schede del deposito ricorso dopo il salvataggio della bozza (video ufficiale «Form Web»).
SCHEDE_RICORSO = ("Parti", "Ricorso, procura e allegati", "Istanza di fissazione udienza", "Altre istanze",
                  "Segnala istanze/domande", "Notifiche", "Contributo unificato", "Ricorsi connessi")

# «Segnala istanze/domande» del ricorso (video ufficiale; stesse voci della tabella istanze del modulo).
ISTANZE_SEGNALABILI = (
    "Dichiarazione questione unica ex art. 72 c.p.a.", "Domanda cautelare collegiale", "Domanda cautelare monocratica",
    "Domanda di risarcimento del danno", "Istanza di abbreviazione termini",
    "Istanza di liquidazione delle spese al procuratore antistatario",
    "Istanza di notificazione per pubblici proclami art. 41 comma 4 c.p.a.", "Istanza di oscuramento",
    "Istanza di riunione", "Istanza di superamento limiti dimensionali scritti difensivi",
    "Patrocinio a spese dello Stato", "Richiesta istruttoria",
)

CONTRIBUTO = ("Non esente", "Esente", "Patrocinio a spese dello Stato", "Non dovuto", "Prenotazione a debito")
TIPOLOGIE_PARTE = ("Persona fisica", "Persona giuridica", "Amministrazione", "Minore/Incapacita")


def deposito(codice: str) -> dict[str, Any]:
    trovato = next((d for d in DEPOSITI if d["id"] == codice), None)
    if trovato is None:
        raise ValueError("Tipo di deposito Formweb non previsto.")
    return trovato


def link_deposito(codice: str) -> str:
    return f"{PORTALE}/#/{deposito(codice)['percorso']}"


@lru_cache(maxsize=16)
def _opzioni_modulo(modulo: str) -> dict[str, tuple[tuple[str, str], ...]]:
    from pct.pat_xfa_schema import build_pat_xfa_schema_payload

    esito: dict[str, tuple[tuple[str, str], ...]] = {}
    for sezione in build_pat_xfa_schema_payload(modulo).get("sections", []):
        for campo in sezione.get("fields", []):
            voci = tuple((str(o["value"]), str(o["label"]).strip()) for o in campo.get("options") or []
                         if str(o.get("value")) not in {"0", ""})
            if len(voci) > 3 and campo["name"] not in esito:
                esito[campo["name"]] = voci
    return esito


def opzioni(nome: str, modulo: str = "deposito_ricorso") -> list[dict[str, str]]:
    """Una lista ufficiale del modulo (tipi di ricorso, esenzioni, materie…) come [{codice, descrizione}]."""
    return [{"codice": c, "descrizione": d} for c, d in _opzioni_modulo(modulo).get(nome, ())]


def descrizione(nome: str, codice: str, modulo: str = "deposito_ricorso") -> str:
    return next((d for c, d in _opzioni_modulo(modulo).get(nome, ()) if c == codice), "")


def tipi_ricorso(codice_sede: str) -> list[dict[str, str]]:
    """TAR: tipi di ricorso di primo grado; Consiglio di Stato e CGARS: tipi di appello."""
    return opzioni("tipoRicorsoCds" if ambito(codice_sede) in {"CDS", "CGARS"} else "tipoRicorsoTar")


def catalogo() -> dict[str, Any]:
    sedi = {codice: etichetta for codice, etichetta in SEDI.values()}
    return {
        "fonte": FONTE,
        "sedi": [{"codice": c, "descrizione": e, "ambito": ambito(c)} for c, e in sorted(sedi.items(), key=lambda v: v[1])],
        "depositi": [{**d, "passi": list(d["passi"]), "link": link_deposito(d["id"])} for d in DEPOSITI],
        "tipiRicorsoTar": opzioni("tipoRicorsoTar"), "tipiRicorsoCds": opzioni("tipoRicorsoCds"),
        "esenzioniTar": opzioni("listTipoEsenzioneTar"), "esenzioniCds": opzioni("listTipoEsenzioneCds"),
        "materie": opzioni("materia"), "tipologieAmministrazione": opzioni("tipologia"),
        "tipiProvvedimento": opzioni("tipoProvvImpugnatoTar"), "richiesteSegreteria": opzioni("tipoAtto", "richieste_segreteria"),
        "istanze": list(ISTANZE_SEGNALABILI), "contributo": list(CONTRIBUTO), "tipologieParte": list(TIPOLOGIE_PARTE),
        "modalitaNotifica": [v["codice"] for v in opzioni("txtModalita")] or ["PEC", "POSTA", "MANI PROPRIE", "ALTRO", "UNEP"],
    }


__all__ = ["DEPOSITI", "FONTE", "PORTALE", "SEDI", "ambito", "catalogo", "deposito", "descrizione", "link_deposito",
           "opzioni", "tipi_ricorso"]
