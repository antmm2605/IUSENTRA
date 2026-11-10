"""Lo stato del contributo unificato del fascicolo: una sola decisione per tutti i pannelli.

Card del presidio economico, finestra del controllo economico, conto economico e quadro del fascicolo
mostrano la stessa etichetta perché la ricavano tutti da ``stato_contributo``. Le regole sono quelle del
conto economico, che l'avvocato ha indicato come corretto:

- il contributo unificato si versa negli importi dell'art. 13 D.P.R. 115/2002; la prova è la ricevuta
  (pagoPA, F23) o la nota di iscrizione a ruolo che lo riporta;
- nelle cause di lavoro, previdenza e pubblico impiego è esente la parte con reddito sotto soglia che
  deposita l'autocertificazione (art. 9, comma 1-bis, D.P.R. 115/2002);
- prevale ciò che l'avvocato ha confermato (catalogo confermato o voce registrata a mano): una lettura
  automatica, anche ben collaudata, resta «da confermare»; una ricevuta solo proposta non vince su
  un'autocertificazione (una PEC di deposito classificata come «versamento» non prova il pagamento);
- l'atto che si limita a richiamare l'esenzione non è la fonte dell'esenzione: non compare fra le fonti.

Modulo puro: riceve la voce economica e i documenti del contributo già letti, non scrive nulla.
"""

from __future__ import annotations

import json
from typing import Any, Iterable, Mapping

NORMA_CU = "art. 13 D.P.R. 115/2002"
NORMA_ESENZIONE_CU = "art. 9, comma 1-bis, D.P.R. 115/2002"
NORMA_ANTICIPAZIONE_FORFETTARIA = "art. 30 D.P.R. 115/2002"

_ETICHETTA_ESENZIONE = "contributo unificato / esenzione"
_ETICHETTA_VERSAMENTO = "contributo unificato / pagamento"
_INDIZI_ESENZIONE = ("autocertificazione", "esenzione")

# codice → (categoria, etichetta, tono). La categoria è una delle cinque situazioni che l'avvocato distingue.
STATI = {
    "pagato": ("dovuto_pagato", "Versato", "success"),
    "pagato_da_confermare": ("dovuto_pagato", "Versato, da confermare", "warning"),
    "da_pagare": ("dovuto_da_pagare", "Da versare", "warning"),
    "esente": ("esente", "Esente", "success"),
    "esente_da_confermare": ("esente", "Esente, da confermare", "warning"),
    "non_dovuto": ("non_dovuto", "Non dovuto", "neutral"),
    "da_verificare": ("da_verificare", "Da verificare", "warning"),
}

# Le letture che sono fonte del contributo: ricevute e note che lo riportano, autocertificazioni,
# attestazioni del registro. Il richiamo nell'atto («richiamo_nell_atto») non lo è.
_CAMPI_RICEVUTA = {"contributo_unificato", "pagamento_cu_non_verificato"}
_DICHIARAZIONI_FONTE = {"autocertificazione", "attestazione_registro"}


def _testo(valore: Any) -> str:
    return " ".join(str(valore or "").split())


def _euro(valore: float | None) -> str:
    if valore is None:
        return ""
    testo = f"{valore:,.2f}".replace(",", "§").replace(".", ",").replace("§", ".")
    return f"€ {testo}"


def _numero(valore: Any) -> float | None:
    try:
        numero = round(float(str(valore).replace("€", "").strip()), 2) if not isinstance(valore, (int, float)) else round(float(valore), 2)
    except (TypeError, ValueError):
        return None
    return numero if numero > 0 else None


def tipo_dichiarazione(fonte: Mapping[str, Any]) -> str:
    """Il tipo di dichiarazione letta (autocertificazione, attestazione del registro, richiamo nell'atto)."""
    for prova in fonte.get("prove") or []:
        if isinstance(prova, Mapping) and prova.get("codice") == "dichiarazione_economica":
            try:
                return _testo((json.loads(prova.get("dettaglio") or "{}") or {}).get("tipo"))
            except (ValueError, TypeError, AttributeError):
                return ""
    return ""


def e_fonte_del_contributo(fonte: Mapping[str, Any]) -> bool:
    """Vero per ricevuta/nota che riporta il contributo, autocertificazione o attestazione; falso per il semplice richiamo."""
    campo = _testo(fonte.get("campo"))
    if not campo:
        # Fonte registrata prima che la proiezione portasse il campo letto: si esclude solo il richiamo dichiarato.
        riscontri = " ".join(_testo(r) for r in fonte.get("riscontri") or []).lower()
        return "richiama l'esenzione" not in riscontri and "richiamo all'esenzione" not in riscontri
    if campo in _CAMPI_RICEVUTA:
        return True
    if campo == "esenzione_cu_dichiarata":
        return tipo_dichiarazione(fonte) in _DICHIARAZIONI_FONTE
    return False


def solo_fonti_del_contributo(fonti: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Le sole fonti del contributo, una per documento, nell'ordine in cui sono arrivate."""
    visti: set[tuple[str, str]] = set()
    esito = []
    for fonte in fonti:
        chiave = (_testo(fonte.get("tipo")), _testo(fonte.get("documentoId")))
        if not e_fonte_del_contributo(fonte) or chiave in visti:
            continue
        visti.add(chiave)
        esito.append(dict(fonte))
    return esito


def avviso_importo(voce: Mapping[str, Any]) -> str:
    """Perché l'importo del contributo non si può dare per certo: più importi letti o lettura da confermare.

    Nelle ricevute dei depositi compare spesso anche l'anticipazione forfettaria di € 27 (art. 30 D.P.R. 115/2002),
    che non è contributo unificato: indicarla come tale falserebbe il conto e le anticipazioni da recuperare.
    """
    letti = sorted({n for n in (_numero(v) for v in voce.get("importiLetti") or []) if n})
    if len(letti) > 1:
        testo = f"Importi letti nelle ricevute: {', '.join(_euro(n) for n in letti)}"
        if 27.0 in letti:
            testo += f"; {_euro(27.0)} è l'anticipazione forfettaria ({NORMA_ANTICIPAZIONE_FORFETTARIA}), non il contributo unificato"
        return testo + ": confermare sulla ricevuta l'importo del contributo."
    if voce.get("richiedeConferma"):
        return "Lettura della ricevuta da confermare: aprirla e verificare importo, data e procedimento."
    return ""


def _documento(d: Mapping[str, Any]) -> dict[str, str]:
    return {"id": _testo(d.get("id")), "nome": _testo(d.get("nome")), "href": _testo(d.get("href"))}


def _esito(codice: str, *, importo: float | None, norma: str, dettaglio: str, fonti: list[dict[str, str]],
           ruolo_fonti: str = "") -> dict[str, Any]:
    categoria, etichetta, tono = STATI[codice]
    return {
        "codice": codice, "categoria": categoria, "etichetta": etichetta, "tono": tono, "norma": norma,
        "importo": importo, "importoLabel": _euro(importo), "dettaglio": dettaglio,
        "confermato": codice in {"pagato", "esente", "non_dovuto"},
        "documento": fonti[0] if fonti else None, "fonti": fonti, "ruoloFonti": ruolo_fonti,
    }


def stato_contributo(voce: Mapping[str, Any], documenti: Iterable[Mapping[str, Any]] = ()) -> dict[str, Any]:
    """Lo stato del contributo unificato del fascicolo.

    ``voce``: la voce economica «contributo_unificato» (status, importo, documento_fonte, documento_id, href,
    richiedeConferma, importiLetti, manuale = registrata o decisa dall'avvocato).
    ``documenti``: i documenti che il catalogo ha classificato come contributo unificato (etichetta, id, nome,
    href, confermato).
    """
    documenti = list(documenti)
    esenzioni = [d for d in documenti if _ETICHETTA_ESENZIONE in _testo(d.get("etichetta")).lower()]
    versamenti = [d for d in documenti if _ETICHETTA_VERSAMENTO in _testo(d.get("etichetta")).lower()]
    stato_voce = _testo(voce.get("status") or voce.get("stato")).lower()
    manuale = bool(voce.get("manuale"))
    nome_voce = _testo(voce.get("documento_fonte"))
    documento_voce = {"id": _testo(voce.get("documento_id")), "nome": nome_voce, "href": _testo(voce.get("href"))}
    if not esenzioni and any(p in nome_voce.lower() for p in _INDIZI_ESENZIONE):
        esenzioni = [{**documento_voce, "confermato": manuale and stato_voce == "non_previsto"}]
    if esenzioni and not any(d.get("confermato") for d in versamenti):
        versamenti = []
    if not versamenti and not esenzioni and stato_voce == "pagato" and nome_voce:
        # Ricevuta registrata nella voce (dall'avvocato o dall'archivio delle letture) senza voce di catalogo.
        versamenti = [{**documento_voce, "confermato": manuale}]
    importo = _numero(voce.get("importo"))
    if versamenti:
        fonti = [_documento(d) for d in versamenti]
        da_confermare = avviso_importo(voce)
        if da_confermare or not any(d.get("confermato") for d in versamenti):
            return _esito("pagato_da_confermare", importo=None if da_confermare else importo, norma=NORMA_CU,
                          fonti=fonti, ruolo_fonti="ricevuta di versamento",
                          dettaglio=da_confermare or "Ricevuta letta e non ancora confermata dall'avvocato: aprirla e "
                                                    "confermare importo e procedimento.")
        return _esito("pagato", importo=importo, norma=NORMA_CU, fonti=fonti, ruolo_fonti="ricevuta di versamento",
                      dettaglio="" if importo else "Importo da riportare dalla ricevuta.")
    if esenzioni:
        confermata = any(d.get("confermato") for d in esenzioni)
        return _esito("esente" if confermata else "esente_da_confermare", importo=None, norma=NORMA_ESENZIONE_CU,
                      fonti=[_documento(d) for d in esenzioni], ruolo_fonti="autocertificazione del reddito",
                      dettaglio="Esenzione per reddito con autocertificazione depositata." if confermata else
                      "Aprire l'autocertificazione e confermarla (anno di reddito, soglia): il documento non è ancora confermato.")
    if stato_voce == "non_previsto" and manuale:
        return _esito("non_dovuto", importo=None, norma="", fonti=[],
                      dettaglio="L'avvocato ha indicato che per questo procedimento il contributo non è dovuto.")
    if importo and stato_voce in {"da_registrare", "parziale", ""}:
        return _esito("da_pagare", importo=importo, norma=NORMA_CU, fonti=[],
                      dettaglio=f"Contributo dovuto ({_euro(importo)}): manca la ricevuta del versamento.")
    return _esito("da_verificare", importo=importo, norma=NORMA_CU, fonti=[],
                  dettaglio="Manca la ricevuta del versamento o l'autocertificazione di esenzione.")


__all__ = ["NORMA_CU", "NORMA_ESENZIONE_CU", "STATI", "avviso_importo", "e_fonte_del_contributo",
           "solo_fonti_del_contributo", "stato_contributo", "tipo_dichiarazione"]
