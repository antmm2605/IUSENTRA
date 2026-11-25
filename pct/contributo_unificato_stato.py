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
import re
from typing import Any, Iterable, Mapping

from pct.document_intelligence.sezioni import NATURA_AUTOCERTIFICAZIONE_CU

NORMA_CU = "art. 13 D.P.R. 115/2002"
NORMA_ESENZIONE_CU = "art. 9, comma 1-bis, D.P.R. 115/2002"
NORMA_ANTICIPAZIONE_FORFETTARIA = "art. 30 D.P.R. 115/2002"

_ETICHETTA_ESENZIONE = "contributo unificato / esenzione"
_ATTO_DI_PARTE = re.compile(r"^(?:ricorso|istanza|atto[\s_]+di|citazione|comparsa|memoria|note|procura)(?=[\W_]|$)", re.IGNORECASE)
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
        # Si esclude solo il richiamo dell'esenzione dentro un atto (ricorso, notifica): una dichiarazione il cui tipo
        # non è stato letto (es. riconosciuta dal nome del documento, senza OCR) resta una fonte da aprire.
        tipo = tipo_dichiarazione(fonte)
        return tipo in _DICHIARAZIONI_FONTE or tipo != "richiamo_nell_atto"
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
    if 27.0 in letti and len(letti) == 2:
        # € 27 non è uno scaglione dell'art. 13 D.P.R. 115/2002: è l'anticipazione dell'art. 30, e l'altro importo è il
        # contributo. Il dubbio si scioglie da sé, senza chiedere all'avvocato.
        if not voce.get("richiedeConferma"):
            return ""
        contributo = next(n for n in letti if n != 27.0)
        return (f"Contributo letto {_euro(contributo)} ({_euro(27.0)} è l'anticipazione forfettaria, "
                f"{NORMA_ANTICIPAZIONE_FORFETTARIA}). " + _AVVISO_LETTURA)
    if len(letti) > 1:
        testo = f"Importi letti nelle ricevute: {', '.join(_euro(n) for n in letti)}"
        if 27.0 in letti:
            testo += f"; {_euro(27.0)} è l'anticipazione forfettaria ({NORMA_ANTICIPAZIONE_FORFETTARIA}), non il contributo unificato"
        return testo + ": confermare sulla ricevuta l'importo del contributo."
    if voce.get("richiedeConferma"):
        return _AVVISO_LETTURA
    return ""


_AVVISO_LETTURA = "Lettura della ricevuta incerta (testo non nitido o importo non leggibile): aprirla e verificare importo, data e procedimento."


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
    inviti = [_documento(d) for d in voce.get("invitiRideposito") or []]
    id_inviti = {d["id"] for d in inviti}
    esenzioni = [d for d in documenti if _testo(d.get("id")) not in id_inviti and (
        d.get("natura") == NATURA_AUTOCERTIFICAZIONE_CU
        or _ETICHETTA_ESENZIONE in _testo(d.get("etichetta")).lower()
    )]
    # Un atto di parte (ricorso, istanza, citazione) cita il contributo ma non è la ricevuta del versamento (G-16).
    versamenti = [d for d in documenti if _ETICHETTA_VERSAMENTO in _testo(d.get("etichetta")).lower()
                  and not _ATTO_DI_PARTE.match(_testo(d.get("nome")))]
    confronto = dict(voce.get("confronto") or {})
    verificata = dict(voce.get("esenzioneVerificata") or {})
    stato_voce = _testo(voce.get("status") or voce.get("stato")).lower()
    manuale = bool(voce.get("manuale"))
    nome_voce = _testo(voce.get("documento_fonte"))
    documento_voce = {"id": _testo(voce.get("documento_id")), "nome": nome_voce, "href": _testo(voce.get("href"))}
    if not esenzioni and documento_voce["id"] not in id_inviti and any(p in nome_voce.lower() for p in _INDIZI_ESENZIONE):
        esenzioni = [{**documento_voce, "confermato": manuale and stato_voce == "non_previsto"}]
    specifiche = [d for d in esenzioni if d.get("natura") == NATURA_AUTOCERTIFICAZIONE_CU]
    if specifiche and not any(d.get("id") == verificata.get("documento_id") for d in esenzioni):
        verificata = {}
    if esenzioni and not any(d.get("confermato") for d in versamenti):
        versamenti = []
    if (not versamenti and (not esenzioni or specifiche) and stato_voce == "pagato" and nome_voce
            and not any(d.get("id") == documento_voce["id"] for d in specifiche)):
        # Ricevuta registrata nella voce (dall'avvocato o dall'archivio delle letture) senza voce di catalogo.
        versamenti = [{**documento_voce, "confermato": manuale}]
    importo = _numero(voce.get("importo"))
    letti = {n for n in (_numero(v) for v in voce.get("importiLetti") or []) if n}
    if 27.0 in letti and len(letti) == 2:
        contributo = next(n for n in letti if n != 27.0)  # l'altro importo è il contributo (vedi avviso_importo)
        if importo in {None, 27.0, round(contributo + 27.0, 2)}:
            importo = contributo
    if confronto.get("esito") == "esente_per_legge":
        # Processo esente per legge (pct/contributo_esenzioni: art. 10 D.P.R. 115/2002, art. 46-bis disp. att. c.c.):
        # la ricevuta presente è quella dell'anticipazione forfettaria dell'art. 30, non del contributo.
        stato = _esito("esente_da_confermare" if confronto.get("dubbio") else "esente", importo=None,
                       norma=str(confronto.get("norma") or ""), fonti=[_documento(d) for d in versamenti],
                       ruolo_fonti="ricevuta dell'anticipazione forfettaria (art. 30 D.P.R. 115/2002)" if versamenti else "",
                       dettaglio=str(confronto.get("dettaglio") or "")
                       + (f" Da chiarire: {confronto['dubbio']}." if confronto.get("dubbio") else ""))
        stato["esenzioneLegge"] = {k: confronto.get(k) for k in ("norma", "motivo", "anticipazione", "dettaglio", "dubbio")}
        return stato
    if versamenti and esenzioni and verificata.get("certa") and not specifiche:
        versamenti = []  # esenzione certa: la ricevuta proposta non prevale
    if versamenti:
        fonti = [_documento(d) for d in versamenti]
        if confronto.get("esito") == "insufficiente":
            return _esito("da_verificare", importo=confronto.get("versato") or None, norma=confronto.get("norma") or NORMA_CU,
                          fonti=fonti, ruolo_fonti="ricevuta di versamento", dettaglio=confronto["dettaglio"])
        if confronto.get("esito") == "coincide":
            # Importo versato pari a quello dovuto per valore e rito: il versamento è certo (direttiva 10/11/2026).
            return _esito("pagato", importo=confronto["versato"], norma=confronto.get("norma") or NORMA_CU, fonti=fonti,
                          ruolo_fonti="ricevuta di versamento", dettaglio=confronto["dettaglio"])
        da_confermare = avviso_importo(voce)
        if da_confermare or not any(d.get("confermato") for d in versamenti):
            return _esito("pagato_da_confermare", importo=None if da_confermare else importo, norma=NORMA_CU,
                          fonti=fonti, ruolo_fonti="ricevuta di versamento",
                          dettaglio=da_confermare or "Il documento non è stato riconosciuto con certezza come ricevuta del "
                                                    "contributo: aprirlo e confermare importo e procedimento.")
        return _esito("pagato", importo=importo, norma=NORMA_CU, fonti=fonti, ruolo_fonti="ricevuta di versamento",
                      dettaglio="" if importo else "Importo da riportare dalla ricevuta.")
    if inviti:
        return _esito(
            "da_verificare", importo=None, norma=NORMA_ESENZIONE_CU, fonti=inviti,
            ruolo_fonti="invito al rideposito",
            dettaglio="Il fascicolo contiene un invito a ridepositare l’autocertificazione. "
                     "Verificare il deposito successivo e la dichiarazione relativa all’anno di reddito richiesto.",
        )
    if esenzioni:
        if verificata.get("certa"):
            return _esito("esente", importo=None, norma=NORMA_ESENZIONE_CU, fonti=[_documento(d) for d in esenzioni],
                          ruolo_fonti="autocertificazione del reddito", dettaglio=verificata["motivo"])
        confermata = any(d.get("confermato") for d in esenzioni if d.get("natura") != NATURA_AUTOCERTIFICAZIONE_CU)
        if specifiche and not confermata:
            return _esito("da_verificare", importo=None, norma=NORMA_ESENZIONE_CU,
                          fonti=[_documento(d) for d in esenzioni], ruolo_fonti="autocertificazione del reddito",
                          dettaglio=verificata.get("motivo") or
                          "Autocertificazione collegata. Verificare la prova di deposito, l’anno di reddito e la soglia.")
        if not confermata and verificata.get("motivo"):
            return _esito("esente_da_confermare", importo=None, norma=NORMA_ESENZIONE_CU, fonti=[_documento(d) for d in esenzioni],
                          ruolo_fonti="autocertificazione del reddito", dettaglio=verificata["motivo"])
        return _esito("esente" if confermata else "esente_da_confermare", importo=None, norma=NORMA_ESENZIONE_CU,
                      fonti=[_documento(d) for d in esenzioni], ruolo_fonti="autocertificazione del reddito",
                      dettaglio="Esenzione per reddito con autocertificazione depositata." if confermata else
                      "Il documento non è stato riconosciuto con certezza come autocertificazione del reddito: aprirlo e "
                      "confermarlo (anno di reddito, soglia).")
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
