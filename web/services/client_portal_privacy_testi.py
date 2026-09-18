"""L'informativa privacy del Portale Cliente: testo governato e versionato.

Il pannello «Privacy e consensi» mostrava la sola chiave del consenso e un
pulsante «Accetta»: il cliente accettava qualcosa che non aveva potuto
leggere. Un consenso cosi' non regge — l'art. 7 § 1 GDPR chiede al titolare di
**dimostrare** che il consenso e' stato prestato, e gli artt. 13-14 impongono
che l'informativa sia resa *prima*.

Qui il testo vive sul server, come gia' accade per i consensi della firma
(`client_portal_signing_texts`): il browser lo mostra, ma quello che viene
registrato e' sempre il testo canonico di questo modulo, mai una stringa
arrivata dal client. Alla versione si aggancia la prova: cambiando il testo si
alza `VERSIONE_INFORMATIVA` e i consensi gia' prestati restano legati alla
versione che l'interessato ha davvero letto.

Le finalita' dichiarate sono quelle che il portale esegue davvero: nessuna
voce di comodo, nessuna finalita' che il software non svolge.

Base normativa: Regolamento (UE) 2016/679, artt. 5, 6, 7, 13, 15-22 e 32;
D.Lgs. 196/2003 come adeguato dal D.Lgs. 101/2018; L. 247/2012 art. 6 e Codice
deontologico forense art. 13 (segreto professionale).
"""

from __future__ import annotations

from typing import Any

#: Si alza quando cambia il testo: la prova del consenso resta legata alla
#: versione che l'interessato ha letto.
VERSIONE_INFORMATIVA = "2026-09"

CHIAVE_INFORMATIVA = "privacy_portale_cliente"

TITOLO_INFORMATIVA = "Informativa sul trattamento dei dati personali — Portale Cliente"

#: Le sezioni dell'informativa. Restano separate per poterle mostrare come
#: capitoli leggibili invece di un muro di testo.
SEZIONI_INFORMATIVA: tuple[tuple[str, str], ...] = (
    (
        "Chi tratta i suoi dati",
        "Titolare del trattamento è lo studio legale indicato in calce, che lei ha "
        "incaricato o con cui è in contatto per un incarico professionale. I "
        "recapiti per ogni richiesta relativa ai suoi dati sono quelli dello studio.",
    ),
    (
        "Quali dati e perché",
        "Attraverso questo portale lo studio tratta i dati anagrafici e di contatto "
        "che lei conferma o corregge, i documenti che carica, i messaggi che "
        "scambia con lo studio, le firme che appone e gli appuntamenti concordati. "
        "Le finalità sono tre: eseguire l'incarico professionale e difenderla, "
        "adempiere agli obblighi di legge che gravano sull'avvocato (fra cui "
        "l'identificazione e la conservazione documentale), e permetterle di "
        "seguire la sua pratica senza doversi recare in studio.",
    ),
    (
        "Su quale base giuridica",
        "Il trattamento per l'esecuzione dell'incarico si fonda sul contratto "
        "(art. 6 § 1 lett. b GDPR); quello per gli adempimenti di legge sull'obbligo "
        "legale (lett. c); quello necessario ad accertare, esercitare o difendere un "
        "diritto in sede giudiziaria sull'art. 9 § 2 lett. f per le categorie "
        "particolari di dati. L'uso di questo portale, in luogo dei canali "
        "tradizionali, si fonda sul suo consenso: può revocarlo in qualsiasi "
        "momento senza che ciò pregiudichi l'incarico, che proseguirà per le vie "
        "ordinarie.",
    ),
    (
        "Chi può vederli",
        "I suoi dati sono visibili allo studio e ai suoi collaboratori tenuti al "
        "segreto professionale. Possono essere comunicati ad autorità giudiziarie, "
        "controparti e loro difensori, consulenti tecnici e organismi di mediazione "
        "solo nella misura necessaria all'incarico, e ai fornitori tecnici che "
        "ospitano il servizio, nominati responsabili del trattamento. Non sono "
        "ceduti a terzi per finalità commerciali e non alimentano alcuna profilazione.",
    ),
    (
        "Dove restano e per quanto",
        "I dati sono conservati su server nell'Unione europea. I documenti sono "
        "cifrati a riposo e il collegamento è protetto. Restano per la durata "
        "dell'incarico e, dopo la sua conclusione, per il tempo in cui lo studio è "
        "tenuto a conservare il fascicolo e a poter provare la propria attività.",
    ),
    (
        "Che cosa può chiedere",
        "In qualsiasi momento può chiedere allo studio di accedere ai suoi dati, di "
        "correggerli, di cancellarli, di limitarne il trattamento, di riceverli in "
        "formato leggibile o di opporsi al trattamento (artt. 15-22 GDPR), e può "
        "revocare questo consenso. Se ritiene che il trattamento violi la legge può "
        "proporre reclamo al Garante per la protezione dei dati personali.",
    ),
    (
        "Che cosa succede se non acconsente",
        "Non usare il portale non le toglie nulla: lo studio continuerà a seguirla "
        "e a scambiare documenti e comunicazioni con i canali consueti. Il consenso "
        "riguarda questo strumento, non l'incarico.",
    ),
)

#: La frase che il cliente accetta: dichiara la lettura, non la sostituisce.
DICHIARAZIONE_INFORMATIVA = (
    "Dichiaro di aver letto l'informativa sul trattamento dei dati personali "
    "riportata sopra e acconsento al trattamento dei miei dati attraverso il "
    "Portale Cliente per le finalità indicate."
)


def _dati_studio() -> dict[str, str]:
    """I recapiti del titolare, dalla configurazione dello studio.

    Se la configurazione non e' leggibile si lasciano vuoti: e' preferibile
    un'informativa che non nomina il titolare — e lo si vede — a una che ne
    inventa i dati.
    """
    try:
        from web.helpers import get_config_studio

        config = get_config_studio()
        studio = getattr(config, "studio", None) or getattr(config, "dati_studio", None)
    except Exception:
        studio = None
    if studio is None:
        return {"nome": "", "indirizzo": "", "email": "", "telefono": ""}

    def _campo(nome: str) -> str:
        return " ".join(str(getattr(studio, nome, "") or "").split()).strip()

    indirizzo = " ".join(
        parte for parte in (_campo("indirizzo"), _campo("cap"), _campo("city"), _campo("province")) if parte
    )
    return {
        "nome": _campo("nome"),
        "indirizzo": indirizzo,
        "email": _campo("email"),
        "telefono": _campo("telefono"),
    }


def testo_informativa() -> str:
    """L'informativa completa in testo semplice, come viene registrata."""
    studio = _dati_studio()
    righe = [TITOLO_INFORMATIVA, ""]
    for titolo, corpo in SEZIONI_INFORMATIVA:
        righe.append(titolo)
        righe.append(corpo)
        righe.append("")
    titolare = ", ".join(parte for parte in (studio["nome"], studio["indirizzo"], studio["email"], studio["telefono"]) if parte)
    righe.append(f"Titolare del trattamento: {titolare}" if titolare else "Titolare del trattamento: lo studio legale incaricato.")
    righe.append(f"Versione dell'informativa: {VERSIONE_INFORMATIVA}")
    return "\n".join(righe).strip()


def informativa_payload() -> dict[str, Any]:
    """L'informativa per la pagina: sezioni leggibili, versione e dichiarazione."""
    return {
        "key": CHIAVE_INFORMATIVA,
        "version": VERSIONE_INFORMATIVA,
        "title": TITOLO_INFORMATIVA,
        "sections": [{"heading": titolo, "body": corpo} for titolo, corpo in SEZIONI_INFORMATIVA],
        "declaration": DICHIARAZIONE_INFORMATIVA,
        "controller": _dati_studio(),
        "text": testo_informativa(),
    }


__all__ = [
    "CHIAVE_INFORMATIVA",
    "DICHIARAZIONE_INFORMATIVA",
    "SEZIONI_INFORMATIVA",
    "TITOLO_INFORMATIVA",
    "VERSIONE_INFORMATIVA",
    "informativa_payload",
    "testo_informativa",
]
