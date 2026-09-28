"""Anteprima del modulo PAT compilato, letta dal PDF generato.

Il modulo ministeriale è un PDF XFA: fuori da Adobe Reader (browser, anteprime di sistema) mostra solo
l'avviso «richiede Adobe Reader». Per far controllare all'avvocato cosa è scritto nel modulo prima di
firmarlo, l'anteprima rilegge il file prodotto — non i dati digitati nella pagina — e li ordina con le
sezioni e le etichette del modello ufficiale. Quello che l'anteprima mostra è quindi quello che c'è nel
file da aprire, completare e firmare in Adobe Reader (Istruzioni per la compilazione dei moduli di
deposito v9.6.2, «Firma digitale del modulo»).
"""

from __future__ import annotations

import hashlib
from typing import Any
from xml.etree import ElementTree as ET

from pct.pat_pdf_templates import PAT_PDF_TEMPLATES, module_only_field, read_compiled_template
from pct.pat_xfa_dati import valore
from pct.pat_xfa_schema import build_pat_xfa_schema_payload

# Valori che il modulo scrive da sé nei campi a scelta quando non è stata fatta una scelta.
_VALORI_NEUTRI = {"", "0", "Z"}
_SI_NO = {"S": "Sì", "N": "No", "1": "Sì"}
# Etichette delle Istruzioni per la compilazione dei moduli (v9.6.2) per i campi che nel modello non hanno
# una didascalia leggibile.
_ETICHETTE = {
    "tipoRicorsoTar": "Tipologia di ricorso", "tipoRicorsoCds": "Tipologia di appello",
    "textFieldAutorita": "Autorità emanante", "listTipoAtto": "Tipo provvedimento", "textFieldAltro": "Tipo (se ALTRO)",
    "numeroAtto": "Numero", "annoAtto": "Anno", "rbAttoValidoTutti": "Procura valida per tutte le parti difese",
    "oggettoEsteso": "Oggetto della domanda e/o provvedimenti impugnati", "rbContributo": "Contributo unificato",
    "rbTipoRicorrente": "Tipologia del ricorrente", "rbTipoResistente": "Tipologia del resistente",
    "codiceFiscale": "Codice fiscale", "dataVersamento": "Data versamento", "txtEstremiVersamento": "Estremi versamento",
    "txtImportoVersato": "Importo versato", "codiceTributo": "Codice tributo", "numRiga": "Nr. riga",
}
# Scelte che si mostrano sempre, anche quando coincidono con il valore iniziale del modulo.
_SEMPRE = {"selectSede", "tipoRicorsoTar", "tipoRicorsoCds", "tipoAtto"}


def _nome(elemento: ET.Element) -> str:
    tag = elemento.tag.split("}", 1)[-1] if isinstance(elemento.tag, str) else ""
    return elemento.attrib.get("name") or tag


def _valori_per_percorso(radice: ET.Element) -> dict[str, list[str]]:
    """Ogni campo del modello compilato con i suoi valori (più d'uno nelle righe ripetibili)."""
    valori: dict[str, list[str]] = {}

    def visita(elemento: ET.Element, percorso: tuple[str, ...]) -> None:
        corrente = (*percorso, _nome(elemento))
        if isinstance(elemento.tag, str) and elemento.tag.endswith("field"):
            valori.setdefault("/".join(corrente), []).append(valore(elemento))
        for figlio in list(elemento):
            visita(figlio, corrente)

    visita(radice, ())
    return valori


def _testo_scelta(campo: dict[str, Any], grezzo: str) -> str:
    for opzione in campo.get("options") or []:
        if grezzo in {str(opzione.get("export") or ""), str(opzione.get("value") or "")}:
            return str(opzione.get("label") or grezzo)
    return _SI_NO.get(grezzo, grezzo) if campo.get("type") in {"checkbox", "select"} else grezzo


def _righe_sezione(sezione: dict[str, Any], valori: dict[str, list[str]], vuoto: dict[str, list[str]]) -> list[dict[str, str]]:
    righe: list[dict[str, str]] = []
    for campo in sezione.get("fields") or []:
        sempre = campo.get("name") in _SEMPRE and "/rigaAtto/" not in str(campo.get("path"))
        if (campo.get("technical") and not sempre) or module_only_field(str(campo.get("name") or "")):
            continue
        if campo.get("type") == "radio":
            scelte = [str(o.get("label") or "") for o in campo.get("options") or []
                      if any(v not in _VALORI_NEUTRI for v in valori.get(str(o.get("path")), []))]
            if scelte:
                righe.append({"etichetta": _ETICHETTE.get(str(campo.get("name")), str(campo["label"])), "valore": ", ".join(scelte)})
            continue
        if not sempre and valori.get(str(campo["path"]), []) == vuoto.get(str(campo["path"]), []):
            continue  # valore di partenza del modulo ministeriale, non scritto da IUSENTRA
        grezzi = [v for v in valori.get(str(campo["path"]), []) if v not in _VALORI_NEUTRI]
        if campo.get("type") == "checkbox":
            grezzi = [v for v in grezzi if v != "N"]
        testi = [_testo_scelta(campo, v) for v in grezzi]
        if testi:
            etichetta = _ETICHETTE.get(str(campo.get("name")), str(campo["label"]))
            if campo.get("repeatableLabel"):
                gruppo = str(campo["repeatableLabel"]).removeprefix("Riga ").strip()
                etichetta = f"{gruppo} · {etichetta}"
            righe.append({"etichetta": etichetta, "valore": " | ".join(testi)})
    return righe


def anteprima(module_id: str, pdf: bytes) -> dict[str, Any]:
    """Sezioni e dati del modulo compilato, riletti dal PDF, con versione e impronta del file."""
    modello = PAT_PDF_TEMPLATES[module_id]
    originale = modello.path.read_bytes()
    valori = _valori_per_percorso(read_compiled_template(pdf))
    vuoto = _valori_per_percorso(read_compiled_template(originale))
    schema = build_pat_xfa_schema_payload(module_id)
    sezioni = []
    for sezione in schema.get("sections") or []:
        righe = _righe_sezione(sezione, valori, vuoto)
        if righe:
            sezioni.append({"titolo": str(sezione.get("title") or ""), "righe": righe})
    versione = next((v for p, vs in valori.items() if p.endswith("txtModuleVersion") for v in vs if v), "")
    return {
        "modulo": modello.official_code,
        "versione": versione,
        "sezioni": sezioni,
        # Il modello ministeriale resta intatto: i suoi byte sono l'inizio del file compilato (salvataggio
        # incrementale), quindi restano validi gli script e i diritti d'uso di Adobe Reader.
        "modelloIntatto": pdf[: len(originale)] == originale,
        "impronta": hashlib.sha256(pdf).hexdigest().upper(),
    }


__all__ = ["anteprima"]
