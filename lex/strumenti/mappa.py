"""Mappa degli strumenti di Lex, generata dal codice.

Per ogni fonte d'informazione interrogabile da Lex la mappa dice nome, contenuto, parametri, permessi, se contiene
dati dello studio, quali funzioni la leggono davvero (con la loro firma), tempo tipico ed esempio di domanda.
Le schede (``lex.strumenti.schede``) aggiungono solo ciò che il codice non sa dire; il resto si ricava qui da:

- registro delle sorgenti operative (``lex.operational_knowledge.source_registry``): permessi, tool deterministici
  dichiarati e se sono implementati in ``OperationalKnowledgeTools``;
- adattatori del retrieval (``lex/retrieval/sources``: ogni classe con ``search``);
- registro dei tool Lex (``lex.tools.registry``);
- calcolatori di Strumenti legali (``pct.calcolatori.schema`` e ``metodi``, titoli da ``catalogo_moduli``);
- codici Normattiva riconosciuti (``lex.testi_ufficiali.CODICI``) e serie della Gazzetta (``pct.gazzetta.serie``).

Uso: ``python -m lex.strumenti.genera`` riscrive ``lex/strumenti/mappa.json``; il test della mappa confronta il file
con la rigenerazione e fallisce se il codice ha una fonte che la mappa non conosce.
"""
from __future__ import annotations

import ast
import importlib
import inspect
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from .schede import FUORI_MAPPA, SCHEDE, Scheda

SCHEMA = "iusentra.lex_mappa_strumenti.v1"
QUI = Path(__file__).resolve().parent
FILE_MAPPA = QUI / "mappa.json"
_SORGENTI_RETRIEVAL = QUI.parent / "retrieval" / "sources"


# ---------------------------------------------------------------------------------------------- lettura del codice
def _risolvi(riferimento: str) -> Any:
    modulo, _, percorso = riferimento.partition(":")
    oggetto: Any = importlib.import_module(modulo)
    for parte in percorso.split(".") if percorso else ():
        oggetto = getattr(oggetto, parte)
    return oggetto


def _firma(oggetto: Any) -> str:
    try:
        return str(inspect.signature(oggetto))
    except (TypeError, ValueError):
        return ""


def _prima_riga(oggetto: Any) -> str:
    testo = inspect.getdoc(oggetto) or ""
    return testo.strip().splitlines()[0] if testo.strip() else ""


def funzione(riferimento: str) -> dict[str, Any]:
    """La funzione nel codice: esiste, firma e prima riga della documentazione."""
    try:
        oggetto = _risolvi(riferimento)
    except Exception as exc:  # il test della mappa segnala il riferimento morto
        return {"riferimento": riferimento, "esiste": False, "errore": type(exc).__name__}
    return {"riferimento": riferimento, "esiste": True, "firma": _firma(oggetto), "descrizione": _prima_riga(oggetto)}


def adattatori_nel_codice() -> dict[str, str]:
    """Le classi con metodo ``search`` dei moduli di ``lex/retrieval/sources`` e il loro modulo (lettura statica)."""
    trovati: dict[str, str] = {}
    for file in sorted(_SORGENTI_RETRIEVAL.glob("*.py")):
        albero = ast.parse(file.read_text(encoding="utf-8"))
        for nodo in albero.body:
            if isinstance(nodo, ast.ClassDef) and not nodo.name.startswith("_") and any(
                isinstance(m, ast.FunctionDef) and m.name == "search" for m in nodo.body
            ):
                trovati[nodo.name] = f"lex.retrieval.sources.{file.stem}"
    return trovati


def sorgenti_registro() -> dict[str, Any]:
    from lex.operational_knowledge.source_registry import DEFAULT_SOURCE_DEFINITIONS

    return {s.source_id: s for s in DEFAULT_SOURCE_DEFINITIONS}


def tool_lex() -> dict[str, Any]:
    from lex.tools.registry import LexToolRegistry

    return {d["tool_name"]: d for d in LexToolRegistry().list_tools()}


def calcolatori() -> dict[str, dict[str, Any]]:
    """Ogni calcolatore con modulo dichiarato: titolo, categoria, metodo e campi (nome, tipo, scelte ammesse)."""
    from pct.calcolatori.metodi import TOOL_METHODS
    from pct.calcolatori.schema import SCHEMI_CALCOLATORI
    from pct.strumenti_legali import GestioneStrumentiLegali

    moduli = {v["id"]: v for v in GestioneStrumentiLegali.catalogo_moduli()}
    try:  # le scelte che i calcolatori prendono dai cataloghi del dominio (materie DM 55/2014, categorie CU, ...)
        from pct.calcolatori.metodi import sorgenti_opzioni

        dinamiche = {k: [o for o in v if isinstance(o, dict) and o.get("value") not in (None, "")]
                     for k, v in sorgenti_opzioni(GestioneStrumentiLegali()).items()}
    except Exception:
        dinamiche = {}
    uscita: dict[str, dict[str, Any]] = {}
    for ident in sorted(SCHEMI_CALCOLATORI):
        schema = SCHEMI_CALCOLATORI[ident]
        metodo = TOOL_METHODS.get(ident, "")
        campi = {}
        for campo in schema.get("campi", []):
            voce: dict[str, Any] = {"tipo": campo.get("type", "text"), "etichetta": campo.get("label", "")}
            opzioni = campo.get("options") if isinstance(campo.get("options"), list) else None
            if campo.get("options_from"):
                voce["valori_da"] = str(campo["options_from"])
                opzioni = dinamiche.get(voce["valori_da"], opzioni)
            if opzioni is not None:
                voce["valori"] = [str(o.get("value")) for o in opzioni if isinstance(o, dict)]
                voce["etichette"] = {str(o.get("value")): str(o.get("label") or o.get("value")) for o in opzioni
                                     if isinstance(o, dict)}
            campi[campo["name"]] = voce
        uscita[ident] = {
            "titolo": moduli.get(ident, {}).get("title", ident),
            "categoria": moduli.get(ident, {}).get("categoria", ""),
            "metodo": f"pct.strumenti_legali:GestioneStrumentiLegali.{metodo}" if metodo else "",
            "metodo_esiste": bool(metodo) and hasattr(GestioneStrumentiLegali, metodo),
            "campi": campi,
        }
    return uscita


def codici_normattiva() -> list[dict[str, Any]]:
    from lex.testi_ufficiali import CODICI

    return [{"chiave": c.chiave, "etichetta": c.etichetta, "sinonimi": list(c.sinonimi)} for c in CODICI]


def serie_gazzetta() -> list[str]:
    from pct.gazzetta.serie import SERIE

    return [s.codice for s in SERIE]


# ---------------------------------------------------------------------------------------------- costruzione
def _parametri(scheda: Scheda, valori_da: dict[str, list[str]]) -> dict[str, dict[str, Any]]:
    uscita = {}
    for nome, spec in scheda.parametri.items():
        voce = dict(spec)
        if voce.get("valori_da") in valori_da and voce.get("tipo") == "scelta":
            voce["valori"] = list(valori_da[voce["valori_da"]])
        uscita[nome] = voce
    return uscita


def _funzioni_della_superficie(api_surface: str) -> set[str]:
    """Le funzioni del modulo Python indicato come superficie della sorgente (es. ``lex.tools.x.dispatch_tool``)."""
    testo = str(api_surface or "").strip()
    if not re.fullmatch(r"[a-z_][\w.]*", testo) or "." not in testo:
        return set()
    try:
        modulo = importlib.import_module(testo.rsplit(".", 1)[0])
    except Exception:
        return set()
    return {n for n, _ in inspect.getmembers(modulo, inspect.isfunction)}


def _voce(scheda: Scheda, registro: dict[str, Any], tools: dict[str, Any], valori_da: dict[str, list[str]],
          implementati: set[str]) -> dict[str, Any]:
    permessi: list[str] = list(scheda.permessi)
    tool_dichiarati: list[dict[str, Any]] = []
    for sid in scheda.sorgenti_registro:
        sorgente = registro.get(sid)
        if sorgente is None:
            continue
        permessi += [p for p in sorgente.required_permissions if p not in permessi]
        altrove = _funzioni_della_superficie(sorgente.api_surface)
        for nome in sorgente.deterministic_tools:
            tool_dichiarati.append({"sorgente": sid, "tool": nome, "implementato": nome in implementati or nome in altrove})
    for nome in scheda.tool_lex:
        descr = tools.get(nome)
        if descr:
            permessi += [p for p in descr.get("permissions", []) if p not in permessi]
    funzioni = [funzione(r) for r in scheda.funzioni]
    return {
        "nome": scheda.nome,
        "titolo": scheda.titolo,
        "gruppo": scheda.gruppo,
        "contenuto": scheda.contenuto,
        "parametri": _parametri(scheda, valori_da),
        "permessi": permessi,
        "dati_dello_studio": scheda.dati_dello_studio,
        "collegata_a_lex": scheda.collegata_a_lex,
        "funzioni": funzioni,
        "sorgenti_registro": list(scheda.sorgenti_registro),
        "tool_dichiarati": tool_dichiarati,
        "adattatori": list(scheda.adattatori),
        "tool_lex": list(scheda.tool_lex),
        "tempo_tipico": scheda.tempo_tipico,
        "esempio": scheda.esempio,
        "segnali": list(scheda.segnali),
        "nota": scheda.nota,
    }


def costruisci_mappa() -> dict[str, Any]:
    from lex.operational_knowledge.tools import OperationalKnowledgeTools

    registro = sorgenti_registro()
    tools = tool_lex()
    calc = calcolatori()
    codici = codici_normattiva()
    valori_da = {"calcolatori": sorted(calc), "serie_gazzetta": serie_gazzetta()}
    # Un tool dichiarato è implementato se è un metodo di OperationalKnowledgeTools o un tool del registro Lex.
    implementati = {n for n, _ in inspect.getmembers(OperationalKnowledgeTools, inspect.isfunction)} | set(tools)
    strumenti = [_voce(s, registro, tools, valori_da, implementati) for s in SCHEDE]
    return {
        "schema": SCHEMA,
        "strumenti": strumenti,
        "calcolatori": calc,
        "codici_normattiva": codici,
        "adattatori": adattatori_nel_codice(),
        "fuori_mappa": FUORI_MAPPA,
        "copertura": copertura(registro=registro, tools=tools, calc=calc),
    }


def copertura(*, registro: dict[str, Any] | None = None, tools: dict[str, Any] | None = None,
              calc: dict[str, Any] | None = None) -> dict[str, Any]:
    """Che cosa del codice è coperto dalla mappa, che cosa manca e che cosa la mappa nomina senza che esista."""
    registro = sorgenti_registro() if registro is None else registro
    tools = tool_lex() if tools is None else tools
    calc = calcolatori() if calc is None else calc
    nel_codice = {
        "sorgenti_registro": set(registro),
        "adattatori": set(adattatori_nel_codice()),
        "tool_lex": set(tools),
        "calcolatori": set(calc),
    }
    in_mappa = {
        "sorgenti_registro": {s for sc in SCHEDE for s in sc.sorgenti_registro},
        "adattatori": {a for sc in SCHEDE for a in sc.adattatori},
        "tool_lex": {t for sc in SCHEDE for t in sc.tool_lex},
        "calcolatori": set(calc),  # tutti nel parametro «strumento» di «calcolo»
    }
    uscita: dict[str, Any] = {}
    for tipo, codice in nel_codice.items():
        esclusi = set(FUORI_MAPPA.get(tipo, {}))
        uscita[tipo] = {
            "nel_codice": len(codice),
            "in_mappa": len(codice & in_mappa[tipo]),
            "fuori_mappa_dichiarati": len(codice & esclusi),
            "mancanti": sorted(codice - in_mappa[tipo] - esclusi),
            "inesistenti": sorted((in_mappa[tipo] | esclusi) - codice),
        }
    morte = [r for sc in SCHEDE for r in sc.funzioni if not funzione(r)["esiste"]]
    uscita["funzioni"] = {"nominate": sum(len(sc.funzioni) for sc in SCHEDE), "inesistenti": morte}
    return uscita


# ---------------------------------------------------------------------------------------------- uso a runtime
@lru_cache(maxsize=1)
def mappa() -> dict[str, Any]:
    """La mappa generata (file versionato), senza importare i moduli che descrive."""
    return json.loads(FILE_MAPPA.read_text(encoding="utf-8"))


def strumento(nome: str) -> dict[str, Any] | None:
    return next((s for s in mappa()["strumenti"] if s["nome"] == nome), None)


_DATA_IT = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
_ATTO_NUMERATO = re.compile(r"^(?:d\.?\s?lgs\.?|d\.?\s?l\.?|l\.?|legge|d\.?p\.?r\.?|d\.?m\.?|r\.?d\.?|d\.?p\.?c\.?m\.?|reg\.?\s?(?:ue|ce)?)\s*\d+/\d{4}$")


def _data_valida(valore: Any) -> bool:
    from datetime import date

    m = _DATA_IT.match(str(valore or ""))
    if not m:
        return False
    try:
        date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return False
    return True


def _atto_valido(valore: str) -> bool:
    testo = " ".join(str(valore or "").lower().split())
    if _ATTO_NUMERATO.match(testo):
        return True
    for codice in mappa()["codici_normattiva"]:
        if testo == codice["chiave"] or testo in {s.lower() for s in codice["sinonimi"]}:
            return True
    return False


def _valore_valido(spec: dict[str, Any], valore: Any) -> str:
    tipo = spec.get("tipo")
    if tipo == "data":
        return "" if _data_valida(valore) else "data non in formato gg/mm/aaaa o inesistente"
    if tipo == "intero":
        return "" if isinstance(valore, int) and not isinstance(valore, bool) else "non è un intero"
    if tipo == "booleano":
        return "" if isinstance(valore, bool) else "non è vero/falso"
    if tipo == "scelta":
        return "" if str(valore) in spec.get("valori", []) else f"«{valore}» non è fra le scelte ammesse"
    if tipo == "oggetto":
        return "" if isinstance(valore, dict) else "non è un oggetto"
    if not isinstance(valore, str) or not valore.strip():
        return "testo vuoto"
    if spec.get("valori_da") == "codici_normattiva" and not _atto_valido(valore):
        return f"«{valore}» non è un codice riconosciuto né un atto «tipo numero/anno»"
    return ""


def _campi_calcolo(ident: str, campi: dict[str, Any]) -> list[str]:
    calc = mappa()["calcolatori"].get(ident)
    if calc is None:
        return [f"calcolatore «{ident}» inesistente"]
    errori = []
    for nome, valore in campi.items():
        campo = calc["campi"].get(nome)
        if campo is None:
            errori.append(f"campo «{nome}» non dichiarato dal calcolatore {ident}")
            continue
        if campo["tipo"] == "select" and "valori" in campo and str(valore) not in campo["valori"]:
            errori.append(f"campo «{nome}»: «{valore}» non è fra le scelte del calcolatore")
        elif campo["tipo"] == "date" and not _data_valida(valore):
            errori.append(f"campo «{nome}»: data non in formato gg/mm/aaaa")
        elif campo["tipo"] == "number" and not (isinstance(valore, (int, float)) and not isinstance(valore, bool)):
            errori.append(f"campo «{nome}»: non è un numero")
    return errori


def valida_chiamata(nome: str, parametri: dict[str, Any] | None) -> list[str]:
    """Gli errori della chiamata rispetto alla mappa (lista vuota = chiamata eseguibile)."""
    voce = strumento(nome)
    if voce is None:
        return [f"strumento «{nome}» inesistente"]
    parametri = dict(parametri or {})
    errori = [f"parametro «{p}» non previsto da {nome}" for p in parametri if p not in voce["parametri"]]
    for p, spec in voce["parametri"].items():
        if p not in parametri:
            if spec.get("obbligatorio"):
                errori.append(f"manca il parametro obbligatorio «{p}»")
            continue
        motivo = _valore_valido(spec, parametri[p])
        if motivo:
            errori.append(f"{p}: {motivo}")
    if nome == "calcolo" and not errori:
        errori += _campi_calcolo(str(parametri["strumento"]), dict(parametri.get("campi") or {}))
    return errori


def per_il_modello(*, con_calcolatori: bool = True) -> str:
    """Descrizione compatta degli strumenti per il prompt del modello piccolo (stessa fonte della mappa)."""
    righe = ["Strumenti di IUSENTRA (rispondi con la chiamata JSON degli strumenti da usare, in ordine):"]
    for s in mappa()["strumenti"]:
        par = []
        for p, spec in s["parametri"].items():
            tipo = spec["tipo"]
            if tipo == "scelta" and spec.get("valori_da") != "calcolatori":
                tipo = "|".join(spec.get("valori", []))
            par.append(f"{p}{'' if spec.get('obbligatorio') else '?'}:{tipo}")
        righe.append(f"- {s['nome']}({', '.join(par)}): {s['contenuto'].split(':')[0].split('.')[0]}")
    if con_calcolatori:
        righe.append("Calcolatori per «calcolo.strumento»: " + ", ".join(sorted(mappa()["calcolatori"])))
    return "\n".join(righe)


__all__ = ["FILE_MAPPA", "SCHEMA", "copertura", "costruisci_mappa", "funzione", "mappa", "per_il_modello",
           "strumento", "valida_chiamata"]
