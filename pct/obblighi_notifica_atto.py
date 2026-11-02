"""Una voce per atto negli obblighi di notifica: copie riunite, prove dell'atto, fase già superata.

`pct.obblighi_notifica` calcola l'obbligo documento per documento. Lo stesso
atto però può stare nel fascicolo in più copie (l'originale importato e
l'originale notificato con relata e ricevute): qui le copie dello stesso atto
diventano una sola voce, e la voce tiene conto di ciò che il fascicolo già
dimostra.

Regole:

1. **Una voce per atto.** Stessa regola (stessa natura dell'atto, stesso
   procedimento del fascicolo) e date dell'atto compatibili (uguali o una sola
   letta): una voce con tutte le copie come fonti. Due atti della stessa
   natura con date diverse restano due voci.
2. **Prova dell'atto.** Una prova verificata in una qualunque copia chiude la
   voce («Notificato»). Una relata o una ricevuta lette in una copia ma non
   ancora complete o confermate non lasciano la voce «Da notificare»: diventa
   «Da verificare» con la prova da controllare (art. 3-bis, comma 3, e art. 9
   L. 53/1994: la notifica si perfeziona con la ricevuta di avvenuta consegna).
3. **Fase superata.** La notifica dell'atto introduttivo non si propone come
   da fare quando il procedimento è andato oltre: sentenza nel fascicolo
   (art. 132 c.p.c.; art. 429 c.p.c. nel rito del lavoro), udienza già tenuta
   (art. 420 c.p.c.; art. 183 c.p.c.) o fascicolo definito. Con prove di
   notifica nel fascicolo la voce è «Notificato» con le prove; senza prove la
   voce non si propone. Nessuna regola facoltativa (notifica della sentenza,
   artt. 285, 325, 326 c.p.c.) viene toccata.
"""

from __future__ import annotations

from typing import Any

from pct.obblighi_notifica import STATO_DA_NOTIFICARE, STATO_DA_VERIFICARE, STATO_FACOLTATIVO, STATO_NOTIFICATO

# Atti che introducono il giudizio (o la fase): la loro notifica precede l'udienza e la decisione.
REGOLE_ATTO_INTRODUTTIVO = frozenset({
    "lavoro_415", "semplificato_281undecies", "citazione_163bis", "sfratto_660",
    "decreto_ingiuntivo_644", "opposizione_di_645", "ricorso_tar_41",
})
_ORDINE = {STATO_NOTIFICATO: 0, STATO_DA_NOTIFICARE: 1, STATO_FACOLTATIVO: 2, STATO_DA_VERIFICARE: 3}


def _data_italiana(iso: str) -> str:
    anno, mese, giorno = (str(iso or "")[:10].split("-") + ["", "", ""])[:3]
    return f"{giorno}/{mese}/{anno}" if anno and mese and giorno else str(iso or "")


def fase_superata(contesto: dict[str, Any]) -> str:
    """Il motivo per cui il procedimento è oltre la notifica dell'atto introduttivo, o stringa vuota."""
    if contesto.get("fascicolo_definito"):
        return "Il fascicolo è definito: la notifica dell'atto introduttivo non è più un adempimento da fare."
    if contesto.get("sentenze"):
        return "Nel fascicolo c'è la sentenza: il procedimento è oltre la notifica dell'atto introduttivo."
    tenute = sorted(contesto.get("udienze_tenute") or ())
    if tenute:
        return (f"Udienza già tenuta il {_data_italiana(tenute[-1])}: "
                "il procedimento è oltre la notifica dell'atto introduttivo.")
    return ""


def _compatibili(uno: dict[str, Any], altro: dict[str, Any]) -> bool:
    if uno.get("regola") != altro.get("regola"):
        return False
    a, b = str(uno.get("dataAtto") or ""), str(altro.get("dataAtto") or "")
    return not a or not b or a == b


def _migliore(voci: list[dict[str, Any]]) -> dict[str, Any]:
    return min(voci, key=lambda v: (_ORDINE.get(v.get("stato"), 9), 0 if v.get("scadenza") else 1, len(v.get("dati_mancanti") or ())))


def _fonti(voci: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fonti: list[dict[str, Any]] = []
    for voce in voci:
        for fonte in voce.get("fonti_documentali") or [{"documentoId": voce.get("documentoId"), "documento": voce.get("documento"), "chiave": voce.get("chiave")}]:
            if not any(f.get("documentoId") == fonte.get("documentoId") for f in fonti):
                fonti.append(dict(fonte))
    return fonti


def _prove(contesto: dict[str, Any], copie: set[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(prove lette nelle copie dell'atto, altre prove di notifica del fascicolo)."""
    # La prova letta nella copia di un altro atto (ad esempio la sentenza notificata) è di quell'atto.
    altri_atti = set(contesto.get("documenti_atti") or ()) - copie
    dell_atto, altre = [], []
    for prova in contesto.get("prove_notifica") or ():
        if not (prova.get("relata") or prova.get("consegna") or prova.get("verificata")):
            continue
        if prova.get("atto_documento_id") in copie or prova.get("documento_id") in copie:
            dell_atto.append(prova)
        elif not prova.get("atto_documento_id") and prova.get("documento_id") not in altri_atti:
            altre.append(prova)
    return dell_atto, altre


def _nomi(prove: list[dict[str, Any]], nomi: dict[str, str]) -> str:
    return ", ".join(f"«{nomi.get(str(p.get('documento_id')), p.get('documento_id'))}»" for p in prove[:4])


def una_voce_per_atto(obblighi: list[dict[str, Any]], contesto: dict[str, Any]) -> list[dict[str, Any]]:
    """Le voci degli obblighi riunite per atto, con le prove e la fase del procedimento."""
    gruppi: list[list[dict[str, Any]]] = []
    for voce in obblighi:
        gruppo = next((g for g in gruppi if _compatibili(g[0], voce)), None)
        if gruppo is None:
            gruppi.append([voce])
        else:
            gruppo.append(voce)
    nomi = dict(contesto.get("nomi_documenti") or {})
    superata = fase_superata(contesto)
    esito: list[dict[str, Any]] = []
    for gruppo in gruppi:
        voce = dict(_migliore(gruppo))
        voce["fonti_documentali"] = _fonti(gruppo)
        copie = {str(f.get("documentoId")) for f in voce["fonti_documentali"]}
        nomi.update({str(f.get("documentoId")): str(f.get("documento") or "") for f in voce["fonti_documentali"]})
        if voce.get("stato") in {STATO_NOTIFICATO, STATO_FACOLTATIVO} or voce.get("facoltativa"):
            esito.append(voce)
            continue
        dell_atto, altre = _prove(contesto, copie)
        if superata and (voce.get("regola") in REGOLE_ATTO_INTRODUTTIVO or contesto.get("fascicolo_definito")):
            if not (dell_atto or altre):
                continue  # fase superata e nessuna prova: la notifica non si propone come da fare
            prove = dell_atto or altre
            voce.update(stato=STATO_NOTIFICATO, scadenza="", calcoli=[], dati_mancanti=[],
                        motivo=f"Notifica eseguita: prove di notifica nel fascicolo ({_nomi(prove, nomi)}). {superata}",
                        prove_documenti=[str(p.get("documento_id")) for p in prove])
        elif dell_atto:
            voce.update(stato=STATO_DA_VERIFICARE,
                        motivo=(f"Prova di notifica dell'atto nel fascicolo ({_nomi(dell_atto, nomi)}): conferma relata e ricevuta "
                                "di avvenuta consegna invece di notificare di nuovo. " + str(voce.get("motivo") or "")).strip(),
                        prove_documenti=[str(p.get("documento_id")) for p in dell_atto])
        esito.append(voce)
    ordine = {STATO_DA_NOTIFICARE: 0, STATO_DA_VERIFICARE: 1, STATO_FACOLTATIVO: 2, STATO_NOTIFICATO: 3}
    return sorted(esito, key=lambda o: (ordine.get(o.get("stato"), 9), o.get("scadenza") or "9999"))


__all__ = ["REGOLE_ATTO_INTRODUTTIVO", "fase_superata", "una_voce_per_atto"]
