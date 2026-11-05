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
}

#: termine di notifica assegnato dal giudice nel dispositivo (``PROVV_NOTIFICA``) o di cui manca il codice
GENERICO = Obbligo("Gli atti indicati nel provvedimento", "Le parti indicate nel provvedimento", "Parte onerata dal giudice", (),
                   "Il termine è quello assegnato dal giudice: verificare nel provvedimento atti e destinatari.")


def obbligo_per_codice(codice: str) -> Obbligo:
    return OBBLIGHI.get(str(codice or "").strip().upper(), GENERICO)


__all__ = ["GENERICO", "OBBLIGHI", "Obbligo", "obbligo_per_codice"]
