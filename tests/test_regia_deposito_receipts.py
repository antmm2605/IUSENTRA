from pct.practice_engine.deposit_orchestrator import prepare_deposit, send_deposit
from pct.practice_engine.receipt_tracker import import_receipt

from tests.regia_test_utils import link_required_documents, make_simple_fascicolo


def test_deposito_non_parte_con_blocchi(tmp_path):
    gf, repo, fascicolo, profile = make_simple_fascicolo(tmp_path)
    prepared = prepare_deposit(repo, fascicolo=fascicolo, profile=profile, fascicoli_manager=gf)
    result = send_deposit(repo, session_id=prepared["session"].id, fascicolo=fascicolo, profile=profile, fascicoli_manager=gf)
    assert result["sent"] is False
    assert result["session"].status in {"IN_PREPARAZIONE", "ERRORE"}


def test_ricevute_intermedie_non_acquisiscono_e_finale_si(tmp_path):
    gf, repo, fascicolo, profile = make_simple_fascicolo(tmp_path)
    link_required_documents(gf, repo, fascicolo)
    session = repo.create_deposit_session(fascicolo.id, profile.code, profile.channel, status="INVIATO", transport_mode="reale")
    acc = import_receipt(
        repo,
        deposito_id=session.id,
        fascicolo_id=fascicolo.id,
        channel=profile.channel,
        payload={"receipt_type": "ACCETTAZIONE_PEC", "status": "ok", "positive": True},
    )
    assert acc["session"].status == "ACCETTATO_PEC"
    cons = import_receipt(
        repo,
        deposito_id=session.id,
        fascicolo_id=fascicolo.id,
        channel=profile.channel,
        payload={"receipt_type": "CONSEGNA_PEC", "status": "ok", "positive": True},
    )
    assert cons["session"].status == "CONSEGNATO"
    ctrl = import_receipt(
        repo,
        deposito_id=session.id,
        fascicolo_id=fascicolo.id,
        channel=profile.channel,
        payload={"receipt_type": "CONTROLLI_AUTOMATICI", "status": "ok", "positive": True},
    )
    assert ctrl["session"].status == "CONTROLLI_OK"
    final = import_receipt(
        repo,
        deposito_id=session.id,
        fascicolo_id=fascicolo.id,
        channel=profile.channel,
        payload={"receipt_type": "ESITO_CANCELLERIA", "status": "accettato", "positive": True},
    )
    assert final["session"].status == "ACQUISITO"
    assert repo.list_receipts(session.id)[0].original_hash_sha256
    assert repo.list_timeline(session.id)


def test_esito_negativo_porta_da_correggere(tmp_path):
    _gf, repo, fascicolo, profile = make_simple_fascicolo(tmp_path)
    session = repo.create_deposit_session(fascicolo.id, profile.code, profile.channel, status="INVIATO")
    result = import_receipt(
        repo,
        deposito_id=session.id,
        fascicolo_id=fascicolo.id,
        channel=profile.channel,
        payload={"receipt_type": "ESITO_CANCELLERIA", "status": "rifiutato", "positive": False},
    )
    assert result["session"].status == "RIFIUTATO_CANCELLERIA"
    assert repo.latest_state(fascicolo.id) == "DA_CORREGGERE"
