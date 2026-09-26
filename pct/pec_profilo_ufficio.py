"""Ufficio, numero di ruolo e fase del profilo processuale di una PEC, letti dove sono certi.

Il profilo processuale scriveva come «Ufficio» l'etichetta della regola che
aveva riconosciuto la PEC («Ufficio giudiziario civile», «TAR o Consiglio di
Stato»): una categoria, non un ufficio, anche quando il mittente era proprio
la cancelleria (tribunale.vicenza@civile.ptel.giustiziacert.it) o quando la
PEC veniva da un Ministero. Qui l'ufficio si prende solo da fonti certe:

1. l'indirizzo PEC della cancelleria mittente o destinataria, confrontato con
   il registro degli uffici giudiziari (ReGIndE: gli indirizzi
   ``*.ptel.giustiziacert.it`` sono quelli degli uffici, art. 7 D.M. 44/2011);
2. l'oggetto ministeriale del deposito («DEPOSITO TELEMATICO - RICORSO -
   Tribunale di Vicenza», specifiche tecniche DGSIA);
3. gli avvisi della Giustizia amministrativa (``pec.ga-cert.it``), il cui
   oggetto porta il NRG del ricorso e il codice della sede («COD#tarrc…»,
   art. 136 c.p.a. e allegato 2 al c.p.a.).

Se nessuna fonte è certa l'ufficio resta vuoto: meglio «da verificare» che
una categoria scambiata per un ufficio.
"""

from __future__ import annotations

import re
from typing import Any

# Etichette delle regole di contesto: descrivono il tipo di PEC, non l'ufficio.
UFFICI_GENERICI = frozenset({
    "ufficio giudiziario civile", "tar o consiglio di stato", "giudice di pace", "unep", "ufficio giudiziario",
})

_PEC_UFFICIO = re.compile(r"\b([a-z0-9][a-z0-9._-]*@(?:civile|penale)\.ptel\.giustiziacert\.it)\b", re.IGNORECASE)
_UFFICIO_IN_OGGETTO = re.compile(
    r"\b((?:Tribunale(?:\s+(?:Ordinario|per i Minorenni|di Sorveglianza))?|Corte\s+d['’]\s*Appello|Giudice\s+di\s+Pace|"
    r"Ufficio\s+del\s+Giudice\s+di\s+Pace)\s+di\s+[A-ZÀ-Ü][\w'’À-ÿ]*(?:\s+(?:di\s+)?[A-ZÀ-Ü][\w'’À-ÿ]*){0,2})",
)
_AVVISO_GA = re.compile(r"\bricorso\s+(\d{4})(\d{5})\b.*?\bCOD#(tar[a-z]{2}|cds|cga)", re.IGNORECASE | re.DOTALL)
_OGGETTO_DEPOSITO = re.compile(
    r"^\s*(?:posta certificata:\s*)?(?:accettazione|consegna|avvenuta consegna|esito controlli automatici|esito intervento cancelleria|"
    r"rifiuto|mancata consegna)?\s*:?\s*(?:accettazione\s+)?deposito telematico\b",
    re.IGNORECASE,
)


def ufficio_generico(valore: Any) -> bool:
    return str(valore or "").strip().casefold() in UFFICI_GENERICI


def _registro_uffici() -> list[dict[str, Any]]:
    try:
        from pct.uffici_giudiziari import get_gestore

        return list(get_gestore().carica())
    except Exception:
        return []


def ufficio_da_pec(testo: str, uffici: list[dict[str, Any]] | None = None) -> str:
    """L'ufficio la cui PEC di cancelleria compare nel messaggio (mittente o destinatario)."""
    indirizzi = [indirizzo.casefold() for indirizzo in _PEC_UFFICIO.findall(str(testo or ""))]
    if not indirizzi:
        return ""
    registro = uffici if uffici is not None else _registro_uffici()
    per_pec: dict[str, str] = {}
    for riga in registro:
        for campo in ("pec", "pec_ministero"):
            pec = str(riga.get(campo) or "").strip().casefold()
            if pec and riga.get("nome"):
                per_pec.setdefault(pec, str(riga["nome"]))
    return next((per_pec[indirizzo] for indirizzo in indirizzi if indirizzo in per_pec), "")


def ufficio_da_oggetto(oggetto: str) -> str:
    """«DEPOSITO TELEMATICO - RICORSO - Tribunale di Vicenza», «Tribunale di Palmi Notificazione…»."""
    trovato = _UFFICIO_IN_OGGETTO.search(str(oggetto or ""))
    if not trovato:
        return ""
    nome = re.split(r"\s+(?:Notificazione|Comunicazione|RG|R\.G\.|-)\b", trovato.group(1))[0]
    return " ".join(nome.split()).rstrip(".")


def avviso_giustizia_amministrativa(testo: str) -> dict[str, str]:
    """NRG e sede dall'oggetto di un avviso della Giustizia amministrativa («ricorso 202500519 COD#tarrc…»)."""
    semplice = str(testo or "")
    if "ga-cert.it" not in semplice.casefold():
        return {}
    trovato = _AVVISO_GA.search(semplice)
    if not trovato:
        return {}
    anno, numero, sede = trovato.group(1), int(trovato.group(2)), trovato.group(3).casefold()
    codice = f"tar_{sede[3:]}" if sede.startswith("tar") else {"cds": "cds", "cga": "cgagiur"}[sede]
    try:
        from pct.pat_formweb.catalogo import SEDI

        etichetta = next((e for c, e in SEDI.values() if c == codice), "")
    except Exception:
        etichetta = ""
    return {"numero_rg": f"{numero}/{anno}", "nrg": f"{anno}{numero:05d}", "ufficio": etichetta}


def numero_ruolo(certificato: str) -> str:
    """«1263/2026/LAV» del Comunicazione.xml → «1263/2026»."""
    trovato = re.match(r"\s*(\d{1,7})\s*/\s*(\d{4})", str(certificato or ""))
    return f"{int(trovato.group(1))}/{trovato.group(2)}" if trovato else ""


def e_ricevuta_di_deposito(oggetto: str) -> bool:
    """Accettazione, consegna o esito di un nostro deposito telematico (non un provvedimento da leggere)."""
    return bool(_OGGETTO_DEPOSITO.search(str(oggetto or "")))


def cliente_da_relata(testo: str) -> str:
    """Nella relata di notifica in proprio: «difensore per mandato come in atti di: Valentina MARRA C.F: …»."""
    trovato = re.search(
        r"difensore\s+(?:per\s+mandato\s+)?(?:come\s+in\s+atti\s+)?di\s*:?\s*([A-ZÀ-Ü][\w'’À-ÿ]+(?:\s+[A-ZÀ-Ü][\w'’À-ÿ]+){1,3})\s+(?:C\.?\s*F\.?|nat[oa]\b|,)",
        str(testo or ""),
    )
    return " ".join(trovato.group(1).split()) if trovato else ""


def parti_da_oggetto(oggetto: str) -> tuple[str, str]:
    """«… Scarfò Emanuela c/Ministero dell'istruzione e del merito.» → (Scarfò Emanuela, Ministero …).

    Solo la forma abbreviata «c/» o «contro» fra due nomi propri: è la dicitura
    con cui amministrazioni e cancellerie indicano la causa nell'oggetto.
    """
    trovato = re.search(
        r"([A-ZÀ-Ü][\w'’À-ÿ]+(?:\s+[A-ZÀ-Ü][\w'’À-ÿ]+){1,3})\s*(?:c/|contro\s)\s*([A-ZÀ-Ü][^.;\n]{3,90})",
        str(oggetto or ""),
    )
    if not trovato:
        return "", ""
    return " ".join(trovato.group(1).split()), " ".join(trovato.group(2).split()).rstrip(" .")


def _senza_formula_cancelleria(valore: Any) -> str:
    return re.split(r"\bSi\s+d[aàá]\s*['’]?\s*atto\b", str(valore or ""), maxsplit=1, flags=re.I)[0].strip(" .;:-")


def riallinea_profilo(profilo: dict[str, Any], *, mittente: str = "", destinatari: str = "") -> dict[str, Any]:
    """Il profilo già salvato di una PEC, corretto con le stesse fonti certe usate alla lettura.

    Le PEC acquisite prima di queste regole mostrano ancora «Ufficio giudiziario
    civile» o il resistente seguito dalla formula della cancelleria: il
    riallineamento avviene alla lettura, senza rielaborare il MIME e senza
    toccare i dati già certi.
    """
    if not isinstance(profilo, dict) or not profilo:
        return profilo
    esito = dict(profilo)
    oggetto = str(esito.get("oggetto_evento") or "")
    fonti = " ".join((oggetto, str(mittente or ""), str(destinatari or ""), str(esito.get("messaggio_operativo") or "")))
    avviso = avviso_giustizia_amministrativa(fonti)
    if not esito.get("ufficio") or ufficio_generico(esito.get("ufficio")):
        ufficio = ufficio_da_pec(fonti) or ufficio_da_oggetto(oggetto) or avviso.get("ufficio", "")
        if ufficio:
            esito["ufficio"] = ufficio
        else:
            esito.pop("ufficio", None)
    if not esito.get("numero_rg"):
        numero = numero_ruolo(esito.get("numero_ruolo_certificato")) or avviso.get("numero_rg", "")
        if numero:
            esito["numero_rg"] = numero
    for campo in ("convenuto_principale", "attore_principale", "parte_processuale", "cliente"):
        if esito.get(campo):
            esito[campo] = _senza_formula_cancelleria(esito[campo])
    if e_ricevuta_di_deposito(oggetto):
        esito["fase_pratica"] = "deposito telematico da completare o monitorare"
    elif avviso:
        esito["fase_pratica"] = "udienza o rinvio da calendarizzare"
        esito.setdefault("nrg_amministrativo", avviso.get("nrg", ""))
    return esito


__all__ = [
    "UFFICI_GENERICI",
    "avviso_giustizia_amministrativa",
    "cliente_da_relata",
    "e_ricevuta_di_deposito",
    "numero_ruolo",
    "parti_da_oggetto",
    "riallinea_profilo",
    "ufficio_da_oggetto",
    "ufficio_da_pec",
    "ufficio_generico",
]
