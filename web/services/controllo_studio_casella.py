"""Stato di lettura della casella SQL; trasporto e contenuti PEC restano invariati."""
from pct.email_client import GestioneEmailRicevute
from web.services.controllo_studio_letture import repository
from web.services.registro_letture_runtime import utente_corrente_id

class CasellaConLettureSQL(GestioneEmailRicevute):
    def _carica(self):
        cached = self._cache is not None
        db = super()._carica()
        if not cached:
            for eid, (stato, letta_il) in repository().stati_pec().items():
                if eid in db:
                    db[eid].stato, db[eid].letta_il = stato, letta_il
        return db

    def marca_letta(self, id_email):
        db = self._carica()
        if id_email in db:
            _, now = repository().segna_pec(utente_corrente_id(), [id_email])
            db[id_email].stato, db[id_email].letta_il = 'LETTA', now
            self._salva()

    def marca_non_letta(self, id_email):
        if id_email in self._carica():
            repository().pec_non_letta(utente_corrente_id(),id_email)
            super().marca_non_letta(id_email)
