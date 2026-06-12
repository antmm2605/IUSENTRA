"""
pct/redazione_suggerimenti.py - Suggerimento del tipo di atto dal fascicolo reale.

Il motore ordina i modelli del compilatore (pct/compilatore_atti.py) usando solo
segnali presenti nel fascicolo: pratica collegata (mappa ufficiale
PRATICA_TO_MODELS), materia (TipoFascicolo), parole chiave di titolo/oggetto/
note e fase del procedimento (R.G. presente = giudizio pendente). Ogni
suggerimento espone i motivi in italiano; la scelta manuale dal catalogo resta
sempre possibile.
"""
from __future__ import annotations

from typing import Any, Iterable, Optional

# Punteggi: la pratica collegata e' il segnale piu' forte, poi le parole chiave,
# poi coerenza di materia e fase.
_PESO_PRATICA = 60
_PESO_KEYWORD = 30
_PESO_MATERIA = 15
_PESO_FASE = 10

# Materia fascicolo (TipoFascicolo) -> aree compilatore coerenti.
_MATERIA_TO_AREE: dict[str, tuple[str, ...]] = {
    "CIVILE": ("CIVILE", "STRAGIUDIZIALE"),
    "PENALE": ("PENALE",),
    "AMMINISTRATIVO": ("AMMINISTRATIVO",),
    "TRIBUTARIO": ("TRIBUTARIO",),
    "STRAGIUDIZIALE": ("STRAGIUDIZIALE",),
    "CONSULENZA": ("STRAGIUDIZIALE",),
    "LAVORO": ("LAVORO", "CIVILE"),
    "FAMIGLIA": ("FAMIGLIA",),
    "SUCCESSIONI": ("CIVILE",),
    "ALTRO": (),
}

# Modelli introduttivi (nessun R.G.) e modelli endoprocessuali (R.G. presente).
_MODELLI_INTRODUTTIVI = {
    "CIV_CIT_001", "CIV_RDI_001", "CIV_SFRINT_001", "CIV_CONVSFR_001", "CIV_RCAUT_001",
    "CIV_PREC_001", "LAV_RIC_001", "LAV_IMPLIC_001", "LAV_PREV_001", "FAM_SEPC_001",
    "FAM_SEPG_001", "FAM_DIVC_001", "FAM_DIVG_001", "FAM_ADS_001", "AMM_RIC_001",
    "TRIB_RIC_001", "PEN_SEGNBASE_001", "STR_DIFF_001", "STR_MM_001", "STR_RDP_001",
}
_MODELLI_ENDOPROCESSUALI = {
    "CIV_COM_001", "CIV_MEM_001", "CIV_CONCL_001", "CIV_REPL_001", "CIV_IST_001",
    "CIV_DEPDOC_001", "LAV_MEM_001", "FAM_MEMO_001", "AMM_MEM_001", "TRIB_MEMILL_001",
    "PEN_MEM_001", "PEN_NOTEUD_001", "PEN_LISTATESTI_001",
}

# Parole chiave (minuscole) -> modelli suggeriti, con etichetta del segnale.
_REGOLE_KEYWORD: tuple[tuple[tuple[str, ...], tuple[str, ...], str], ...] = (
    (("sfratto", "morosit", "finita locazione"), ("CIV_SFRINT_001", "CIV_CONVSFR_001"), "locazione con sfratto o morosita'"),
    (("licenziament",), ("LAV_IMPLIC_001",), "impugnazione di licenziamento"),
    (("differenze retributive", "demansionament", "mobbing", "straining"), ("LAV_RIC_001",), "controversia di lavoro"),
    (("decreto ingiuntivo", "monitorio"), ("CIV_RDI_001",), "ricorso monitorio"),
    (("opposizione a decreto", "opposizione al decreto"), ("CIV_OPPDI_001",), "opposizione a decreto ingiuntivo"),
    (("recupero credit", "fattur", "insolut", "mancato pagamento"), ("CIV_RDI_001", "STR_RDP_001"), "recupero del credito"),
    (("preliminare", "compromesso", "rogito", "caparra"), ("CIV_CIT_001",), "contratto preliminare immobiliare"),
    (("risoluzione", "inadempiment"), ("CIV_CIT_001", "STR_DIFF_001"), "inadempimento contrattuale"),
    (("risarciment", "danni", "sinistro"), ("CIV_CIT_001", "STR_DIFF_001"), "domanda risarcitoria"),
    (("sinistro stradale", "incidente stradale"), ("CIV_CIT_001",), "sinistro stradale"),
    (("separazione consensuale",), ("FAM_SEPC_001",), "separazione consensuale"),
    (("separazione",), ("FAM_SEPG_001", "FAM_SEPC_001"), "separazione"),
    (("divorzio congiunto",), ("FAM_DIVC_001",), "divorzio congiunto"),
    (("divorzio",), ("FAM_DIVG_001", "FAM_DIVC_001"), "divorzio"),
    (("affidament", "responsabilita genitoriale", "mantenimento figli"), ("FAM_AFF_001",), "affidamento e responsabilita' genitoriale"),
    (("amministrazione di sostegno", "amministratore di sostegno"), ("FAM_ADS_001",), "amministrazione di sostegno"),
    (("precetto",), ("CIV_PREC_001",), "atto di precetto"),
    (("pignoramento presso terzi",), ("CIV_PPT_001",), "pignoramento presso terzi"),
    (("pignorament",), ("CIV_PPT_001", "CIV_PIGBASE_001"), "esecuzione forzata"),
    (("opposizione all'esecuzione", "opposizione esecuzione"), ("CIV_OPESE_001",), "opposizione all'esecuzione"),
    (("atti esecutivi",), ("CIV_OPATTESE_001",), "opposizione agli atti esecutivi"),
    (("cautelare", "urgenza", "700"), ("CIV_RCAUT_001",), "tutela cautelare o d'urgenza"),
    (("querela", "denuncia"), ("PEN_SEGNBASE_001",), "querela o denuncia"),
    (("parte civile",), ("PEN_PARTECIVBASE_001",), "costituzione di parte civile"),
    (("nomina difensore",), ("PEN_NOM_001",), "nomina del difensore"),
    (("dissequestro", "sequestr"), ("PEN_DISSEQ_001",), "istanza di dissequestro"),
    (("tar", "provvedimento amministrativo", "annullamento"), ("AMM_RIC_001",), "impugnazione di provvedimento amministrativo"),
    (("cartella", "avviso di accertamento", "agenzia delle entrate", "tributar"), ("TRIB_RIC_001",), "atto impositivo da impugnare"),
    (("diffida",), ("STR_DIFF_001",), "diffida stragiudiziale"),
    (("messa in mora",), ("STR_MM_001",), "costituzione in mora"),
    (("transazione", "accordo bonario", "proposta transattiva"), ("STR_ATR_001", "STR_PTR_001"), "definizione transattiva"),
    (("condomini", "delibera assembleare"), ("CIV_CIT_001",), "controversia condominiale"),
    (("oneri condominiali",), ("CIV_RDI_001",), "recupero oneri condominiali"),
    (("usucapione", "servitu", "regolamento di confini", "rivendica"), ("CIV_CIT_001",), "diritti reali"),
    (("spoglio", "reintegrazione", "manutenzione del possesso"), ("CIV_RCAUT_001", "CIV_CIT_001"), "tutela possessoria"),
    (("eredit", "testament", "divisione ereditaria", "legittima"), ("CIV_CIT_001",), "materia successoria"),
    (("comparsa", "costituzione e risposta"), ("CIV_COM_001",), "costituzione in giudizio"),
    (("appello",), ("CIV_APP_001",), "impugnazione in appello"),
    (("sfratto per finita locazione",), ("CIV_SFRINT_001",), "finita locazione"),
)

_MODELLI_FALLBACK_PER_AREA: dict[str, tuple[str, ...]] = {
    "CIVILE": ("CIV_CIT_001", "CIV_RDI_001", "CIV_COM_001"),
    "PENALE": ("PEN_NOM_001", "PEN_MEM_001"),
    "AMMINISTRATIVO": ("AMM_RIC_001",),
    "TRIBUTARIO": ("TRIB_RIC_001",),
    "LAVORO": ("LAV_RIC_001",),
    "FAMIGLIA": ("FAM_SEPG_001", "FAM_AFF_001"),
    "STRAGIUDIZIALE": ("STR_DIFF_001", "STR_PAR_001"),
}


def _testo_fascicolo(fascicolo: Any) -> str:
    pezzi = []
    for nome in ("titolo", "oggetto", "note", "area_pratica", "tipo_procedimento", "procedura_operativa_nome"):
        valore = getattr(fascicolo, nome, "") or ""
        if hasattr(valore, "value"):
            valore = valore.value
        pezzi.append(str(valore))
    return " ".join(pezzi).lower()


def _materia(fascicolo: Any) -> str:
    tipo = getattr(fascicolo, "tipo", "")
    if hasattr(tipo, "value"):
        tipo = tipo.value
    return str(tipo or "").strip().upper()


def _etichetta_pratica(id_pratica: str) -> str:
    return str(id_pratica or "").replace("_", " ").strip()


def suggerisci_modelli(fascicolo: Any, *, limite: int = 6) -> list[dict[str, Any]]:
    """Modelli ordinati per pertinenza con motivazione leggibile.

    Restituisce: [{code, name, area, areaLabel, score, motivi: [str]}].
    """
    try:
        from pct.compilatore_atti import AREA_LABELS, MODEL_INDEX, PRATICA_TO_MODELS
    except Exception:
        return []

    punteggi: dict[str, int] = {}
    motivi: dict[str, list[str]] = {}

    def aggiungi(codici: Iterable[str], punti: int, motivo: str) -> None:
        for posizione, codice in enumerate(codici):
            if codice not in MODEL_INDEX:
                continue
            punteggi[codice] = punteggi.get(codice, 0) + max(punti - posizione * 5, 5)
            elenco = motivi.setdefault(codice, [])
            if motivo not in elenco:
                elenco.append(motivo)

    materia = _materia(fascicolo)
    testo = _testo_fascicolo(fascicolo)
    rg_presente = bool(str(getattr(fascicolo, "numero_rg", "") or "").strip())

    id_pratica = str(getattr(fascicolo, "id_pratica", "") or "").strip()
    if id_pratica and id_pratica in PRATICA_TO_MODELS:
        aggiungi(
            PRATICA_TO_MODELS[id_pratica],
            _PESO_PRATICA,
            f"Pratica collegata al fascicolo: {_etichetta_pratica(id_pratica)}.",
        )

    for parole, codici, etichetta in _REGOLE_KEYWORD:
        parola_trovata = next((parola for parola in parole if parola in testo), "")
        if parola_trovata:
            aggiungi(codici, _PESO_KEYWORD, f"Nel fascicolo risulta {etichetta} («{parola_trovata}»).")

    aree_coerenti = _MATERIA_TO_AREE.get(materia, ())
    if aree_coerenti:
        for codice, modello in MODEL_INDEX.items():
            if modello.get("area") in aree_coerenti and codice in punteggi:
                punteggi[codice] += _PESO_MATERIA
                etichetta_materia = materia.replace("_", " ").title()
                motivo_materia = f"Coerente con la materia del fascicolo: {etichetta_materia}."
                if motivo_materia not in motivi[codice]:
                    motivi[codice].append(motivo_materia)

    if not punteggi and aree_coerenti:
        for area in aree_coerenti:
            aggiungi(
                _MODELLI_FALLBACK_PER_AREA.get(area, ()),
                _PESO_MATERIA,
                f"Atto tipico per la materia del fascicolo ({AREA_LABELS.get(area, area.title())}).",
            )

    for codice in list(punteggi):
        if rg_presente and codice in _MODELLI_ENDOPROCESSUALI:
            punteggi[codice] += _PESO_FASE
            motivi[codice].append("Giudizio gia' iscritto a ruolo (R.G. presente nel fascicolo).")
        elif not rg_presente and codice in _MODELLI_INTRODUTTIVI:
            punteggi[codice] += _PESO_FASE
            motivi[codice].append("Nessun R.G. nel fascicolo: fase introduttiva.")

    ordinati = sorted(punteggi.items(), key=lambda item: (-item[1], item[0]))
    risultato: list[dict[str, Any]] = []
    for codice, punteggio in ordinati[: max(1, int(limite))]:
        modello = MODEL_INDEX.get(codice) or {}
        risultato.append(
            {
                "code": codice,
                "name": str(modello.get("name") or codice),
                "area": str(modello.get("area") or ""),
                "areaLabel": AREA_LABELS.get(str(modello.get("area") or ""), str(modello.get("area") or "").title()),
                "score": punteggio,
                "motivi": motivi.get(codice, []),
            }
        )
    return risultato


def catalogo_per_scelta_manuale() -> list[dict[str, Any]]:
    """Catalogo completo raggruppato per area per la scelta manuale nel wizard."""
    try:
        from pct.compilatore_atti import modelli_per_area
    except Exception:
        return []
    gruppi: list[dict[str, Any]] = []
    for gruppo in modelli_per_area():
        modelli = [
            {"code": str(modello.get("code") or ""), "name": str(modello.get("name") or "")}
            for modello in gruppo.get("models", [])
            if modello.get("code")
        ]
        if modelli:
            gruppi.append({"area": gruppo.get("area", ""), "label": gruppo.get("label", ""), "modelli": modelli})
    return gruppi
