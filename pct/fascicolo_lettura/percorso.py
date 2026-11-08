"""Dopo la sentenza della causa: esito per il cliente e percorso (realizzazione o impugnazione).

L'esito viene dai fatti del motore documenti (dispositivo della sentenza pertinente alla causa); il ruolo del cliente
dalle parti del fascicolo; il rito dal tipo di fascicolo. I passi e i rimedi con le norme sono in
``pct/percorso_pratica/rimedi.py``; qui si traducono le norme negli identificativi del registro delle fonti.
"""

from __future__ import annotations

import re
from typing import Any

from pct.percorso_pratica.rimedi import rimedi

from ._testo import pulisci

_PA = re.compile(r"\b(?:minister[oi]|amministrazion|agenzia|avvocatura|presidenza del consiglio|istituto comprensivo|ufficio scolastico|"
                 r"prefettura|questura|inps|inail|comune di|regione|provincia di|azienda sanitaria|asl\b|universit)", re.IGNORECASE)
_NORMA = (
    (re.compile(r"art\. (\d+(?:-[a-z]+)?)(?:, [a-z]+ comma,)? c\.p\.c\."), "cpc_{}"),
    (re.compile(r"art\. (\d+(?:-[a-z]+)?) c\.p\.a\."), "cpa_{}"),
    (re.compile(r"art\. (\d+(?:-[a-z]+)?) c\.c\."), "cc_{}"),
    (re.compile(r"art\. (\d+(?:-[a-z]+)?) c\.p\.p\."), "cpp_{}"),
    (re.compile(r"art\. (\d+(?:-[a-z]+)?) D\.Lgs\. 546/1992"), "dlgs546_{}"),
    (re.compile(r"art\. 11 R\.D\. 1611/1933"), "rd1611_art11"),
    (re.compile(r"art\. 14 D\.L\. 669/1996"), "dl669_art14"),
    (re.compile(r"art\. 59, comma 2, L\. 69/2009"), "l69_art59"),
)


def identificativi(norme: list[str]) -> tuple[str, ...]:
    """«art. 285 c.p.c.» -> «cpc_285» (gli identificativi che il registro non conosce sono ignorati in visualizzazione)."""
    risultato = []
    for norma in norme:
        for schema, formato in _NORMA:
            m = schema.search(norma)
            if m:
                risultato.append(formato.format(*(g.replace("-", "") for g in m.groups())) if m.groups() else formato)
                break
    return tuple(dict.fromkeys(risultato))


_ATTO_DI_CHI_PROMUOVE = re.compile(r"\b(?:ricorso|citazione|atto di citazione|opposizione|reclamo|appello)\b", re.IGNORECASE)
_ATTO_DI_CHI_RESISTE = re.compile(r"\b(?:comparsa di (?:risposta|costituzione)|memoria (?:difensiva|di costituzione))\b", re.IGNORECASE)


def _ruolo_cliente(intestazione: dict[str, Any], documenti_letti: dict[str, Any] | None = None) -> tuple[str, str]:
    """Ruolo del cliente nella causa e da dove si ricava: parti del fascicolo, poi l'atto di parte dello studio."""
    from .passi_note_127_ter import _ruolo_cliente as ruolo

    attivo = ruolo(intestazione)
    if attivo is not None:
        return ("ricorrente" if attivo else "resistente"), "parti del fascicolo"
    documenti_letti = documenti_letti or {}
    introduttivo = documenti_letti.get("atto_introduttivo") or {}
    if _ATTO_DI_CHI_PROMUOVE.search(pulisci(introduttivo.get("etichetta"))):
        return "ricorrente", f"atto introduttivo dello studio: {pulisci(introduttivo.get('etichetta'))}"
    atti = [voce for voce in documenti_letti.get("tutti") or [] if voce.get("sezione") == "atti"]
    difesa = next((voce for voce in atti if _ATTO_DI_CHI_RESISTE.search(pulisci(voce.get("etichetta")))), None)
    if difesa:
        return "resistente", f"atto difensivo dello studio: {pulisci(difesa.get('etichetta'))}"
    return "", ""


def _spese(valore: str) -> dict[str, Any]:
    parti = valore.split(";")
    importo = next((p.split("=", 1)[1] for p in parti if p.startswith("importo=")), "")
    return {"regolazione": parti[0] if parti else "non_indicata", "importo": importo, "distrazione": "distrazione" in parti}


def percorso_dopo_sentenza(intestazione: dict[str, Any], documenti_letti: dict[str, Any]) -> dict[str, Any] | None:
    sentenza = documenti_letti.get("sentenza") or {}
    esito_letto = sentenza.get("esito") or {}
    codice = esito_letto.get("esito_sentenza")
    if not codice:
        return None
    ruolo, fonte_ruolo = _ruolo_cliente(intestazione, documenti_letti)
    per_noi = _per_il_cliente(codice, ruolo)
    esito = {"esito": codice, "per_il_cliente": per_noi, "spese": _spese(esito_letto.get("spese_sentenza", "")), "ragioni": []}
    from pct.procedura_fasi.riti import rito_per_fascicolo

    rito = rito_per_fascicolo(intestazione.get("tipo", ""), intestazione.get("rito", ""))
    giurisdizione, grado = _giurisdizione_e_grado(intestazione, sentenza)
    controparti = " ".join(nome for nomi in dict(intestazione.get("parti") or {}).values() for nome in nomi) + " " + pulisci(intestazione.get("controparte"))
    percorso = rimedi(esito, rito=rito if rito in {"lavoro", "ordinario", "semplificato"} else "ordinario", grado=grado,
                      giurisdizione=giurisdizione, controparte_pa=bool(_PA.search(controparti)))
    return {"sentenza": pulisci(sentenza.get("etichetta")), "data": pulisci(sentenza.get("data_it")), "esito": codice,
            "per_il_cliente": per_noi, "ruolo_cliente": ruolo, "fonte_ruolo": fonte_ruolo, "spese": esito["spese"], **percorso}


def _giurisdizione_e_grado(intestazione: dict[str, Any], sentenza: dict[str, Any]) -> tuple[str, str]:
    """Dall'ufficio del fascicolo, dal rito e dall'intestazione della sentenza letta: una sentenza d'appello non si
    impugna con l'appello, una del TAR non con i termini del c.p.c."""
    from pct.percorso_pratica.giurisdizioni import giurisdizione_e_grado

    return giurisdizione_e_grado(
        tipo=intestazione.get("tipo", ""), ufficio=intestazione.get("ufficio", ""), rito=intestazione.get("rito", ""),
        sentenza=" ".join(pulisci(sentenza.get(campo)) for campo in ("etichetta", "intestazione", "ufficio")))


def impugnazione_del_grado(intestazione: dict[str, Any], documenti_letti: dict[str, Any]) -> dict[str, Any] | None:
    """Il mezzo d'impugnazione della sentenza quando l'esito non è letto; None per il primo grado civile."""
    from pct.procedura_fasi.riti import rito_per_fascicolo

    giurisdizione, grado = _giurisdizione_e_grado(intestazione, documenti_letti.get("sentenza") or {})
    if (giurisdizione, grado) == ("civile", "primo"):
        return None
    rito = rito_per_fascicolo(intestazione.get("tipo", ""), intestazione.get("rito", ""))
    elenco = rimedi({"per_il_cliente": "da_valutare"}, rito=rito if rito in {"lavoro", "ordinario", "semplificato"} else "ordinario",
                    grado=grado, giurisdizione=giurisdizione)["rimedi"]
    return elenco[0] if elenco else None


def _per_il_cliente(codice: str, ruolo: str) -> str:
    promotore, difensore = ruolo == "ricorrente", ruolo == "resistente"
    if codice in {"accoglimento", "rigetto"} and (promotore or difensore):
        return "favorevole" if (codice == "accoglimento") == promotore else "sfavorevole"
    if codice == "accoglimento_parziale" and (promotore or difensore):
        return "parziale"
    if codice in {"inammissibile", "improcedibile", "estinzione", "incompetenza", "difetto_giurisdizione"} and promotore:
        return "sfavorevole"
    return "da_valutare"


__all__ = ["identificativi", "impugnazione_del_grado", "percorso_dopo_sentenza"]
