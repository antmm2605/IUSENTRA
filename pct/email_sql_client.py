"""Adattatore SQL della casella, senza cambiare MIME, IMAP, allegati o SMTP.

La factory può usarlo soltanto dopo la migrazione esplicita del catalogo.
Non viene letto il mirror JSON come recupero in caso di errore SQL.
"""
from pathlib import Path

from pct.email_client import EmailRicevuta, GestioneEmailRicevute
from pct.email_mailbox_repository import EmailMailboxRepository


class MailboxMirrorError(RuntimeError):
    """La scrittura primaria è riuscita, il mirror richiede rigenerazione."""

    primary_committed = True


class GestioneEmailSQL(GestioneEmailRicevute):
    def __init__(self, db_path, *, studio_db, tenant_key, mailbox_kind,
                 tenant_root, actor_key='system', load_catalog=True):
        root = Path(tenant_root).resolve()
        filename = {'pec': 'casella.json', 'ordinary': 'ordinaria.json'}.get(mailbox_kind)
        if not filename or Path(db_path).resolve() != root / 'email' / filename:
            raise ValueError('La casella non appartiene al contesto dello studio.')
        self.repository = EmailMailboxRepository(
            studio_db, tenant_key, mailbox_kind, mirror_path=db_path,
        )
        # Verifica il catalogo prima di creare cartelle o invocare procedure native.
        records = self.repository.load(message_keys=None if load_catalog else [])
        self.actor_key = str(actor_key or 'system')
        super().__init__(db_path=str(db_path))
        if load_catalog:
            self._replace_cache(records)

    def _replace_cache(self, records):
        self._cache = {key: EmailRicevuta.from_dict(value) for key, value in records.items()}
        self._object_snapshot = {key: message.to_dict() for key, message in self._cache.items()}

    def _carica(self):
        if self._cache is None:
            self._replace_cache(self.repository.load())
        return self._cache

    def get_readonly(self, id_email):
        """Dettaglio consultivo puntuale; l'oggetto non è un edit del catalogo."""
        records = self.repository.load(message_keys=[str(id_email)], update_original=False)
        record = records.get(str(id_email))
        return EmailRicevuta.from_dict(record) if record is not None else None

    def _salva(self):
        # I campi futuri del catalogo rimangono intatti anche se la dataclass
        # corrente non li conosce; il repository governa le sole differenze.
        records = {}
        for key, message in self._carica().items():
            original = (self.repository.original or {}).get(key, {})
            after = message.to_dict()
            if key not in (self.repository.original or {}):
                records[key] = after
                continue
            before = self._object_snapshot[key]
            records[key] = {**original, **{
                field: value for field, value in after.items()
                if field not in before or before[field] != value
            }}
        saved = self.repository.save(records, actor_key=self.actor_key)
        self._replace_cache(saved)
        self._export_mirror()

    def _export_mirror(self):
        try:
            self.repository.export_mirror()
        except OSError as exc:
            raise MailboxMirrorError(
                'Modifica salvata nell’archivio dello studio. La copia di scambio '
                'non è stata aggiornata e richiede rigenerazione.'
            ) from exc

    def marca_lette_multipla(self, ids_email):
        result = self.repository.mark_read(ids_email, actor_key=self.actor_key, require_inbox=True)
        self._invalida()
        try:
            self._export_mirror()
        except MailboxMirrorError as exc:
            exc.operation_result = result
            raise
        return result

    def elimina_definitivamente(self, id_email):
        # La procedura multipla nativa salva il catalogo prima di rimuovere
        # il fascicolo degli allegati. Riutilizzarla anche per un solo ID
        # preserva i file se il controllo di concorrenza SQL rifiuta il commit.
        self.elimina_definitivamente_multipla([id_email])
