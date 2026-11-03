"""Le tre fonti del collegamento certo di una notifica L. 53/1994 al fascicolo, nell'ordine di certezza.

1. ``eml_nel_fascicolo``: l'.eml della notifica o della ricevuta è già tra i documenti di un fascicolo
   (stessa impronta SHA-256 del messaggio o stesso Message-ID); ``notifica_id``: il codice ``[Notifica_ID:…]``
   dell'oggetto è registrato in un solo fascicolo (notifiche preparate da IUSENTRA);
2. ``stesso_invio``: la ricevuta si riferisce a un messaggio originale collegato (o l'originale ha una ricevuta
   collegata): tutto l'invio va nello stesso fascicolo;
3. ``ruolo_cliente_ufficio``: numero di ruolo con anno, nome del cliente e ufficio coincidono con un solo
   fascicolo (``pct.pec_collegamento_certo.cerca_collegamento_certo``), letti anche dalla relata allegata
   (``relata``: art. 3-bis, comma 5, L. 53/1994) con l'ufficio della relata.

Fail-closed: se una fonte indica più fascicoli, o fonti diverse indicano fascicoli diversi per lo stesso invio,
nessun collegamento. Nessun ``from __future__``: il file si concatena allo script di sola lettura del server.
"""

import re
from collections import defaultdict

L53 = re.compile(r"notificazione\s+ai\s+sensi\s+della\s+legge\s+n\.?\s*53|\[notifica_id:", re.IGNORECASE)
#: Stato del collegamento nel linker del presidio (pct.pec_pipeline.LINK_STATI_CERTIFICATI): decisione dell'avvocato
#: del 03/11/2026, i collegamenti ricavati da queste fonti contano come certi.
STATO_CERTIFICATO = "notifica_l53_verificata"
VERSIONE_REGOLA = "2"  # 2: relata allegata e Notifica_ID
_NOTIFICA_ID = re.compile(r"\[?notifica_id\s*:\s*([A-Za-z0-9_-]{4,64})", re.IGNORECASE)


def notifica_id(testo):
    """Il codice Notifica_ID nel testo (oggetto della PEC o metadati di un documento), o stringa vuota."""
    trovato = _NOTIFICA_ID.search(str(testo or ""))
    return trovato.group(1).casefold() if trovato else ""


def _norm_id(valore):
    return str(valore or "").strip().strip("<>").casefold()


def chiave_invio(messaggio):
    """L'invio a cui appartiene il messaggio: il Message-ID dell'originale per le ricevute, il proprio per l'invio."""
    return _norm_id(messaggio.get("originale")) or _norm_id(messaggio.get("message_id")) or "__" + str(messaggio.get("id"))


def _unico(insieme):
    return next(iter(insieme)) if len(insieme) == 1 else ""


def collega_tutti(messaggi, *, indice_impronte, indice_message_id, certo_per_messaggio, indice_notifica_id=None):
    """Per ogni messaggio {fascicolo_id, fonte, motivo}.

    ``messaggi``: dict con id, message_id, originale, sha256; ``indice_impronte``/``indice_message_id``: valore →
    insieme di fascicoli che contengono quell'.eml; ``certo_per_messaggio``: callable(messaggio) → id fascicolo
    dei tre controlli (stringa vuota se non certo).
    """
    esito = {}
    gruppi = defaultdict(list)
    for m in messaggi:
        gruppi[chiave_invio(m)].append(m)
    for membri in gruppi.values():
        diretti, fonti = {}, {}
        for m in membri:
            trovati = set(indice_impronte.get(str(m.get("sha256") or "").casefold(), ())) | set(indice_message_id.get(_norm_id(m.get("message_id")), ()))
            codice = notifica_id(m.get("oggetto"))
            dal_codice = set((indice_notifica_id or {}).get(codice, ())) if codice else set()
            fonti[m["id"]] = "eml_nel_fascicolo" if trovati else "notifica_id"
            trovati |= dal_codice
            if len(trovati) > 1:
                diretti[m["id"]] = None  # lo stesso .eml in più fascicoli: nessuna certezza
            elif trovati:
                diretti[m["id"]] = next(iter(trovati))
        fascicoli_diretti = {f for f in diretti.values() if f}
        if None in diretti.values() or len(fascicoli_diretti) > 1:
            for m in membri:
                esito[m["id"]] = {"fascicolo_id": "", "fonte": "", "motivo": "fascicoli_discordanti"}
            continue
        if fascicoli_diretti:
            fascicolo = _unico(fascicoli_diretti)
            for m in membri:
                fonte = fonti[m["id"]] if m["id"] in diretti else "stesso_invio"
                esito[m["id"]] = {"fascicolo_id": fascicolo, "fonte": fonte, "motivo": fonte}
            continue
        certi = {m["id"]: certo_per_messaggio(m) for m in membri}
        trovati = {f for f in certi.values() if f}
        fascicolo = _unico(trovati)
        for m in membri:
            if fascicolo:
                fonte = "ruolo_cliente_ufficio" if certi[m["id"]] else "stesso_invio"
                esito[m["id"]] = {"fascicolo_id": fascicolo, "fonte": fonte, "motivo": fonte}
            else:
                esito[m["id"]] = {"fascicolo_id": "", "fonte": "", "motivo": "piu_fascicoli" if trovati else "nessuna_fonte_certa"}
    return esito
