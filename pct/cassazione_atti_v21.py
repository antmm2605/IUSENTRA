"""Atti di parte Cassazione presenti negli schemi v21 e non ancora nel catalogo depositi.

Fonte tecnica: PST, XSD_Cassazione_20260227 (Processo Telematico di legittimita - Schemi XSD
v.21), `docs/specs/ministero/parte/parte_v21/Parte-cassazione.xsd`. Le radici sono state
introdotte dal Ministero con le versioni v14 (L. 197/2022), v16 (revocazione, errore materiale,
udienza) e v17 (oscuramento). Il catalogo Studio Telematico decompilato non le contiene.

PREDISPOSTI, NON ATTIVI: per decisione dello studio questi atti restano fuori dal catalogo e dal
generatore finche `CASSAZIONE_ATTI_V21_ATTIVI` e False. L'attivazione richiede la checklist in
`docs/specs/ministero/CASSAZIONE_ATTI_V21_PREDISPOSTI.md` (prova sulla macchina reale e
aggiornamento delle attese dell'audit del catalogo).
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

CASSAZIONE_ATTI_V21_ATTIVI = False
CASSAZIONE_ATTI_V21_SOURCE = "xsd_ministeriale_cassazione_v21"
CASSAZIONE_ATTI_V21_NON_ATTIVI_MESSAGE = (
    "Questo atto della Corte di Cassazione è predisposto ma non ancora attivato in IUSENTRA: "
    "non può essere preparato né depositato."
)

ROOTS_ISTANZE = frozenset(
    {
        "IstanzaSospensioneExL197_2022",
        "ProduzionePagamentoExL197_2022",
        "IstanzaAnticipazioneUdienza",
        "IstanzaTrattazionePubblicaUdienza",
    }
)
ROOT_OSCURAMENTO = "IstanzaOscuramento"
ROOTS_INTRODUTTIVI = frozenset({"RicorsoErroreMateriale", "RevocazioneExArt391ter", "RevocazioneExArt391quater"})
CASSAZIONE_ATTI_V21_ROOTS = ROOTS_ISTANZE | ROOTS_INTRODUTTIVI | {ROOT_OSCURAMENTO}

# Motivi di revocazione (tipi-base.xsd v21): contenitore, elemento e tipo del numero di articolo.
MOTIVI_REVOCAZIONE = {
    "RevocazioneExArt391ter": ("MotiviRevocazione391Ter", "MotivoRevocazione391Ter", "Art395Num"),
    "RevocazioneExArt391quater": ("MotiviRevocazione391Quater", "MotivoRevocazione391Quater", "Art391QuaterNum"),
}

_CATEGORIA_ENDO = "Atti endo-processuali"
_CATEGORIA_INTRO = "Atti introduttivi"

# Definizione di ogni atto: radice, variabile, etichetta, categoria, base normativa e dati richiesti.
_ATTI: tuple[dict[str, Any], ...] = (
    {
        "root": "IstanzaSospensioneExL197_2022",
        "text": "Istanza di sospensione per definizione agevolata ex L. 197/2022 (Corte di Cassazione)",
        "categoria": _CATEGORIA_ENDO,
        "base_normativa": "L. 29 dicembre 2022, n. 197, art. 1, comma 197 (definizione agevolata delle controversie tributarie)",
        "schema_da": "v14",
    },
    {
        "root": "ProduzionePagamentoExL197_2022",
        "text": "Definizione agevolata: produzione del pagamento ex L. 197/2022 (Corte di Cassazione)",
        "categoria": _CATEGORIA_ENDO,
        "base_normativa": "L. 29 dicembre 2022, n. 197, art. 1, commi 186-203 (definizione agevolata delle controversie tributarie)",
        "schema_da": "v14",
    },
    {
        "root": "IstanzaAnticipazioneUdienza",
        "text": "Istanza di anticipazione dell'udienza (Corte di Cassazione)",
        "categoria": _CATEGORIA_ENDO,
        "base_normativa": "Schema XSD Cassazione v21, atto IstanzaAnticipazioneUdienza",
        "schema_da": "v16",
    },
    {
        "root": "IstanzaTrattazionePubblicaUdienza",
        "text": "Istanza di trattazione in pubblica udienza (Corte di Cassazione)",
        "categoria": _CATEGORIA_ENDO,
        "base_normativa": "Schema XSD Cassazione v21, atto IstanzaTrattazionePubblicaUdienza (da protocollo di intesa)",
        "schema_da": "v16",
    },
    {
        "root": "IstanzaOscuramento",
        "text": "Istanza di oscuramento dei dati identificativi (Corte di Cassazione)",
        "categoria": _CATEGORIA_ENDO,
        "base_normativa": "D.Lgs. 30 giugno 2003, n. 196, art. 52 (dati identificativi degli interessati)",
        "schema_da": "v17",
    },
    {
        "root": "RicorsoErroreMateriale",
        "text": "Ricorso per correzione di errore materiale (Corte di Cassazione)",
        "categoria": _CATEGORIA_INTRO,
        "base_normativa": "c.p.c., art. 391-bis (correzione degli errori materiali dei provvedimenti della Corte)",
        "schema_da": "v16",
        "introduttivo": True,
    },
    {
        "root": "RevocazioneExArt391ter",
        "text": "Ricorso per revocazione ex art. 391-ter c.p.c. (Corte di Cassazione)",
        "categoria": _CATEGORIA_INTRO,
        "base_normativa": "c.p.c., art. 391-ter e art. 395, primo comma, nn. 1, 2, 3 e 6",
        "schema_da": "v16",
        "introduttivo": True,
    },
    {
        "root": "RevocazioneExArt391quater",
        "text": "Ricorso per revocazione ex art. 391-quater c.p.c. (Corte di Cassazione)",
        "categoria": _CATEGORIA_INTRO,
        "base_normativa": "c.p.c., art. 391-quater (revocazione per contrarietà alla CEDU), introdotto dal D.Lgs. 149/2022",
        "schema_da": "v16",
        "introduttivo": True,
    },
)

CASSAZIONE_ATTI_V21_KEYS = frozenset(f"Parte_CASSAZIONE::{atto['root']}" for atto in _ATTI)
CASSAZIONE_ATTI_V21_INTRODUTTIVI_KEYS = frozenset(
    f"Parte_CASSAZIONE::{atto['root']}" for atto in _ATTI if atto.get("introduttivo")
)


def cassazione_atti_v21_attivi() -> bool:
    return bool(CASSAZIONE_ATTI_V21_ATTIVI)


def _variable(root: str) -> str:
    return root[:1].lower() + root[1:]


def _raw_entry(atto: dict[str, Any]) -> dict[str, Any]:
    root = atto["root"]
    macro = "Corte di Cassazione (civile)"
    introduttivo = bool(atto.get("introduttivo"))
    required = ["IndiceBusta", "AttoPrincipale.id", "Allegati in IndiceBusta"]
    required += (
        ["AnagraficaProcedimento", "Ruolo", "Ufficio giudiziario", "ContributoUnificato"]
        if introduttivo
        else ["RiferimentoProcedimento"]
    )
    return {
        "key": f"Parte_CASSAZIONE::{root}",
        "text": atto["text"],
        "macro": macro,
        "categoria": atto["categoria"],
        "path": f"{macro} > {atto['categoria']} > {atto['text']}",
        "prefix": "Parte_CASSAZIONE::",
        "channel": "Cassazione civile",
        "catalog_override_source": CASSAZIONE_ATTI_V21_SOURCE,
        "base_normativa": atto["base_normativa"],
        "schema_ministeriale_da": atto["schema_da"],
        "datiatto_methods": [],
        "datiatto_roots": [{"variable": _variable(root), "type": f"ParteCassazione.{root}"}],
        "datiatto_required_data": required,
        "deposit_menu_flags": (
            {"VisualizzaAnagraficaProcedimento": True, "needProcura": True, "needContributoUnificato": True}
            if introduttivo
            else {}
        ),
        "deposit_fixed_object_codes": [],
        "deposit_controls": [],
        "deposit_combo_sources": [],
        "deposit_assignments": [],
    }


def cassazione_atti_v21_raw_entries() -> list[dict[str, Any]]:
    """Voci del catalogo depositi, nello stesso formato del catalogo decompilato."""
    return [deepcopy(_raw_entry(atto)) for atto in _ATTI]


def catalog_raw_with_cassazione_v21(raw: dict[str, Any]) -> dict[str, Any]:
    """Aggiunge gli atti v21 al catalogo solo se attivati; altrimenti restituisce il catalogo invariato."""
    if not cassazione_atti_v21_attivi():
        return raw
    merged = dict(raw)
    known = {str(item.get("key") or "") for item in raw.get("entries") or [] if isinstance(item, dict)}
    extra = [entry for entry in cassazione_atti_v21_raw_entries() if entry["key"] not in known]
    merged["entries"] = [*(raw.get("entries") or []), *extra]
    counts = dict(raw.get("counts") or {})
    macroareas = dict(counts.get("macroareas") or {})
    categories = dict(counts.get("categories") or {})
    for entry in extra:
        macroareas[entry["macro"]] = int(macroareas.get(entry["macro"]) or 0) + 1
        categories[entry["categoria"]] = int(categories.get(entry["categoria"]) or 0) + 1
    counts["macroareas"] = macroareas
    counts["categories"] = categories
    counts["total_deposit_types"] = int(counts.get("total_deposit_types") or 0) + len(extra)
    merged["counts"] = counts
    return merged


__all__ = [
    "CASSAZIONE_ATTI_V21_ATTIVI",
    "CASSAZIONE_ATTI_V21_INTRODUTTIVI_KEYS",
    "CASSAZIONE_ATTI_V21_KEYS",
    "CASSAZIONE_ATTI_V21_NON_ATTIVI_MESSAGE",
    "CASSAZIONE_ATTI_V21_ROOTS",
    "CASSAZIONE_ATTI_V21_SOURCE",
    "MOTIVI_REVOCAZIONE",
    "ROOTS_INTRODUTTIVI",
    "ROOTS_ISTANZE",
    "ROOT_OSCURAMENTO",
    "cassazione_atti_v21_attivi",
    "cassazione_atti_v21_raw_entries",
    "catalog_raw_with_cassazione_v21",
]
