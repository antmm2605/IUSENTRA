"""Un elenco non deve trasferire l'archivio documentale dello studio.

La riga di un elenco mostra cliente, ruolo, scadenze, pagamenti e il numero
di documenti: i documenti veri non li guarda mai. Leggerli costava la colonna
piu' pesante della tabella a ogni apertura della lista.
"""

from __future__ import annotations

from pathlib import Path

from pct.fascicoli import Documento, GestioneFascicoli, TipoDocumento, TipoFascicolo
from web.services.react_fascicoli_bridge import _fast_documents_count


def _studio(tmp_path: Path):
    from pct.storage import StudioDB

    db = StudioDB.get(str(tmp_path / "studio.db"))
    db.ensure_schema()
    return db


def _repo(tmp_path: Path, **kwargs) -> GestioneFascicoli:
    return GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli" / "fascicoli.json"),
        studio_db=_studio(tmp_path),
        **kwargs,
    )


def _semina(tmp_path: Path, documenti_per_fascicolo: int = 7) -> list[str]:
    repo = _repo(tmp_path)
    ids = []
    for i in range(4):
        f = repo.nuovo(
            titolo=f"Pratica {i}",
            tipo=TipoFascicolo.CIVILE,
            nome_cliente=f"Cliente {i}",
            numero_rg=str(1000 + i),
            anno_rg="2026",
        )
        f.documenti = [
            Documento(id=f"D{i}-{j}", nome=f"atto-{j}.pdf", tipo=TipoDocumento.ALTRO,
                      percorso=f"/docs/{i}/{j}.pdf", note="x" * 300)
            for j in range(documenti_per_fascicolo)
        ]
        ids.append(f.id)
    repo._salva()
    return sorted(ids)


def test_l_elenco_vede_tutti_i_fascicoli(tmp_path: Path):
    ids = _semina(tmp_path)

    elenco = _repo(tmp_path, senza_documenti=True).tutti()

    assert {f.id for f in elenco} == set(ids)


def test_il_numero_di_documenti_resta_esatto(tmp_path: Path):
    """La cosa piu' importante: il conteggio non deve diventare zero."""

    _semina(tmp_path, documenti_per_fascicolo=7)

    for fascicolo in _repo(tmp_path, senza_documenti=True).tutti():
        assert _fast_documents_count(fascicolo) == 7


def test_i_fascicoli_dichiarano_di_non_avere_gli_allegati(tmp_path: Path):
    """Una lista vuota non deve poter passare per 'nessun documento'."""

    _semina(tmp_path)

    for fascicolo in _repo(tmp_path, senza_documenti=True).tutti():
        assert fascicolo.documenti_non_caricati is True
        assert fascicolo.documenti == []
        assert fascicolo.documenti_conteggio == 7


def test_la_lettura_normale_non_dichiara_niente_e_ha_i_documenti(tmp_path: Path):
    _semina(tmp_path)

    for fascicolo in _repo(tmp_path).tutti():
        assert getattr(fascicolo, "documenti_non_caricati", False) is False
        assert len(fascicolo.documenti) == 7
        assert _fast_documents_count(fascicolo) == 7


def test_i_campi_che_servono_all_elenco_ci_sono_tutti(tmp_path: Path):
    """Pagamenti, conflitti e depositi vivono in dati_json: devono arrivare."""

    repo = _repo(tmp_path)
    fascicolo = repo.nuovo(
        titolo="Con pagamenti", tipo=TipoFascicolo.CIVILE,
        nome_cliente="Cliente X", numero_rg="1500", anno_rg="2026",
    )
    fascicolo.pagamenti = {"contributo_unificato": {"importo": 43.0, "stato": "da_versare"}}
    fascicolo.has_conflicts = True
    repo._salva()

    letto = next(f for f in _repo(tmp_path, senza_documenti=True).tutti() if f.id == fascicolo.id)

    assert letto.pagamenti == {"contributo_unificato": {"importo": 43.0, "stato": "da_versare"}}
    assert letto.has_conflicts is True
    assert letto.nome_cliente == "Cliente X"
    assert letto.numero_rg == "1500"


def test_un_fascicolo_senza_documenti_conta_zero(tmp_path: Path):
    repo = _repo(tmp_path)
    vuoto = repo.nuovo(titolo="Senza allegati", tipo=TipoFascicolo.CIVILE, nome_cliente="Y")
    repo._salva()

    letto = next(f for f in _repo(tmp_path, senza_documenti=True).tutti() if f.id == vuoto.id)

    assert _fast_documents_count(letto) == 0


def test_l_idratazione_mirata_riporta_i_documenti_su_un_solo_fascicolo(tmp_path: Path):
    """Chi deve guardare gli allegati davvero li ottiene, uno per volta.

    La vista economica dell'elenco legge i documenti dei fascicoli mostrati a
    schermo. Senza questa idratazione vedrebbe zero allegati e prenderebbe il
    ripiego «fascicolo senza documenti»: nessun errore, risposta sbagliata.
    """

    ids = _semina(tmp_path, documenti_per_fascicolo=5)
    repo = _repo(tmp_path, senza_documenti=True)
    elenco = repo.tutti()
    scelto = next(f for f in elenco if f.id == ids[0])

    assert scelto.documenti_non_caricati is True
    assert scelto.documenti == []

    idratato = repo.idrata_documenti(scelto)

    assert len(idratato.documenti) == 5
    # Il flag sparisce: chi lo controlla non deve piu' diffidare di dati buoni.
    assert getattr(idratato, "documenti_non_caricati", False) is False
    assert idratato.id == scelto.id
    assert idratato.nome_cliente == scelto.nome_cliente


def test_idratare_un_fascicolo_gia_completo_non_fa_danni(tmp_path: Path):
    ids = _semina(tmp_path, documenti_per_fascicolo=5)
    repo = _repo(tmp_path)
    completo = repo.get(ids[0])

    assert repo.idrata_documenti(completo) is completo
    assert len(completo.documenti) == 5
