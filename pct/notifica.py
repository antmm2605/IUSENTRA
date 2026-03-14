"""
Gestione delle notifiche telematiche via PEC (art. 3-bis L. 53/1994).

Le notifiche in proprio degli avvocati avvengono:
- Via PEC agli indirizzi presenti nei pubblici elenchi (ReGINde, IPA, ANPR)
- Con firma digitale sull'atto e sulla relata di notifica
- Con produzione di ricevute PEC come prova della notifica
"""

from datetime import datetime
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass

from .pec import ClientPEC, ConfigPEC
from .firma import FirmaDigitale


@dataclass
class RelataDiNotifica:
    """Relata di notifica telematica (art. 3-bis L. 53/1994)."""

    notificante: str
    cf_notificante: str
    pec_notificante: str
    destinatario: str
    cf_destinatario: str
    pec_destinatario: str
    atto_notificato: str
    data_ora: str
    numero_procedimento: Optional[str] = None
    autorita_giudiziaria: Optional[str] = None


class NotificaTelematica:
    """
    Gestisce le notifiche telematiche tra avvocati e verso le parti.

    Procedura:
    1. Predisposizione atto da notificare (PDF/A firmato digitalmente)
    2. Redazione relata di notifica
    3. Firma digitale della relata
    4. Invio PEC all'indirizzo del destinatario (da ReGINde/IPA)
    5. Salvataggio ricevute come prova della notifica
    """

    def __init__(self, config_pec: ConfigPEC, firma: Optional[FirmaDigitale] = None):
        self.pec = ClientPEC(config_pec)
        self.firma = firma

    def notifica(
        self,
        atto_path: str,
        pec_destinatario: str,
        relata: RelataDiNotifica,
        allegati: Optional[List[str]] = None,
    ) -> dict:
        """
        Esegue la notifica telematica.

        Args:
            atto_path: Percorso all'atto da notificare (firmato)
            pec_destinatario: Indirizzo PEC del destinatario
            relata: Dati della relata di notifica
            allegati: Eventuali allegati aggiuntivi

        Returns:
            Esito della notifica con ricevute
        """
        if not self.pec.verifica_indirizzo_pec(pec_destinatario):
            return {
                "esito": "ERRORE",
                "messaggio": f"Indirizzo PEC non valido: {pec_destinatario}",
            }

        # Crea busta per notifica (atto + relata firmata)
        from .busta import BustaTelematica, DatiBusta, Allegato
        import uuid

        allegati_notifica = []
        if allegati:
            for all_path in allegati:
                allegati_notifica.append(
                    Allegato(
                        percorso=all_path,
                        descrizione=Path(all_path).stem,
                        tipo="ALLEGATO",
                    )
                )

        dati = DatiBusta(
            codice_ufficio="",
            codice_registro="",
            oggetto=f"Notifica - {relata.atto_notificato}",
            tipo_atto="NOTIFICA",
            atto_principale=atto_path,
            allegati=allegati_notifica,
            cf_mittente=relata.cf_notificante,
            operatore=relata.notificante,
        )

        busta = BustaTelematica(dati)
        output_dir = f"./notifiche/{uuid.uuid4().hex[:8]}"
        busta_path = busta.crea_busta(output_dir)

        esito_invio = self.pec.invia_busta(
            destinatario_pec=pec_destinatario,
            busta_path=busta_path,
            oggetto=f"Notifica telematica - {relata.atto_notificato}",
            corpo=self._corpo_notifica(relata),
        )

        ricevute = {}
        if esito_invio["inviato"]:
            ricevute = self.pec.attendi_ricevute(timeout=120)

        return {
            "esito": "NOTIFICATO" if esito_invio["inviato"] else "ERRORE",
            "busta_path": busta_path,
            "pec_destinatario": pec_destinatario,
            "ricevuta_accettazione": ricevute.get("accettazione"),
            "ricevuta_consegna": ricevute.get("consegna"),
            "messaggio": esito_invio.get("errore", "Notifica eseguita correttamente"),
        }

    def _corpo_notifica(self, relata: RelataDiNotifica) -> str:
        """Genera il corpo del messaggio PEC per la notifica."""
        return (
            f"Notifica telematica ai sensi dell'art. 3-bis L. 53/1994\n\n"
            f"Notificante: {relata.notificante}\n"
            f"PEC Notificante: {relata.pec_notificante}\n"
            f"Destinatario: {relata.destinatario}\n"
            f"Atto notificato: {relata.atto_notificato}\n"
            f"Data e ora: {relata.data_ora}\n"
        )

    def genera_relata(self, relata: RelataDiNotifica, output_path: str) -> str:
        """
        Genera il documento di relata di notifica in formato testo/PDF.

        Args:
            relata: Dati della relata
            output_path: Percorso dove salvare la relata

        Returns:
            Percorso al file generato
        """
        contenuto = (
            "RELATA DI NOTIFICA TELEMATICA\n"
            "(art. 3-bis L. 53/1994)\n\n"
            f"Il sottoscritto {relata.notificante} (C.F. {relata.cf_notificante}),\n"
            f"con indirizzo PEC {relata.pec_notificante},\n"
            f"attesta di aver notificato in data {relata.data_ora}\n"
            f"il seguente atto: {relata.atto_notificato}\n\n"
            f"al destinatario {relata.destinatario}\n"
            f"(C.F. {relata.cf_destinatario})\n"
            f"all'indirizzo PEC {relata.pec_destinatario}\n"
            f"estratto dai pubblici elenchi (ReGINde/IPA/ANPR).\n\n"
        )
        if relata.numero_procedimento:
            contenuto += f"Procedimento: {relata.numero_procedimento}\n"
        if relata.autorita_giudiziaria:
            contenuto += f"Autorità giudiziaria: {relata.autorita_giudiziaria}\n"

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(contenuto)
        return output_path
