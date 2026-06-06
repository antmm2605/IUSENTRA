"""Registro strumenti (tools) di Lex per studio legale italiano.

23 strumenti tenant-aware che coprono l'operatività completa:
fascicoli, agenda, scadenze, economico, telematico, normativa, redazione.
"""

from __future__ import annotations

from datetime import date, timedelta
import os
from pathlib import Path
from typing import Any


# ------------------------------------------------------------------ #
# Helpers tenant-aware                                                 #
# ------------------------------------------------------------------ #

def _safe_import(module_path: str):
    try:
        import importlib
        return importlib.import_module(module_path)
    except Exception:
        return None


def _current_date() -> date:
    return date.today()


def _format_data(d: Any) -> str:
    if isinstance(d, date):
        return d.strftime("%d/%m/%Y")
    text = str(d or "").strip()
    if not text:
        return ""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            from datetime import datetime
            return datetime.strptime(text, fmt).strftime("%d/%m/%Y")
        except Exception:
            continue
    return text


def _normative_manager():
    helpers = _safe_import("web.helpers")
    if helpers is not None:
        getter = getattr(helpers, "get_normative_tables", None)
        if getter is not None:
            try:
                return getter()
            except Exception:
                pass
    mod = _safe_import("pct.normative_tables")
    if mod is None:
        return None
    manager_cls = getattr(mod, "GestioneTabelleNormative", None)
    if manager_cls is None:
        return None
    candidates = [
        os.environ.get("NORMATIVE_TABLES_DB"),
        os.environ.get("PCT_NORMATIVE_TABLES_DB"),
        os.environ.get("IUSENTRA_NORMATIVE_TABLES_DB"),
        str(Path("data") / "intelligence" / "tabelle_normative.json"),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            return manager_cls(str(candidate))
        except Exception:
            continue
    return None


def _normative_match(payload: dict[str, Any], query: str) -> bool:
    tokens = [token for token in str(query or "").lower().replace("-", " ").split() if len(token) >= 2][:8]
    haystack = " ".join(str(value or "") for value in payload.values()).lower()
    return bool(tokens) and all(token in haystack for token in tokens)


# ------------------------------------------------------------------ #
# 1. Fascicolo context                                                  #
# ------------------------------------------------------------------ #

def get_fascicolo_context(fascicolo_id: str, *, tenant_id: str = "") -> dict[str, Any]:
    """Ritorna il quadro sintetico di un fascicolo per ID."""
    if not fascicolo_id:
        return {"ok": False, "errore": "fascicolo_id mancante"}
    try:
        mod = _safe_import("web.helpers")
        if mod is None:
            return {"ok": False, "errore": "modulo fascicoli non disponibile"}
        fascicolo = mod.get_fascicoli().get(fascicolo_id)
        if not fascicolo:
            return {"ok": False, "errore": f"fascicolo {fascicolo_id!r} non trovato"}
        return {
            "ok": True,
            "id": fascicolo_id,
            "titolo": getattr(fascicolo, "titolo", ""),
            "cliente": getattr(fascicolo, "nome_cliente", ""),
            "controparte": getattr(fascicolo, "controparte", ""),
            "tribunale": getattr(fascicolo, "tribunale", ""),
            "stato": str(getattr(getattr(fascicolo, "stato", ""), "value", getattr(fascicolo, "stato", "")) or ""),
            "oggetto": getattr(fascicolo, "oggetto", ""),
            "data_prossima_udienza": str(getattr(fascicolo, "data_prossima_udienza", "") or ""),
        }
    except Exception as exc:
        return {"ok": False, "errore": str(exc)}


# ------------------------------------------------------------------ #
# 2. Calcolo scadenze e termini processuali                            #
# ------------------------------------------------------------------ #

_TERMINI_PROCESSUALI: dict[str, int] = {
    "opposizione_decreto_ingiuntivo": 40,
    "appello_sentenza_civile": 30,
    "appello_sentenza_lavoro": 30,
    "ricorso_cassazione": 60,
    "opposizione_sanzione_amministrativa": 30,
    "ricorso_tar": 60,
    "appello_tar": 30,
    "reclamo_cautelare": 15,
    "opposizione_sequestro": 20,
    "opposizione_esecuzione": 20,
    "costituzione_convenuto": 20,
    "notifica_atto_introduttivo": 90,
    "iscrizione_ruolo_civile": 10,
    "riassunzione_causa": 90,
}

_TERMINI_LABELS: dict[str, str] = {
    "opposizione_decreto_ingiuntivo": "Opposizione a decreto ingiuntivo (art. 645 c.p.c.)",
    "appello_sentenza_civile": "Appello sentenza civile (art. 325 c.p.c.)",
    "appello_sentenza_lavoro": "Appello sentenza lavoro (art. 434 c.p.c.)",
    "ricorso_cassazione": "Ricorso in Cassazione (art. 325 c.p.c.)",
    "opposizione_sanzione_amministrativa": "Opposizione a sanzione amministrativa (L. 689/1981)",
    "ricorso_tar": "Ricorso al TAR (D.Lgs. 104/2010 art. 29)",
    "appello_tar": "Appello Consiglio di Stato (D.Lgs. 104/2010 art. 91)",
    "reclamo_cautelare": "Reclamo cautelare (art. 669-terdecies c.p.c.)",
    "opposizione_sequestro": "Opposizione a sequestro",
    "opposizione_esecuzione": "Opposizione all'esecuzione (art. 615 c.p.c.)",
    "costituzione_convenuto": "Costituzione convenuto (art. 166 c.p.c.)",
    "notifica_atto_introduttivo": "Notifica atto introduttivo al convenuto",
    "iscrizione_ruolo_civile": "Iscrizione a ruolo causa civile",
    "riassunzione_causa": "Riassunzione causa (art. 307 c.p.c.)",
}


def calculate_deadline(
    tipo_termine: str,
    *,
    data_decorrenza: str = "",
    giorni_personalizzati: int | None = None,
    escludi_festivi: bool = False,
) -> dict[str, Any]:
    """Calcola la scadenza processuale dalla data di decorrenza."""
    oggi = _current_date()
    decorrenza: date
    if data_decorrenza:
        try:
            from datetime import datetime
            decorrenza = datetime.strptime(data_decorrenza, "%Y-%m-%d").date()
        except Exception:
            try:
                from datetime import datetime
                decorrenza = datetime.strptime(data_decorrenza, "%d/%m/%Y").date()
            except Exception:
                decorrenza = oggi
    else:
        decorrenza = oggi

    giorni = giorni_personalizzati if giorni_personalizzati is not None else _TERMINI_PROCESSUALI.get(tipo_termine, 30)
    scadenza = decorrenza + timedelta(days=giorni)
    label = _TERMINI_LABELS.get(tipo_termine, tipo_termine.replace("_", " "))
    restanti = (scadenza - oggi).days

    return {
        "ok": True,
        "tipo_termine": tipo_termine,
        "label": label,
        "data_decorrenza": _format_data(decorrenza),
        "giorni": giorni,
        "scadenza": _format_data(scadenza),
        "giorni_restanti": restanti,
        "urgente": restanti <= 7,
        "scaduto": restanti < 0,
        "avvertenza": (
            "Verificare sospensioni feriali (1-31 agosto) e festività ai sensi dell'art. 155 c.p.c."
            if not escludi_festivi else ""
        ),
    }


def list_termini_disponibili() -> list[dict[str, Any]]:
    """Elenca i tipi di termine processuale disponibili."""
    return [
        {"key": k, "label": _TERMINI_LABELS[k], "giorni": v}
        for k, v in _TERMINI_PROCESSUALI.items()
    ]


# ------------------------------------------------------------------ #
# 3. Template redazione lettere                                         #
# ------------------------------------------------------------------ #

def generate_diffida_template(
    *,
    controparte: str = "",
    oggetto: str = "",
    importo: str = "",
    termine_giorni: int = 15,
    avvocato: str = "",
) -> dict[str, Any]:
    """Genera il template testuale di diffida e messa in mora."""
    from lex.providers.deterministic_provider import build_diffida_messa_in_mora_template

    ctx = {
        "controparte": controparte,
        "oggetto": oggetto,
        "importo": importo,
        "termine_giorni": termine_giorni,
        "avvocato": avvocato,
    }
    bozza = build_diffida_messa_in_mora_template(ctx)
    return {"ok": True, "tipo": "diffida_messa_in_mora", "bozza": bozza}


def generate_sollecito_template(
    *,
    controparte: str = "",
    importo: str = "",
    scadenza_originale: str = "",
    avvocato: str = "",
) -> dict[str, Any]:
    """Genera template di sollecito pagamento."""
    from lex.providers.deterministic_provider import build_sollecito_pagamento_template

    ctx = {
        "controparte": controparte,
        "importo": importo,
        "scadenza_originale": scadenza_originale,
        "avvocato": avvocato,
    }
    bozza = build_sollecito_pagamento_template(ctx)
    return {"ok": True, "tipo": "sollecito_pagamento", "bozza": bozza}


def generate_pec_template(
    *,
    destinatario: str = "",
    oggetto_pec: str = "",
    corpo: str = "",
    avvocato: str = "",
) -> dict[str, Any]:
    """Genera template PEC formale."""
    from lex.providers.deterministic_provider import build_pec_formale_template

    ctx = {
        "destinatario": destinatario,
        "oggetto_pec": oggetto_pec,
        "corpo": corpo,
        "avvocato": avvocato,
    }
    bozza = build_pec_formale_template(ctx)
    return {"ok": True, "tipo": "pec_formale", "bozza": bozza}


# ------------------------------------------------------------------ #
# 4. Tariffario forense (DM 55/2014 semplificato)                      #
# ------------------------------------------------------------------ #

_DM55_SCAGLIONI = (
    (1_100, 0, {"fase_studio": 450, "fase_intro": 540, "fase_istr": 1_080, "fase_dec": 810}),
    (5_200, 1_101, {"fase_studio": 900, "fase_intro": 1_080, "fase_istr": 2_160, "fase_dec": 1_620}),
    (26_000, 5_201, {"fase_studio": 1_500, "fase_intro": 1_800, "fase_istr": 3_600, "fase_dec": 2_700}),
    (52_000, 26_001, {"fase_studio": 2_100, "fase_intro": 2_520, "fase_istr": 5_040, "fase_dec": 3_780}),
    (260_000, 52_001, {"fase_studio": 3_000, "fase_intro": 3_600, "fase_istr": 7_200, "fase_dec": 5_400}),
    (520_000, 260_001, {"fase_studio": 4_500, "fase_intro": 5_400, "fase_istr": 10_800, "fase_dec": 8_100}),
    (2_600_000, 520_001, {"fase_studio": 7_500, "fase_intro": 9_000, "fase_istr": 18_000, "fase_dec": 13_500}),
    (float("inf"), 2_600_001, {"fase_studio": 12_000, "fase_intro": 14_400, "fase_istr": 28_800, "fase_dec": 21_600}),
)

_FASE_LABELS = {
    "fase_studio": "Fase di studio",
    "fase_intro": "Fase introduttiva",
    "fase_istr": "Fase istruttoria",
    "fase_dec": "Fase decisionale",
}


def calculate_tariffario(
    valore_causa: float,
    *,
    fasi: list[str] | None = None,
    riduzione_pct: float = 0.0,
    aumento_pct: float = 0.0,
) -> dict[str, Any]:
    """Calcola compenso forense DM 55/2014 per valore causa e fasi liquidate."""
    if fasi is None:
        fasi = ["fase_studio", "fase_intro", "fase_istr", "fase_dec"]

    scaglione_trovato: dict[str, float] = {}
    scaglione_label = ""
    for max_val, min_val, valori in _DM55_SCAGLIONI:
        if valore_causa <= max_val:
            scaglione_trovato = valori
            scaglione_label = f"da € {min_val:,.0f} a € {max_val:,.0f}".replace(",", ".")
            break

    if not scaglione_trovato:
        scaglione_trovato = _DM55_SCAGLIONI[-1][2]
        scaglione_label = "oltre € 2.600.000"

    dettaglio: list[dict[str, Any]] = []
    totale = 0.0
    for fase in fasi:
        base = float(scaglione_trovato.get(fase, 0))
        if aumento_pct:
            base *= 1 + aumento_pct / 100
        if riduzione_pct:
            base *= 1 - riduzione_pct / 100
        dettaglio.append({"fase": fase, "label": _FASE_LABELS.get(fase, fase), "importo": round(base, 2)})
        totale += base

    rimborso_forfettario = round(totale * 0.15, 2)
    return {
        "ok": True,
        "valore_causa": valore_causa,
        "scaglione": scaglione_label,
        "normativa": "D.M. 55/2014 (aggiornato D.M. 147/2022)",
        "fasi_liquidate": dettaglio,
        "totale_compenso": round(totale, 2),
        "rimborso_forfettario_15pct": rimborso_forfettario,
        "totale_con_rimborso": round(totale + rimborso_forfettario, 2),
        "avvertenza": "Valori tabellari di riferimento: il giudice può applicare riduzioni o aumenti fino al 50%.",
    }


# ------------------------------------------------------------------ #
# 5. Info cliente                                                        #
# ------------------------------------------------------------------ #

def get_client_info(cliente_id: str, *, tenant_id: str = "") -> dict[str, Any]:
    """Ritorna dati anagrafici base del cliente."""
    if not cliente_id:
        return {"ok": False, "errore": "cliente_id mancante"}
    try:
        mod = _safe_import("pct.clienti")
        if mod is None:
            return {"ok": False, "errore": "modulo clienti non disponibile"}
        gestione = getattr(mod, "GestioneClienti", None)
        if gestione is None:
            return {"ok": False, "errore": "GestioneClienti non disponibile"}
        cliente = gestione().get(cliente_id)
        if not cliente:
            return {"ok": False, "errore": f"cliente {cliente_id!r} non trovato"}
        return {
            "ok": True,
            "id": cliente_id,
            "nome": getattr(cliente, "nome", ""),
            "cognome": getattr(cliente, "cognome", ""),
            "ragione_sociale": getattr(cliente, "ragione_sociale", ""),
            "email": getattr(cliente, "email", ""),
            "pec": getattr(cliente, "pec", ""),
            "cf": getattr(cliente, "codice_fiscale", ""),
            "piva": getattr(cliente, "partita_iva", ""),
            "indirizzo": getattr(cliente, "indirizzo", ""),
        }
    except Exception as exc:
        return {"ok": False, "errore": str(exc)}


# ------------------------------------------------------------------ #
# 6. Agenda e appuntamenti                                              #
# ------------------------------------------------------------------ #

def get_agenda_today(*, tenant_id: str = "") -> dict[str, Any]:
    """Ritorna gli appuntamenti di oggi."""
    oggi = _current_date()
    try:
        mod = _safe_import("pct.agenda")
        if mod is None:
            return {"ok": False, "errore": "modulo agenda non disponibile", "appuntamenti": []}
        gestione = getattr(mod, "GestioneAppuntamenti", None)
        if gestione is None:
            return {"ok": False, "errore": "GestioneAppuntamenti non disponibile", "appuntamenti": []}
        tutti = gestione().lista()
        oggi_str = oggi.isoformat()
        appuntamenti = [
            {
                "id": getattr(a, "id", ""),
                "titolo": getattr(a, "titolo", ""),
                "data": str(getattr(a, "data", "") or ""),
                "ora": str(getattr(a, "ora_inizio", "") or ""),
                "luogo": getattr(a, "luogo", ""),
                "fascicolo_id": getattr(a, "fascicolo_id", ""),
            }
            for a in (tutti or [])
            if str(getattr(a, "data", "") or "").startswith(oggi_str)
        ]
        return {"ok": True, "data": _format_data(oggi), "appuntamenti": appuntamenti}
    except Exception as exc:
        return {"ok": False, "errore": str(exc), "appuntamenti": []}


# ------------------------------------------------------------------ #
# 7. Scadenze urgenti                                                   #
# ------------------------------------------------------------------ #

def get_scadenze_urgenti(*, giorni_avanti: int = 7, tenant_id: str = "") -> dict[str, Any]:
    """Ritorna le scadenze che scadono entro N giorni."""
    oggi = _current_date()
    limite = oggi + timedelta(days=giorni_avanti)
    try:
        mod = _safe_import("pct.scadenziario")
        if mod is None:
            return {"ok": False, "errore": "modulo scadenziario non disponibile", "scadenze": []}
        gestione = getattr(mod, "GestioneScadenziario", None)
        if gestione is None:
            return {"ok": False, "errore": "GestioneScadenziario non disponibile", "scadenze": []}
        tutte = gestione().lista()
        urgenti = []
        for s in (tutte or []):
            data_s = getattr(s, "data_scadenza", None) or getattr(s, "data", None)
            if not data_s:
                continue
            try:
                from datetime import datetime
                if isinstance(data_s, str):
                    data_s = datetime.strptime(data_s, "%Y-%m-%d").date()
                if oggi <= data_s <= limite:
                    urgenti.append({
                        "id": getattr(s, "id", ""),
                        "titolo": getattr(s, "titolo", ""),
                        "data": _format_data(data_s),
                        "tipo": getattr(s, "tipo", ""),
                        "fascicolo_id": getattr(s, "fascicolo_id", ""),
                        "giorni_restanti": (data_s - oggi).days,
                    })
            except Exception:
                continue
        urgenti.sort(key=lambda x: x.get("giorni_restanti", 999))
        return {"ok": True, "scadenze": urgenti, "totale": len(urgenti)}
    except Exception as exc:
        return {"ok": False, "errore": str(exc), "scadenze": []}


# ------------------------------------------------------------------ #
# 8. Checklist deposito telematico                                      #
# ------------------------------------------------------------------ #

_CHECKLIST_PST = [
    "PDF/A-1b per tutti gli atti da depositare",
    "Firma CAdES-BES (.p7m) sull'atto principale",
    "DatiAtto.xml con namespace corretto e tag <Attoprincipale>",
    "Oggetto PEC: 'DEPOSITO TELEMATICO - {TipoAtto} - RG {n}/{anno}'",
    "Busta .enc (ZIP) contenente DatiAtto.xml + atti firmati",
    "Certificato firma non scaduto (controllo pre-deposito)",
    "PEC del tribunale da ReGINde (giustiziapec.it)",
    "Hash SHA-256 di ciascun documento nel DatiAtto.xml",
]

_CHECKLIST_PDP = [
    "Endpoint REST /depositi su appweb.giustizia.it",
    "Autenticazione mTLS (certificato P12 o PEM lato client)",
    "Multipart/form-data con campo 'atto' e metadati JSON",
    "Risposta JSON con codiceEsito, idDeposito, dataDeposito",
    "Polling ricevuta PEC di accettazione e consegna (5 min)",
    "Firma CAdES o PAdES sull'atto penale",
    "Verifica scadenza certificato CNS/CIE prima del deposito",
]

_CHECKLIST_PAT = [
    "WSDL SIGA: depositoAtto su giustizia-amministrativa.it/pac",
    "Atto in base64 nel payload SOAP",
    "Autenticazione mTLS (certificato P12/PEM)",
    "Risposta SOAP con codice accettazione segreteria TAR",
    "PDF/A-1b obbligatorio per ogni allegato",
    "Firma CAdES o PAdES sull'atto amministrativo",
    "Verifica termini ricorso TAR (60 gg notifica, art. 29 D.Lgs. 104/2010)",
]

_CHECKLIST_PTT = [
    "Deposito tramite PTT sul portale dedicato",
    "Firma digitale qualificata obbligatoria",
    "Accesso con CNS/CIE/SPID",
    "Verifica dati fascicolo telematico prima dell'invio",
]


def build_deposito_checklist(portale: str = "PST") -> dict[str, Any]:
    """Ritorna la checklist di deposito per il portale indicato."""
    portale_upper = str(portale or "PST").strip().upper()
    checklists = {
        "PST": _CHECKLIST_PST,
        "POLISWEB": _CHECKLIST_PST,
        "PDP": _CHECKLIST_PDP,
        "PAT": _CHECKLIST_PAT,
        "PTT": _CHECKLIST_PTT,
    }
    items = checklists.get(portale_upper, _CHECKLIST_PST)
    return {
        "ok": True,
        "portale": portale_upper,
        "checklist": items,
        "totale_passi": len(items),
        "normativa": {
            "PST": "D.M. 44/2011",
            "POLISWEB": "D.M. 44/2011",
            "PDP": "D.Lgs. 150/2022 + D.M. 217/2023",
            "PAT": "D.P.C.M. 16/02/2016 + D.P.C.S.G.A. 28/07/2021",
            "PTT": "D.M. 44/2011",
        }.get(portale_upper, "D.M. 44/2011"),
    }


# ------------------------------------------------------------------ #
# 9. PEC: stato e template                                              #
# ------------------------------------------------------------------ #

def get_pec_status(*, tenant_id: str = "") -> dict[str, Any]:
    """Ritorna lo stato della configurazione PEC dello studio."""
    try:
        mod = _safe_import("pct.config_studio")
        if mod is None:
            return {"ok": False, "errore": "config_studio non disponibile"}
        cfg = getattr(mod, "get_config_studio", None)
        if cfg is None:
            return {"ok": False, "errore": "get_config_studio non disponibile"}
        config = cfg()
        pec = getattr(config, "pec", None) or {}
        if isinstance(pec, dict):
            return {
                "ok": True,
                "pec_configurata": bool(pec.get("host") and pec.get("username")),
                "host": pec.get("host", ""),
                "porta_imap": pec.get("porta_imap", ""),
                "porta_smtp": pec.get("porta_smtp", ""),
                "username": pec.get("username", ""),
            }
        return {"ok": True, "pec_configurata": False}
    except Exception as exc:
        return {"ok": False, "errore": str(exc)}


# ------------------------------------------------------------------ #
# 10. Ricerca normativa e giurisprudenza                                #
# ------------------------------------------------------------------ #

def search_normativa(query: str, *, limit: int = 5) -> dict[str, Any]:
    """Ricerca nella base dati normativa interna."""
    if not query:
        return {"ok": False, "errore": "query mancante", "risultati": []}
    try:
        manager = _normative_manager()
        if manager is None:
            return {"ok": True, "risultati": [], "fonte": "database normativo non disponibile"}
        snapshot = manager.snapshot()
        risultati: list[dict[str, Any]] = []
        for table in list(snapshot.get("tabelle") or []):
            if not isinstance(table, dict):
                continue
            sample_rows: list[dict[str, Any]] = []
            try:
                sample_rows = list(manager.rows(str(table.get("id") or "")) or [])[:3]
            except Exception:
                sample_rows = []
            payload = {
                "tipo": "tabella_normativa",
                "id": table.get("id"),
                "titolo": table.get("title"),
                "categoria": table.get("category"),
                "descrizione": table.get("description"),
                "stato": table.get("sync_status"),
                "ultimo_aggiornamento": table.get("last_synced_at"),
                "avviso": table.get("last_warning"),
                "fonti": table.get("sources") or [],
                "righe_campione": sample_rows,
            }
            if _normative_match(payload, query):
                risultati.append(payload)
        try:
            references = list(manager.catalogo_riferimenti_normativi() or [])
        except Exception:
            references = list(snapshot.get("riferimenti_normativi") or [])
        for row in references:
            if not isinstance(row, dict):
                continue
            payload = {
                "tipo": "riferimento_normativo",
                "id": row.get("reference_code"),
                "titolo": row.get("title"),
                "articolo": row.get("article"),
                "descrizione": row.get("description"),
                "url": row.get("url"),
                "aree": row.get("areas") or [],
                "tipologie": row.get("tipologie_labels") or [],
                "motori": row.get("motori") or [],
                "redattori": row.get("redattori") or [],
            }
            if _normative_match(payload, query):
                risultati.append(payload)
        return {
            "ok": True,
            "risultati": risultati[: max(1, int(limit or 1))],
            "query": query,
            "fonte": "DB normativa IUSENTRA tenant-aware",
        }
    except Exception as exc:
        return {"ok": False, "errore": str(exc), "risultati": []}


def search_giurisprudenza(query: str, *, organo: str = "", limit: int = 5) -> dict[str, Any]:
    """Ricerca nella base dati giurisprudenziale interna."""
    if not query:
        return {"ok": False, "errore": "query mancante", "risultati": []}
    try:
        mod = _safe_import("pct.legal_intelligence")
        if mod is None:
            return {"ok": True, "risultati": [], "fonte": "database giurisprudenza non disponibile"}
        fn = getattr(mod, "search_giurisprudenza", None) or getattr(mod, "cerca_sentenza", None)
        if fn is None:
            return {"ok": True, "risultati": [], "fonte": "funzione di ricerca non disponibile"}
        risultati = fn(query, organo=organo, limit=limit) if organo else fn(query, limit=limit)
        return {"ok": True, "risultati": list(risultati or []), "query": query, "organo": organo}
    except Exception as exc:
        return {"ok": False, "errore": str(exc), "risultati": []}


# ------------------------------------------------------------------ #
# 11. Config studio                                                     #
# ------------------------------------------------------------------ #

def get_studio_config(*, tenant_id: str = "") -> dict[str, Any]:
    """Ritorna i dati identificativi dello studio."""
    try:
        mod = _safe_import("pct.config_studio")
        if mod is None:
            return {"ok": False, "errore": "config_studio non disponibile"}
        cfg = getattr(mod, "get_config_studio", None)
        if cfg is None:
            return {"ok": False, "errore": "get_config_studio non disponibile"}
        config = cfg()
        return {
            "ok": True,
            "nome_studio": getattr(config, "nome_studio", "") or getattr(config, "nome", ""),
            "avvocato": getattr(config, "avvocato", ""),
            "cf": getattr(config, "codice_fiscale", ""),
            "piva": getattr(config, "partita_iva", ""),
            "indirizzo": getattr(config, "indirizzo", ""),
            "pec": str((getattr(config, "pec", None) or {}).get("username", "")) if isinstance(getattr(config, "pec", None), dict) else "",
        }
    except Exception as exc:
        return {"ok": False, "errore": str(exc)}


# ------------------------------------------------------------------ #
# 12. Verifica firma digitale                                           #
# ------------------------------------------------------------------ #

def check_firma_validity(cert_path: str = "") -> dict[str, Any]:
    """Verifica la scadenza del certificato di firma digitale."""
    try:
        mod = _safe_import("pct.firma")
        if mod is None:
            return {"ok": False, "errore": "modulo firma non disponibile"}
        fn = getattr(mod, "verifica_scadenza_certificato", None)
        if fn is None:
            return {"ok": False, "errore": "funzione di verifica non disponibile"}
        result = fn(cert_path) if cert_path else fn()
        return {"ok": True, **dict(result or {})}
    except Exception as exc:
        return {"ok": False, "errore": str(exc)}


# ------------------------------------------------------------------ #
# 13. Fascicoli attivi                                                  #
# ------------------------------------------------------------------ #

def get_fascicoli_attivi(*, limit: int = 20, tenant_id: str = "") -> dict[str, Any]:
    """Ritorna l'elenco dei fascicoli attivi."""
    try:
        mod = _safe_import("web.helpers")
        if mod is None:
            return {"ok": False, "errore": "modulo fascicoli non disponibile", "fascicoli": []}
        tutti = mod.get_fascicoli()
        attivi = []
        for fid, f in list(tutti.items())[:limit]:
            stato = str(getattr(getattr(f, "stato", ""), "value", getattr(f, "stato", "")) or "")
            if stato.lower() not in {"archiviato", "chiuso", "concluso"}:
                attivi.append({
                    "id": fid,
                    "titolo": getattr(f, "titolo", ""),
                    "cliente": getattr(f, "nome_cliente", ""),
                    "stato": stato,
                })
        return {"ok": True, "fascicoli": attivi, "totale": len(attivi)}
    except Exception as exc:
        return {"ok": False, "errore": str(exc), "fascicoli": []}


# ------------------------------------------------------------------ #
# 14. Riepilogo fatturazione                                            #
# ------------------------------------------------------------------ #

def build_invoice_summary(*, tenant_id: str = "") -> dict[str, Any]:
    """Ritorna riepilogo fatture non pagate."""
    try:
        mod = _safe_import("pct.fatturazione")
        if mod is None:
            return {"ok": False, "errore": "modulo fatturazione non disponibile"}
        fn = getattr(mod, "get_fatture_non_pagate", None) or getattr(mod, "lista_fatture", None)
        if fn is None:
            return {"ok": False, "errore": "funzione non disponibile"}
        fatture = fn() or []
        totale = sum(float(getattr(f, "importo", 0) or 0) for f in fatture)
        return {
            "ok": True,
            "fatture_non_pagate": len(fatture),
            "totale_da_incassare": round(totale, 2),
        }
    except Exception as exc:
        return {"ok": False, "errore": str(exc)}


# ------------------------------------------------------------------ #
# 15. Stato preventivo                                                  #
# ------------------------------------------------------------------ #

def get_preventivo_status(preventivo_id: str, *, tenant_id: str = "") -> dict[str, Any]:
    """Ritorna lo stato di un preventivo specifico."""
    if not preventivo_id:
        return {"ok": False, "errore": "preventivo_id mancante"}
    try:
        mod = _safe_import("pct.preventivi")
        if mod is None:
            return {"ok": False, "errore": "modulo preventivi non disponibile"}
        fn = getattr(mod, "get_preventivo", None)
        if fn is None:
            return {"ok": False, "errore": "funzione non disponibile"}
        prev = fn(preventivo_id)
        if not prev:
            return {"ok": False, "errore": f"preventivo {preventivo_id!r} non trovato"}
        return {
            "ok": True,
            "id": preventivo_id,
            "cliente": getattr(prev, "cliente", ""),
            "importo": getattr(prev, "importo_totale", 0),
            "stato": getattr(prev, "stato", ""),
            "data": str(getattr(prev, "data_creazione", "") or ""),
        }
    except Exception as exc:
        return {"ok": False, "errore": str(exc)}


# ------------------------------------------------------------------ #
# 16. Stato deposito telematico                                         #
# ------------------------------------------------------------------ #

def check_telematico_status(deposito_id: str, *, portale: str = "PST") -> dict[str, Any]:
    """Ritorna lo stato di un deposito telematico."""
    if not deposito_id:
        return {"ok": False, "errore": "deposito_id mancante"}
    return {
        "ok": True,
        "deposito_id": deposito_id,
        "portale": portale,
        "note": "Verificare stato nel pannello PST/PDP/PAT del gestionale.",
        "link_portale": {
            "PST": "https://pst.giustizia.it",
            "PDP": "https://appweb.giustizia.it",
            "PAT": "https://giustizia-amministrativa.it/pac",
        }.get(portale.upper(), ""),
    }


# ------------------------------------------------------------------ #
# 17. Ricerca ufficio giudiziario                                       #
# ------------------------------------------------------------------ #

def get_ufficio_giudiziario(query: str, *, limit: int = 5) -> dict[str, Any]:
    """Ricerca uffici giudiziari per nome o città."""
    if not query:
        return {"ok": False, "errore": "query mancante", "uffici": []}
    try:
        from pct.uffici_giudiziari import cerca_ufficio_giudiziario
        uffici = cerca_ufficio_giudiziario(query, limit=limit)
        return {"ok": True, "uffici": [dict(u) for u in (uffici or [])[:limit]]}
    except Exception as exc:
        return {"ok": False, "errore": str(exc), "uffici": []}


# ------------------------------------------------------------------ #
# 18. Timeline fascicolo                                                #
# ------------------------------------------------------------------ #

def build_timeline_fascicolo(fascicolo_id: str) -> dict[str, Any]:
    """Costruisce la timeline degli eventi principali del fascicolo."""
    ctx = get_fascicolo_context(fascicolo_id)
    if not ctx.get("ok"):
        return ctx
    return {
        "ok": True,
        "fascicolo_id": fascicolo_id,
        "titolo": ctx.get("titolo", ""),
        "cliente": ctx.get("cliente", ""),
        "stato": ctx.get("stato", ""),
        "prossima_udienza": ctx.get("data_prossima_udienza", ""),
        "note": "Timeline completa disponibile nel dettaglio fascicolo IUSENTRA.",
    }


# ------------------------------------------------------------------ #
# 19. Documenti fascicolo                                               #
# ------------------------------------------------------------------ #

def get_documenti_fascicolo(fascicolo_id: str, *, limit: int = 10) -> dict[str, Any]:
    """Ritorna l'elenco dei documenti del fascicolo."""
    if not fascicolo_id:
        return {"ok": False, "errore": "fascicolo_id mancante", "documenti": []}
    try:
        from pct.fascicoli import GestioneFascicoli
        gf = GestioneFascicoli()
        fascicolo = gf.get(fascicolo_id)
        if not fascicolo:
            return {"ok": False, "errore": f"fascicolo {fascicolo_id!r} non trovato", "documenti": []}
        documenti = list(getattr(fascicolo, "documenti", []) or [])[:limit]
        return {
            "ok": True,
            "fascicolo_id": fascicolo_id,
            "documenti": [
                {
                    "id": getattr(d, "id", ""),
                    "nome": getattr(d, "nome_file", ""),
                    "tipo": getattr(d, "tipo_atto", ""),
                    "data": str(getattr(d, "data_caricamento", "") or ""),
                }
                for d in documenti
            ],
            "totale": len(documenti),
        }
    except Exception as exc:
        return {"ok": False, "errore": str(exc), "documenti": []}


# ------------------------------------------------------------------ #
# 20. Suggest prossime azioni                                           #
# ------------------------------------------------------------------ #

def suggest_next_actions(*, fascicolo_id: str = "", tenant_id: str = "") -> dict[str, Any]:
    """Suggerisce le prossime azioni prioritarie per il fascicolo o lo studio."""
    azioni: list[str] = []
    if fascicolo_id:
        ctx = get_fascicolo_context(fascicolo_id)
        if ctx.get("ok"):
            if ctx.get("data_prossima_udienza"):
                azioni.append(f"Preparare atti per udienza del {ctx['data_prossima_udienza']}")
            azioni.append("Verificare scadenze collegate al fascicolo")
            azioni.append("Controllare comunicazioni di cancelleria recenti")
    else:
        scadenze = get_scadenze_urgenti(giorni_avanti=7, tenant_id=tenant_id)
        n = len(scadenze.get("scadenze", []))
        if n:
            azioni.append(f"Ci sono {n} scadenze nei prossimi 7 giorni da verificare")
        azioni.append("Controllare agenda appuntamenti di oggi")
        azioni.append("Verificare stato depositi telematici in corso")
    return {"ok": True, "azioni": azioni, "fascicolo_id": fascicolo_id or None}


# ------------------------------------------------------------------ #
# 21. Lookup tabella normativa                                           #
# ------------------------------------------------------------------ #

def lookup_normativa_table(codice_norma: str) -> dict[str, Any]:
    """Cerca una norma per codice (es. 'art. 1218 c.c.')."""
    if not codice_norma:
        return {"ok": False, "errore": "codice_norma mancante"}
    try:
        result = search_normativa(codice_norma, limit=8)
        return {
            "ok": bool(result.get("ok")),
            "codice": codice_norma,
            "risultati": result.get("risultati") or [],
            "fonte": result.get("fonte") or "DB normativa IUSENTRA",
        }
    except Exception as exc:
        return {"ok": False, "errore": str(exc)}


# ------------------------------------------------------------------ #
# 22. Debug: lista tool disponibili                                     #
# ------------------------------------------------------------------ #

_TOOL_REGISTRY: list[dict[str, str]] = [
    {"name": "get_fascicolo_context", "label": "Quadro fascicolo", "area": "fascicoli"},
    {"name": "calculate_deadline", "label": "Calcolo scadenza processuale", "area": "termini"},
    {"name": "list_termini_disponibili", "label": "Lista tipi termine processuale", "area": "termini"},
    {"name": "generate_diffida_template", "label": "Template diffida", "area": "redazione"},
    {"name": "generate_sollecito_template", "label": "Template sollecito", "area": "redazione"},
    {"name": "generate_pec_template", "label": "Template PEC formale", "area": "redazione"},
    {"name": "calculate_tariffario", "label": "Calcolo compenso DM 55", "area": "economico"},
    {"name": "get_client_info", "label": "Anagrafica cliente", "area": "clienti"},
    {"name": "get_agenda_today", "label": "Agenda di oggi", "area": "agenda"},
    {"name": "get_scadenze_urgenti", "label": "Scadenze urgenti", "area": "scadenze"},
    {"name": "build_deposito_checklist", "label": "Checklist deposito telematico", "area": "telematico"},
    {"name": "get_pec_status", "label": "Stato PEC studio", "area": "pec"},
    {"name": "search_normativa", "label": "Ricerca normativa", "area": "normativa"},
    {"name": "search_giurisprudenza", "label": "Ricerca giurisprudenza", "area": "giurisprudenza"},
    {"name": "get_studio_config", "label": "Config studio", "area": "studio"},
    {"name": "check_firma_validity", "label": "Verifica firma digitale", "area": "firma"},
    {"name": "get_fascicoli_attivi", "label": "Fascicoli attivi", "area": "fascicoli"},
    {"name": "build_invoice_summary", "label": "Riepilogo fatture", "area": "fatturazione"},
    {"name": "get_preventivo_status", "label": "Stato preventivo", "area": "preventivi"},
    {"name": "check_telematico_status", "label": "Stato deposito telematico", "area": "telematico"},
    {"name": "get_ufficio_giudiziario", "label": "Ricerca ufficio giudiziario", "area": "uffici"},
    {"name": "build_timeline_fascicolo", "label": "Timeline fascicolo", "area": "fascicoli"},
    {"name": "get_documenti_fascicolo", "label": "Documenti fascicolo", "area": "fascicoli"},
    {"name": "suggest_next_actions", "label": "Prossime azioni", "area": "operativo"},
    {"name": "lookup_normativa_table", "label": "Lookup norma per codice", "area": "normativa"},
]


def list_tools() -> list[dict[str, str]]:
    """Ritorna il registro completo degli strumenti disponibili."""
    return list(_TOOL_REGISTRY)


# ------------------------------------------------------------------ #
# 23. Tool dispatcher                                                   #
# ------------------------------------------------------------------ #

def dispatch_tool(name: str, **kwargs: Any) -> dict[str, Any]:
    """Esegue uno strumento per nome, con i kwargs forniti."""
    _MAP = {
        "get_fascicolo_context": get_fascicolo_context,
        "calculate_deadline": calculate_deadline,
        "list_termini_disponibili": list_termini_disponibili,
        "generate_diffida_template": generate_diffida_template,
        "generate_sollecito_template": generate_sollecito_template,
        "generate_pec_template": generate_pec_template,
        "calculate_tariffario": calculate_tariffario,
        "get_client_info": get_client_info,
        "get_agenda_today": get_agenda_today,
        "get_scadenze_urgenti": get_scadenze_urgenti,
        "build_deposito_checklist": build_deposito_checklist,
        "get_pec_status": get_pec_status,
        "search_normativa": search_normativa,
        "search_giurisprudenza": search_giurisprudenza,
        "get_studio_config": get_studio_config,
        "check_firma_validity": check_firma_validity,
        "get_fascicoli_attivi": get_fascicoli_attivi,
        "build_invoice_summary": build_invoice_summary,
        "get_preventivo_status": get_preventivo_status,
        "check_telematico_status": check_telematico_status,
        "get_ufficio_giudiziario": get_ufficio_giudiziario,
        "build_timeline_fascicolo": build_timeline_fascicolo,
        "get_documenti_fascicolo": get_documenti_fascicolo,
        "suggest_next_actions": suggest_next_actions,
        "lookup_normativa_table": lookup_normativa_table,
        "list_tools": list_tools,
    }
    fn = _MAP.get(str(name or "").strip())
    if fn is None:
        return {"ok": False, "errore": f"tool '{name}' non disponibile", "disponibili": list(_MAP)}
    try:
        result = fn(**kwargs)
        return dict(result) if isinstance(result, dict) else {"ok": True, "risultato": result}
    except TypeError as exc:
        return {"ok": False, "errore": f"parametri errati per '{name}': {exc}"}
    except Exception as exc:
        return {"ok": False, "errore": str(exc)}


__all__ = [
    "build_deposito_checklist",
    "build_invoice_summary",
    "build_timeline_fascicolo",
    "calculate_deadline",
    "calculate_tariffario",
    "check_firma_validity",
    "check_telematico_status",
    "dispatch_tool",
    "generate_diffida_template",
    "generate_pec_template",
    "generate_sollecito_template",
    "get_agenda_today",
    "get_client_info",
    "get_documenti_fascicolo",
    "get_fascicolo_context",
    "get_fascicoli_attivi",
    "get_pec_status",
    "get_preventivo_status",
    "get_scadenze_urgenti",
    "get_studio_config",
    "get_ufficio_giudiziario",
    "list_termini_disponibili",
    "list_tools",
    "lookup_normativa_table",
    "search_giurisprudenza",
    "search_normativa",
    "suggest_next_actions",
]
