"""Obblighi di notifica per codice del termine, con le norme del registro ``pct/procedura_fasi/fonti.py``.

Testi verificati sull'archivio Normattiva il 05/11/2026 (``pct/procedura_fasi/fonti_notifiche.py``).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Obbligo:
    atti: str
    destinatari: str
    a_cura_di: str
    norme: tuple[str, ...]
    nota: str = ""
    impugnazione: bool = False
    #: modalità propria dell'atto (testo, norme), al posto delle regole generali sul destinatario
    come: tuple[tuple[str, tuple[str, ...]], ...] = ()
    #: che cosa depositare dopo, se diverso dal deposito della notifica nel fascicolo telematico
    dopo: str = ""


_DEPOSITO_CIVILE = ("Depositare nel fascicolo telematico la notifica eseguita (atto notificato, relata, ricevute di "
                    "accettazione e di consegna) con l'attestazione di conformità prima dell'udienza.")

_COME_PENALE = (("Notifica del difensore a mezzo PEC o altro servizio elettronico di recapito certificato qualificato, oppure "
                 "copia dell'atto con raccomandata con avviso di ricevimento.", ("cpp_152",)),)

OBBLIGHI: dict[str, Obbligo] = {
    "LAV_415_NOTIFICA_DIECI_GIORNI": Obbligo(
        "Ricorso e decreto di fissazione dell'udienza di discussione", "Convenuto", "Ricorrente", ("cpc_415",),
        "Tra la notifica e l'udienza devono restare almeno 30 giorni liberi (40 se il convenuto è all'estero)."),
    "LAV_415_NOTIFICA_TRENTA_GIORNI": Obbligo(
        "Ricorso e decreto di fissazione dell'udienza di discussione", "Convenuto", "Ricorrente", ("cpc_415",),
        "Almeno 30 giorni liberi prima dell'udienza (40 se il convenuto è all'estero)."),
    "LAV_435_NOTIFICA_DIECI_GIORNI": Obbligo(
        "Ricorso in appello e decreto di fissazione dell'udienza", "Appellato", "Appellante", ("cpc_435", "cpc_330"),
        "Tra la notifica e l'udienza devono restare almeno 25 giorni (60 se la notifica va eseguita all'estero).",
        impugnazione=True),
    "LAV_435_NOTIFICA_VENTICINQUE_GIORNI": Obbligo(
        "Ricorso in appello e decreto di fissazione dell'udienza", "Appellato", "Appellante", ("cpc_435", "cpc_330"),
        "Almeno 25 giorni prima dell'udienza (60 se la notifica va eseguita all'estero).", impugnazione=True),
    "CIV_281UNDECIES_NOTIFICA": Obbligo(
        "Ricorso e decreto di fissazione dell'udienza", "Convenuto", "Ricorrente", ("cpc_281undecies",),
        "Almeno 40 giorni liberi prima dell'udienza (60 se il luogo della notifica è all'estero)."),
    "FAM_473BIS_NOTIFICA": Obbligo(
        "Ricorso e decreto di fissazione dell'udienza", "Convenuto", "Attore", ("cpc_473bis14",),
        "Almeno 60 giorni liberi prima dell'udienza (90 se la notifica va eseguita all'estero); il decreto è comunicato "
        "al pubblico ministero a cura della cancelleria."),
    "CIV_DI_NOTIFICA_644": Obbligo(
        "Ricorso e decreto ingiuntivo, in copia conforme", "Ingiunto", "Ricorrente", ("cpc_643", "cpc_644"),
        "Entro 60 giorni dalla pronuncia (90 se la notifica va eseguita all'estero), altrimenti il decreto diventa inefficace."),
    "CIV_INTIMAZIONE_TESTI_103": Obbligo(
        "Intimazione a comparire all'udienza fissata per la prova", "Testimoni ammessi", "Parte che ha chiesto la prova",
        ("cpc_250", "dispatt_103"), "Almeno 7 giorni prima dell'udienza; con l'autorizzazione del giudice il termine può essere ridotto.",
        come=(("Intimazione del difensore con raccomandata con avviso di ricevimento o a mezzo PEC.", ("cpc_250",)),
              ("Oppure richiesta all'ufficiale giudiziario.", ("cpc_250",))),
        dopo="Depositare copia dell'atto inviato e della ricevuta di consegna."),
    "PEN_GDP_27_NOTIFICA": Obbligo(
        "Decreto di convocazione e ricorso immediato",
        "Pubblico ministero, persona citata in giudizio e suo difensore; altre persone offese note", "Ricorrente",
        ("dlgs274_art27", "cpp_152"), "Almeno 20 giorni prima dell'udienza."),
    # Termini assegnati dal giudice su obblighi che la legge prevede: la scadenza è quella scritta nel provvedimento.
    "CIV_102_INTEGRAZIONE": Obbligo(
        "Atto di integrazione del contraddittorio con il provvedimento che la ordina", "Le parti indicate dal giudice",
        "Parte onerata dal giudice", ("cpc_102",), "Il termine è perentorio: se l'ordine non è eseguito il processo si estingue."),
    "AMM_49_INTEGRAZIONE": Obbligo(
        "Ricorso, con il provvedimento che ordina l'integrazione", "Le parti indicate dal giudice", "Ricorrente", ("cpa_49",),
        "Il ricorso va notificato e poi depositato nel termine fissato dal giudice."),
    "TRIB_58_INTEGRAZIONE": Obbligo(
        "Atto di chiamata in causa dei litisconsorti", "I soggetti interessati inscindibilmente indicati dal giudice",
        "Parte onerata dal giudice", ("tu175_art58",), "Il termine è stabilito a pena di decadenza."),
    "CIV_291_RINNOVAZIONE": Obbligo(
        "Citazione (o ricorso) e provvedimento, con una nuova notificazione", "Convenuto non costituito", "Attore", ("cpc_291",),
        "Il termine è perentorio: se la rinnovazione non è eseguita la causa è cancellata dal ruolo e il processo si estingue."),
    "AMM_44_RINNOVAZIONE": Obbligo(
        "Ricorso, con una nuova notificazione", "Destinatario non costituito", "Ricorrente", ("cpa_44",),
        "Il termine è perentorio; la rinnovazione impedisce ogni decadenza."),
    "CIV_164_RINNOVAZIONE": Obbligo(
        "Citazione rinnovata, priva del vizio rilevato dal giudice", "Convenuto non costituito", "Attore", ("cpc_164",),
        "Il termine è perentorio: se la rinnovazione non è eseguita la causa è cancellata dal ruolo e il processo si estingue."),
    "CIV_269_CHIAMATA_TERZO": Obbligo(
        "Citazione del terzo, con il decreto che differisce l'udienza", "Terzo chiamato in causa",
        "Convenuto, o attore autorizzato dal giudice", ("cpc_269", "cpc_163bis"),
        "Entro il termine del giudice e lasciando almeno 120 giorni liberi prima dell'udienza (150 se il terzo è all'estero).",
        dopo="Depositare la citazione notificata entro il termine dell'art. 165 c.p.c. (dieci giorni dalla notifica)."),
    "CIV_669SEXIES_NOTIFICA": Obbligo(
        "Ricorso cautelare e decreto", "Controparte", "Ricorrente", ("cpc_669sexies",),
        "Termine perentorio assegnato dal giudice, non superiore a otto giorni (triplicato se la notifica va eseguita all'estero); "
        "all'udienza il giudice conferma, modifica o revoca il decreto."),
    "CIV_618_NOTIFICA": Obbligo(
        "Ricorso in opposizione e decreto di fissazione dell'udienza",
        "Le parti del processo esecutivo indicate nel decreto (creditore procedente, creditori intervenuti; nell'opposizione di "
        "terzo anche il debitore)", "Opponente", ("cpc_618", "cpc_619"), "Il termine fissato dal giudice dell'esecuzione è perentorio.",
        come=(("Ai creditori di regola presso il difensore che li rappresenta nel processo esecutivo; verificarlo nel fascicolo "
               "dell'esecuzione.", ("cpc_170",)),
              ("A chi non è costituito, all'indirizzo PEC dei pubblici elenchi.", ("l53_art3bis", "dl179_art16ter")),
              ("Senza PEC nei pubblici elenchi, tramite l'ufficiale giudiziario.", ("cpc_137",)))),
    # Penale: atti dello studio che la legge vuole notificati a cura di chi li presenta.
    "PEN_78_NOTIFICA": Obbligo(
        "Dichiarazione di costituzione di parte civile presentata fuori udienza", "Le altre parti del procedimento",
        "Parte civile", ("cpp_78", "cpp_79"),
        "La costituzione produce effetto per ciascuna parte solo dal giorno della notifica a quella parte.",
        come=_COME_PENALE),
    "PEN_395_NOTIFICA": Obbligo(
        "Richiesta di incidente probatorio", "Pubblico ministero e persone indicate nella richiesta (art. 393 c.p.p.)",
        "Chi ha proposto la richiesta", ("cpp_395", "cpp_396"),
        "Dalla notifica decorrono i due giorni per le deduzioni; il giudice decide dopo il deposito della prova della notifica.",
        come=_COME_PENALE, dopo="Depositare in cancelleria la prova della notificazione (art. 395 c.p.p.)."),
}

#: termine di notifica assegnato dal giudice nel dispositivo (``PROVV_NOTIFICA``) o di cui manca il codice
GENERICO = Obbligo("Gli atti indicati nel provvedimento", "Le parti indicate nel provvedimento", "Parte onerata dal giudice", (),
                   "Il termine è quello assegnato dal giudice: verificare nel provvedimento atti e destinatari.")


def obbligo_per_codice(codice: str) -> Obbligo:
    return OBBLIGHI.get(str(codice or "").strip().upper(), GENERICO)


__all__ = ["GENERICO", "OBBLIGHI", "Obbligo", "obbligo_per_codice"]
