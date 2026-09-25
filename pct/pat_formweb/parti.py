"""Le parti del fascicolo con il ruolo che il Formweb chiede (ricorrente, resistente, controinteressato).

La posizione dell'assistito la indica l'avvocato (di default ricorrente). Le
altre parti si propongono così: amministrazioni ed enti pubblici dalla parte
opposta all'assistito sono «resistenti», i privati controparte sono
«controinteressati» (art. 41 c.p.a.); l'avvocato può cambiare ogni ruolo o
escludere una parte, e la sua scelta prevale. La tipologia segue le quattro
voci del portale (Persona fisica, Persona giuridica, Amministrazione,
Minore/Incapacità).
"""

from __future__ import annotations

from typing import Any, Iterable

PUBBLICHE = {"PUBBLICA_AMMINISTRAZIONE", "ENTE"}
GIURIDICHE = {"PERSONA_GIURIDICA", "CONDOMINIO", "ASSOCIAZIONE"}
_CONTRO = {"CONTROPARTE", "INTERVENIENTE"}


def tipologia(tipo: str) -> str:
    tipo = (tipo or "").upper()
    if tipo in PUBBLICHE:
        return "Amministrazione"
    if tipo in GIURIDICHE or tipo in {"AZIENDA", "SOCIETA", "PERSONA_GIURIDICA"}:
        return "Persona giuridica"
    return "Persona fisica"


def _voce(chiave: str, dati: dict[str, Any], ruolo: str, fonte: str) -> dict[str, Any]:
    tip = tipologia(dati.get("tipo", ""))
    fisica = tip == "Persona fisica"
    denominazione = str(dati.get("ragione_sociale") or dati.get("denominazione") or "").strip()
    if not fisica and not denominazione:
        denominazione = " ".join(x for x in (dati.get("cognome"), dati.get("nome")) if x).strip()
    return {
        "id": chiave, "ruolo": ruolo, "tipologia": tip, "fonte": fonte,
        "cognome": str(dati.get("cognome") or "").strip() if fisica else "",
        "nome": str(dati.get("nome") or "").strip() if fisica else "",
        "denominazione": "" if fisica else denominazione,
        "codiceFiscale": str(dati.get("codice_fiscale") or dati.get("partita_iva") or "").strip().upper(),
        "pec": str(dati.get("pec") or "").strip().lower(),
    }


def parti_pat(cliente: dict[str, Any] | None, soggetti: Iterable[tuple[str, dict[str, Any]]],
              posizione: str = "ricorrente", scelte: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """``soggetti``: coppie (ruolo IUSENTRA, dati del soggetto con ``id``); ``scelte``: {id: ruolo PAT o «escludi»}."""
    scelte = scelte or {}
    posizione = posizione or "ricorrente"
    elenco: list[dict[str, Any]] = []
    if cliente:
        elenco.append(_voce("cliente", cliente, posizione, "cliente"))
    for ruolo_iusentra, dati in soggetti:
        ruolo_iusentra = (ruolo_iusentra or "").upper()
        if ruolo_iusentra == "ASSISTITO":
            proposto = posizione
        elif ruolo_iusentra in _CONTRO:
            pubblica = (dati.get("tipo") or "").upper() in PUBBLICHE
            if posizione == "ricorrente":
                proposto = "resistente" if pubblica else "controinteressato"
            else:
                proposto = "ricorrente"
        else:
            continue
        elenco.append(_voce(str(dati.get("id") or ""), dati, proposto, "soggetti"))
    esito = []
    for parte in elenco:
        scelto = scelte.get(parte["id"])
        if scelto == "escludi":
            continue
        if scelto:
            parte = {**parte, "ruolo": scelto, "sceltaAvvocato": True}
        esito.append(parte)
    return esito


def per_ruolo(parti: Iterable[dict[str, Any]], ruolo: str) -> list[dict[str, Any]]:
    return [p for p in parti if p.get("ruolo") == ruolo]


__all__ = ["parti_pat", "per_ruolo", "tipologia"]
