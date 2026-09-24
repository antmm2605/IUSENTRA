"""La sincronizzazione PEC ordinaria legge solo il nuovo e non si ferma sulle PEC storiche."""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from pct.email_client import CartellaEmail, EmailRicevuta, GestioneEmailRicevute, StatoEmail


def _casella_con_pec_illeggibili(tmp_path, quante: int) -> GestioneEmailRicevute:
    ge = GestioneEmailRicevute(str(tmp_path / "casella.json"))
    for uid in range(1, quante + 1):
        ge.aggiungi(
            EmailRicevuta(
                id=f"PEC-{uid}",
                cartella=CartellaEmail.INBOX,
                stato=StatoEmail.LETTA,
                mittente="cancelleria@example.it",
                oggetto=f"PEC {uid}",
                data="2026-05-13T10:17:00+02:00",
                corpo_testo="testo � rotto",
                uid_imap=f"INBOX:UID:{uid}",
                message_id=f"<pec-{uid}@example.test>",
            )
        )
    return ge


def _imap_finto(monkeypatch, quante: int) -> list[str]:
    import pct.email_client as email_runtime

    scaricate: list[str] = []

    class _FakeIMAP:
        def login(self, username, password):
            return "OK", []

        def select(self, mailbox, readonly=True):
            return "OK", [str(quante).encode()]

        def uid(self, command, *args):
            if command == "SEARCH":
                return "OK", [" ".join(str(n) for n in range(1, quante + 1)).encode()]
            if command == "FETCH":
                # Il server non restituisce il messaggio: la riparazione non riesce mai.
                scaricate.append(args[0])
                return "OK", [None]
            return "NO", []

        def logout(self):
            return "OK", []

    monkeypatch.setattr(email_runtime.imaplib, "IMAP4_SSL", lambda *a, **k: _FakeIMAP())
    return scaricate


def _sincronizza(tmp_path) -> dict:
    return GestioneEmailRicevute(str(tmp_path / "casella.json")).sincronizza_imap(
        imap_host="imap.example.it",
        imap_port=993,
        username="studio@example.it",
        password="segreta",
        cartelle_imap=["INBOX"],
        limite=500,
        incremental_only=True,
    )


def test_le_pec_da_riparare_si_riscaricano_poche_per_volta_e_non_a_ogni_aggiornamento(tmp_path, monkeypatch):
    _casella_con_pec_illeggibili(tmp_path, 7)
    scaricate = _imap_finto(monkeypatch, 7)

    primo = _sincronizza(tmp_path)
    assert len(scaricate) == GestioneEmailRicevute.RIPARAZIONI_PER_SINCRONIZZAZIONE == 5
    assert primo["riparazioni_rinviate"] == 2

    scaricate.clear()
    secondo = _sincronizza(tmp_path)
    assert len(scaricate) == 2
    assert secondo["riparazioni_rinviate"] == 5

    # Tutte provate da poco: un nuovo "Aggiorna" non riscarica niente.
    scaricate.clear()
    terzo = _sincronizza(tmp_path)
    assert scaricate == []
    assert terzo["nuove"] == 0


def test_una_riparazione_tentata_da_una_settimana_si_riprova(tmp_path, monkeypatch):
    _casella_con_pec_illeggibili(tmp_path, 1)
    scaricate = _imap_finto(monkeypatch, 1)
    vecchia = (datetime.now() - timedelta(days=8)).isoformat(timespec="seconds")
    (tmp_path / "casella.riparazioni.json").write_text(json.dumps({"INBOX:UID:1": vecchia}), encoding="utf-8")

    _sincronizza(tmp_path)

    assert scaricate == ["1"]
    tentate = json.loads((tmp_path / "casella.riparazioni.json").read_text(encoding="utf-8"))
    assert tentate["INBOX:UID:1"] > vecchia


def test_le_ricevute_di_deposito_si_leggono_con_una_richiesta_sola(monkeypatch):
    import pct.polling_depositi as polling

    richieste: list[tuple[str, str]] = []
    selezioni: list[bool] = []
    risposte = {"deposito": b"1 2", "telematic": b"2", "ACCETTAZIONE": b"3", "CONSEGNA": b""}

    class _FakeIMAP:
        def __init__(self, *args, **kwargs):
            pass

        def login(self, username, password):
            return "OK", []

        def select(self, mailbox, readonly=False):
            selezioni.append(readonly)
            return "OK", [b"3"]

        def search(self, charset, criterio):
            parola = criterio.rsplit('"', 2)[-2]
            return "OK", [risposte[parola]]

        def fetch(self, numeri, domanda):
            richieste.append((numeri, domanda))
            return "OK", [
                (f"{n} (BODY[HEADER.FIELDS (SUBJECT FROM DATE)] {{40}}".encode(), f"Subject: ACCETTAZIONE {n}\r\n\r\n".encode())
                for n in numeri.split(",")
            ] + [b")"]

        def logout(self):
            return "OK", []

    monkeypatch.setattr(polling.imaplib, "IMAP4_SSL", _FakeIMAP)

    ricevute = polling._cerca_ricevute_imap("imap.example.it", 993, "studio@example.it", "segreta")

    assert richieste == [("1,2,3", "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE)])")]
    assert selezioni == [True]
    assert [r["subject"] for r in ricevute] == ["ACCETTAZIONE 1", "ACCETTAZIONE 2", "ACCETTAZIONE 3"]


def test_la_risposta_della_sincronizzazione_dice_quanto_dura_ogni_passo():
    from web.blueprints.email_client import _public_sync_payload

    risposta = _public_sync_payload(
        {"ok": True, "nuove": 2, "tempi": {"casella": 3.2, "esiti": 0.4, "segreto": "x"}},
        fallback_message="errore",
        success_message="fatto",
    )

    assert risposta["tempi"] == {"casella": 3.2, "esiti": 0.4}
    assert risposta["nuove"] == 2


def test_l_archivio_degli_allegati_si_legge_una_volta_finche_non_cambia(tmp_path, monkeypatch):
    import zipfile

    import pct.email_client as email_runtime

    ge = GestioneEmailRicevute(str(tmp_path / "casella.json"))
    archivio = ge.attachments_dir / "archivio-allegati.zip"
    with zipfile.ZipFile(archivio, "w") as zip_file:
        zip_file.writestr("pec/1/postacert.eml", b"x")

    aperture = []
    zip_originale = email_runtime.zipfile.ZipFile

    def _zip_contato(*args, **kwargs):
        aperture.append(args[0])
        return zip_originale(*args, **kwargs)

    monkeypatch.setattr(email_runtime.zipfile, "ZipFile", _zip_contato)
    info = {"archivio_rel": "archivio-allegati.zip", "archivio_membro": "pec/1/postacert.eml"}
    assert all(ge._allegato_salvato(info) for _ in range(50))
    assert not ge._allegato_salvato({**info, "archivio_membro": "pec/2/postacert.eml"})
    assert len(aperture) == 1

    # l'archivio cambia: l'indice si rilegge
    monkeypatch.setattr(email_runtime.zipfile, "ZipFile", zip_originale)
    with zipfile.ZipFile(archivio, "a") as zip_file:
        zip_file.writestr("pec/2/postacert.eml", b"y")
    assert ge._allegato_salvato({**info, "archivio_membro": "pec/2/postacert.eml"})
