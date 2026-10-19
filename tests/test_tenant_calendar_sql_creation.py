"""Uno studio SQLite nasce con calendari SQL prima della pubblicazione."""
from pathlib import Path
import pytest

from pct.agenda import Agenda, TipoAppuntamento
from pct.scadenziario import GestioneScadenziario
from pct.tenant import GestioneTenant


def test_calendari_sql_pronti_prima_che_lo_studio_sia_pubblicato(tmp_path, monkeypatch):
    manager = GestioneTenant(str(tmp_path / 'tenants.json'))
    slug = 'studio-sql-controllato'
    save = manager._salva
    observed = []
    def publish(studios):
        if slug in studios:
            root = manager._data_dir(slug)
            assert Agenda(str(root / 'agenda/appuntamenti.json'))._sql_only
            assert GestioneScadenziario(str(root / 'scadenziario/scadenze.json'))._sql_only
            observed.append(True)
        return save(studios)
    monkeypatch.setattr(manager, '_salva', publish)
    studio = manager.crea('Studio SQL controllato', slug, db_config={'mode': 'SQLITE'})
    assert observed and studio.slug == slug
    paths = manager.percorsi_dati(slug, reconcile_aliases=False, ensure_baseline=False)
    source = Path(paths['AGENDA_DB'])
    historical = source.read_bytes()
    item = Agenda(str(source)).aggiungi('Evento controllato', TipoAppuntamento.RIUNIONE, '2026-12-01T10:00:00')
    assert Agenda(str(source)).get(item.id).titolo == 'Evento controllato'
    assert source.read_bytes() == historical


def test_preparazione_interrotta_non_pubblica_e_riprende_senza_duplicare_audit(tmp_path, monkeypatch):
    from pct import template_atti_preparation
    from pct.storage import StudioDB
    manager = GestioneTenant(str(tmp_path / 'tenants.json'))
    slug = 'studio-sql-ripresa'
    prepare = template_atti_preparation.prepare_catalog
    def interrupted(*args, **kwargs):
        raise RuntimeError('Interruzione controllata prima della pubblicazione')
    monkeypatch.setattr(template_atti_preparation, 'prepare_catalog', interrupted)
    with pytest.raises(RuntimeError, match='Interruzione controllata'):
        manager.crea('Studio controllato ripresa', slug, db_config={'mode': 'SQLITE'})
    assert manager.get(slug) is None
    root = manager._data_dir(slug)
    assert Agenda(str(root / 'agenda/appuntamenti.json'))._sql_only
    monkeypatch.setattr(template_atti_preparation, 'prepare_catalog', prepare)
    manager.crea('Studio controllato ripresa', slug, db_config={'mode': 'SQLITE'})
    db = StudioDB.get(str(root / 'studio.db'))
    for domain in ('agenda', 'scadenziario'):
        assert db.conn.execute('SELECT count(*) FROM audit_log WHERE azione=?',
                               (domain + '.adozione_sql',)).fetchone()[0] == 1
