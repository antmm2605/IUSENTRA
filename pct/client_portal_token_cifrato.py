"""Il token del Portale Cliente conservato cifrato, per poterlo rimostrare.

Il database conserva del token solo l'impronta (`token_hash`): e' la scelta
giusta per verificarlo, ma significa che il link esiste soltanto nell'istante
in cui nasce e nessuno puo' piu' rileggerlo — nemmeno l'avvocato che lo ha
generato ieri e deve rimandarlo al cliente.

Qui il token si conserva **cifrato a riposo** con AES-256-GCM, la stessa
protezione dei documenti del fascicolo, e si decifra solo per l'avvocato
autenticato. Chi mettesse le mani su un backup otterrebbe testo cifrato inutile
senza la chiave.

**Fail-closed**: senza `PCT_DOC_KEY` non si conserva nulla. Non esiste un
ripiego in chiaro: un link del portale e' una credenziale d'accesso ai dati del
cliente, e scriverla leggibile «per comodita'» sarebbe peggio del problema che
risolve. Quando non c'e' chiave, il link resta rigenerabile e basta.

Base normativa: GDPR 2016/679 art. 32 § 1 lett. a) (cifratura dei dati
personali come misura tecnica adeguata) e CAD D.Lgs. 82/2005 art. 51.
"""

from __future__ import annotations

import base64

#: Marcatore del token cifrato: distingue un valore nostro da qualsiasi altro.
MARCATORE = "cpt1:"


def cifratura_disponibile() -> bool:
    """Se il server ha la chiave con cui cifrare e decifrare il token."""
    from pct.document_crypto import doc_key

    return doc_key() is not None


def cifra_token(token: str) -> str:
    """Il token cifrato, pronto da conservare. Stringa vuota se non si puo'.

    Senza chiave non si conserva nulla: meglio un link da rigenerare che una
    credenziale leggibile nel database.
    """
    testo = str(token or "").strip()
    if not testo or not cifratura_disponibile():
        return ""
    from pct.document_crypto import encrypt_doc

    cifrato = encrypt_doc(testo.encode("utf-8"))
    return MARCATORE + base64.b64encode(cifrato).decode("ascii")


def decifra_token(valore: str) -> str:
    """Il token in chiaro per l'avvocato autenticato; vuoto se non recuperabile.

    Vuoto significa «non si puo' rimostrare»: nessuna chiave, nessun valore
    conservato (invito creato prima di questa protezione) o dato manomesso. In
    tutti questi casi la strada e' rigenerare il link, non indovinarlo.
    """
    testo = str(valore or "").strip()
    if not testo.startswith(MARCATORE) or not cifratura_disponibile():
        return ""
    from pct.document_crypto import decrypt_doc

    try:
        cifrato = base64.b64decode(testo[len(MARCATORE) :].encode("ascii"), validate=True)
        return decrypt_doc(cifrato).decode("utf-8").strip()
    except Exception:
        return ""


__all__ = ["MARCATORE", "cifra_token", "cifratura_disponibile", "decifra_token"]
