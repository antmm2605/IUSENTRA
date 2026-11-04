"""Collaudo permanente della catena notturna su un fascicolo completo (richiesta dell'avvocato del 04/11/2026).

Una PEC di cancelleria con la sentenza in .zip, collegata con certezza al fascicolo (R.G., ufficio e cliente
coincidenti), attraversa la catena notturna vera (``pct/scheduler_notturno``) con il semaforo dei motori vero su
SQLite temporaneo, un passo per giro come di notte:

fase 2 PEC nel fascicolo → fase 3 attesa OCR → fase 4 letture (coda degli eventi del registro) → fase 5 presidio.

Alla fine: sentenza ed .eml nel fascicolo, testo letto, sentenza riconosciuta, fascicolo definito
automaticamente (annullabile), credito registrato perché certo, nessun oggetto «da leggere» residuo.

Base: art. 3 D.M. 44/2011 e art. 20 CAD (integrità delle letture); art. 16, comma 4, D.L. 179/2012
(comunicazioni di cancelleria); art. 132 e art. 91 c.p.c. (sentenza e condanna alle spese).
Dati di prova sintetici: nessun dato reale di clienti.
"""

from __future__ import annotations

import io
import threading
import uuid
import zipfile
from datetime import datetime
from email import policy
from email.message import EmailMessage
from pathlib import Path
from types import SimpleNamespace

import pytest

from pct.fascicoli import StatoFascicolo, TipoDocumento, TipoFascicolo
from tests.test_archivio_letture_runtime import _app, _pdf

ROMA = "Europe/Rome"

RIGHE_SENTENZA = [
    "TRIBUNALE DI TORINO",
    "REPUBBLICA ITALIANA - IN NOME DEL POPOLO ITALIANO",
    "Il Tribunale di Torino, in composizione monocratica, ha pronunciato la seguente",
    "SENTENZA n. 321/2026 pubblicata il 15/10/2026 nella causa iscritta al R.G. n. 777/2026",
    "tra BIANCHI ANNA (attrice), rappresentata e difesa dall'avv. Verdi, e DELTA S.R.L. (convenuta).",
    "Svolgimento del processo. Motivi della decisione.",
    "P.Q.M. Il Tribunale, definitivamente pronunciando, accoglie la domanda e condanna DELTA S.R.L.",
    "alla rifusione delle spese di lite in favore di BIANCHI ANNA, che liquida in euro 2.500,00",
    "per compensi, oltre accessori.",
]


def _zip(nome: str, dati: bytes) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archivio:
        archivio.writestr(nome, dati)
    return buffer.getvalue()


def _pec_sentenza(sentenza: bytes) -> bytes:
    msg = EmailMessage()
    msg["From"] = "Per conto di: tribunale.torino@civile.ptel.giustiziacert.it <posta-certificata@giustiziacert.it>"
    msg["To"] = "studio@pec.example.test"
    msg["Subject"] = "POSTA CERTIFICATA: COMUNICAZIONE RG 777/2026 - DEPOSITO SENTENZA"
    msg["Date"] = "Mon, 02 Nov 2026 10:30:00 +0100"
    msg["Message-ID"] = "<sentenza-777@example.test>"
    msg.set_content("Comunicazione di cancelleria: deposito della sentenza n. 321/2026 nel procedimento R.G. 777/2026.")
    msg.add_attachment(_zip("321s.pdf", sentenza), maintype="application", subtype="zip", filename="321s.pdf.zip")
    msg.add_attachment(b"<postacert tipo=\"posta-certificata\"/>", maintype="application", subtype="xml", filename="daticert.xml")
    return msg.as_bytes(policy=policy.SMTP)


class _LettureInSfondo:
    """Le letture in sfondo partono in un thread che aspetta il semaforo: nel collaudo si raccolgono e girano
    fra un giro e l'altro della catena, quando il passo ha liberato il semaforo (come in produzione)."""

    def __init__(self):
        self.in_attesa: list = []

    def Thread(self, target=None, name=None, daemon=None, **_):  # noqa: N802 - stessa firma di threading.Thread
        lista = self.in_attesa
        return SimpleNamespace(start=lambda: lista.append(target))

    def esegui(self) -> int:
        eseguite = 0
        while self.in_attesa:
            self.in_attesa.pop(0)()
            eseguite += 1
        return eseguite


@pytest.fixture()
def ambiente(tmp_path, monkeypatch):
    monkeypatch.setenv("PCT_SEMAFORO_DB", str(tmp_path / "semaforo_motori.sqlite"))
    monkeypatch.setenv("PCT_SEMAFORO_MOTORI", "1")
    import pct.archivio_letture.presidi as presidi
    from datetime import date

    monkeypatch.setattr(presidi, "oggi_roma", lambda: date(2026, 11, 3))
    app = _app(tmp_path)
    app.config.setdefault("FEATURE_FLAGS", {})
    with app.app_context():
        fascicoli = app.extensions["core_runtime"]["get_fascicoli"]()
        fascicolo = fascicoli.nuovo("Bianchi / Delta S.r.l.", TipoFascicolo.CIVILE, nome_cliente="Anna Bianchi",
                                    tribunale="Tribunale di Torino", numero_rg="777", anno_rg=2026,
                                    controparte="Delta S.r.l.")
    return SimpleNamespace(app=app, fascicolo_id=fascicolo.id, tmp=tmp_path)


def _paths(app) -> dict:
    chiavi = ("EMAIL_CASELLA_DB", "FASCICOLI_DB", "FASCICOLI_DOCS", "SCADENZIARIO_DB", "AGENDA_DB", "PEC_AUDIT_DB")
    return {k: app.config[k] for k in chiavi if app.config.get(k)}


def _ingesta_e_collega(app, fascicolo_id: str, *, sentenza: bytes | None = None) -> str:
    """Fasi 1-2 a monte: la PEC entra nel presidio e il linker la collega con certezza (R.G. + ufficio)."""
    from pct.pec_pipeline import canonical_json, iso_now
    from web.services.pec_pipeline_runtime import repository_from_paths

    repo = repository_from_paths(_paths(app), tenant_label="default")
    esito = repo.ingest_mime(_pec_sentenza(sentenza or _pdf(RIGHE_SENTENZA)), account_email="studio@pec.example.test",
                             folder="INBOX", imap_uid="INBOX:UID:777", actor="pytest")
    repo.run_pending_jobs(limit=40)
    message_id = str(esito["id"])
    with repo.connect() as conn:
        versione = repo.latest_parsed_row(conn, message_id)
        conn.execute(
            "INSERT INTO pec_fascicolo_links (id, message_id, parsed_version_id, fascicolo_id, score, status, seeds_json, candidates_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (uuid.uuid4().hex, message_id, versione["id"], fascicolo_id, 1.0, "ruolo_certificato_ufficio",
             canonical_json({}), canonical_json([]), iso_now()),
        )
        conn.execute("UPDATE pec_messages SET linked_fascicolo_id=?, status='linked' WHERE id=?", (fascicolo_id, message_id))
    return message_id


def _lavori(app):
    """I lavori della catena per le fasi 2-5, con la stessa chiamata e lo stesso contesto dello scheduler."""
    from pct.scheduler_notturno.guardia import custodisci

    def pec_nel_fascicolo():
        with app.app_context():
            from web.services.pec_fascicolo_documenti_runtime import limite_recupero, recupero_per_studi

            return recupero_per_studi([("default", _paths(app))], limite=limite_recupero(app.config))

    def letture():
        with app.app_context():
            from web.services.archivio_letture_runtime import lettura_automatica_per_tutti

            return lettura_automatica_per_tutti(app, limite_oggetti=150, usa_marker_scheduler=True)

    def presidio_economico():
        with app.app_context():
            from web.services.fascicoli_presidi_runtime import run_fascicoli_document_economic_presidio_for_all_tenants

            return run_fascicoli_document_economic_presidio_for_all_tenants(app, limit_per_tenant=25, actor="IUSENTRA scheduler")

    funzioni = {
        "pec_fascicolo_documenti_recupero": pec_nel_fascicolo,
        "archivio_letture_automatico": letture,
        "fascicoli_document_economic_presidio": presidio_economico,
    }
    return {nome: SimpleNamespace(func=custodisci(nome, f), args=(), kwargs={}, next_run_time=datetime.now())
            for nome, f in funzioni.items()}


def _esegui_notte(registro_notte, lavori, sfondo, *, ocr_in_coda=lambda: 0, giri_massimi: int = 400):
    """Un passo per giro, come il lavoro ``sequenza_notturna``; l'orologio avanza di 2 minuti a ogni lettura."""
    from datetime import timedelta
    from zoneinfo import ZoneInfo

    from pct.scheduler_notturno import catena

    ambiente = catena.Ambiente(trova_lavoro=lavori.get, memoria_libera_mb=lambda: 8000,
                               ocr_in_coda=ocr_in_coda, scarica_ai_locale=lambda: [])
    orologio = {"ora": datetime(2026, 11, 3, 21, 31, tzinfo=ZoneInfo(ROMA))}

    def adesso():
        orologio["ora"] += timedelta(minutes=2)
        sfondo.esegui()  # le letture in sfondo avanzano mentre la catena aspetta il giro successivo
        return orologio["ora"]

    esiti = []
    for _ in range(giri_massimi):
        esito = catena.esegui_passo(registro_notte, ambiente, adesso=adesso)
        sfondo.esegui()
        if esito.get("skipped") and "conclusa" in str(esito.get("message")):
            break
        esiti.append(esito)
    return esiti


def test_pec_con_sentenza_in_zip_completa_il_fascicolo_in_una_notte(ambiente, monkeypatch):
    import web.services.archivio_letture_runtime as archivio
    from pct.scheduler_notturno.registro import RegistroNotte

    app, fascicolo_id = ambiente.app, ambiente.fascicolo_id
    from pct.scheduler_notturno import catena

    sfondo = _LettureInSfondo()
    monkeypatch.setattr(archivio, "threading", SimpleNamespace(Thread=sfondo.Thread, Lock=threading.Lock, get_ident=threading.get_ident))
    monkeypatch.setattr(catena, "dormi", lambda _s: None)
    message_id = _ingesta_e_collega(app, fascicolo_id)
    registro_notte = RegistroNotte(ambiente.tmp / "scheduler_registry.sqlite")
    esiti = _esegui_notte(registro_notte, _lavori(app), sfondo)
    eseguiti = {e["lavoro"]: e["esito"] for e in esiti if e.get("lavoro")}
    assert eseguiti["pec_fascicolo_documenti_recupero"] == "completato", esiti
    assert eseguiti["archivio_letture_automatico"] == "completato", esiti
    assert eseguiti["fascicoli_document_economic_presidio"] == "completato", esiti

    with app.app_context():
        from web.services.registro_letture_runtime import registro_corrente, tenant_corrente

        fascicolo = app.extensions["core_runtime"]["get_fascicoli"]().get(fascicolo_id)
        nomi = {d.nome_originale or d.nome: d for d in fascicolo.documenti}
        # 1. documento ed .eml nel fascicolo, con la provenienza della PEC.
        assert "321s.pdf" in nomi, sorted(nomi)
        assert any(d.tipo == TipoDocumento.COMUNICAZIONE and str(d.nome).endswith(".eml") for d in fascicolo.documenti)
        assert f"iusentra:pec:{message_id}" in nomi["321s.pdf"].tags
        # 2. testo letto e nessun oggetto «da leggere» per i motori.
        registro, tenant = registro_corrente(), tenant_corrente()
        assert registro.da_leggere(tenant, fascicolo_id, "motore_documenti", tipi=("documento",)) == []
        assert registro.da_leggere(tenant, fascicolo_id, "motore_pec", tipi=("pec", "allegato_pec")) == []
        # 3. sentenza riconosciuta e definizione automatica (annullabile).
        assert fascicolo.stato == StatoFascicolo.DEFINITO, fascicolo.stato
        from web.services.sentenza_proposte_runtime import proposte_sentenza_payload

        proposte = proposte_sentenza_payload(fascicolo)
        (voce,) = proposte["automatiche"]
        assert voce["numero"] == "321" and voce["definito"] and voce["dataDefinizione"] == "2026-10-15"
        # 4. credito certo: condannata la controparte, beneficiario il cliente, importo unico (art. 91 c.p.c.).
        from web.services.sentenza_economic_runtime import _repo

        crediti = [e for e in _repo().list_economic_events(tenant, fascicolo_id=fascicolo_id) if e["event_type"].startswith("apri_credito")]
        assert len(crediti) == 1 and crediti[0]["status"] == "confirmed", crediti
        assert crediti[0]["event_type"] == "apri_credito_cliente" and float(crediti[0]["amount"]) == 2500.0
        # 5. la sentenza non crea udienze o termini futuri da confermare: nessuna scadenza inventata.
        assert not [f for f in registro.fatti(tenant, fascicolo_id) if f.campo in {"udienza", "termine"}]

    # Il presidio economico (fase 5) chiede una verifica del contributo unificato: l'evento lo legge il primo giro
    # della coda (alle 07:33 di giorno, o la fase 4 della notte dopo). Dopo quel giro la coda è vuota.
    with app.app_context():
        from web.services.archivio_letture_runtime import lettura_automatica_per_tutti

        lettura_automatica_per_tutti(app, limite_oggetti=150, usa_marker_scheduler=True)
    sfondo.esegui()
    with app.app_context():
        assert registro_corrente().eventi_da_riprendere(tenant_corrente()) == []

    # L'avvocato può annullare la definizione automatica: il fascicolo torna in corso.
    with app.test_request_context("/"):
        from web.services.sentenza_proposte_runtime import decidi_definizione, proposte_sentenza_payload

        fascicolo = app.extensions["core_runtime"]["get_fascicoli"]().get(fascicolo_id)
        (voce,) = proposte_sentenza_payload(fascicolo)["automatiche"]
        decidi_definizione(fascicolo, voce["id"], esito="annulla", utente="avv1")
    with app.app_context():
        from pct.fascicoli import GestioneFascicoli

        riletto = GestioneFascicoli(db_path=app.config["FASCICOLI_DB"], documents_dir=app.config["FASCICOLI_DOCS"]).get(fascicolo_id)
        assert riletto.stato == StatoFascicolo.IN_CORSO, [(a.stato_precedente, a.stato_nuovo) for a in riletto.avanzamento]

    # Il registro della notte riporta ogni passo, in ordine.
    passi = [e["lavoro"] for e in esiti if e.get("lavoro")]
    assert passi.index("pec_fascicolo_documenti_recupero") < passi.index("archivio_letture_automatico") < passi.index(
        "fascicoli_document_economic_presidio")


# --- correzioni emerse dal collaudo ---------------------------------------------------------------------------

def test_passo_ripetuto_si_ferma_quando_i_totali_sono_a_zero():
    """«limite» e «studi» non sono lavoro: il recupero PEC a vuoto non si ripete per 40 minuti."""
    from pct.scheduler_notturno.catena import _niente_da_fare

    assert _niente_da_fare({"ok": True, "limite": 100, "studi": 1, "totals": {"esaminati": 0, "restano": 0, "errori": 0}})
    assert not _niente_da_fare({"ok": True, "limite": 100, "studi": 1, "totals": {"esaminati": 3, "restano": 0}})
    # Letture: eventi pronti o letture in sfondo ancora vive tengono aperto il passo.
    assert not _niente_da_fare({"ok": True, "mode": "event_queue", "totals": {"esaminati": 0, "restano": 2}})
    assert _niente_da_fare({"ok": True, "mode": "event_queue", "totals": {"esaminati": 0, "restano": 0}})
    assert not _niente_da_fare({"ok": True, "lette": 2, "errori": 0})  # catalogo Lex: si ripete finché legge
    assert _niente_da_fare(None)


def test_passo_ripetuto_respira_fra_un_giro_e_l_altro(monkeypatch):
    from pct.scheduler_notturno import catena
    from pct.scheduler_notturno.sequenza import Passo

    pause: list[float] = []
    giri = iter([{"totals": {"esaminati": 1}}, {"totals": {"esaminati": 1}}, {"totals": {"esaminati": 0}}])
    monkeypatch.setattr(catena, "dormi", pause.append)
    job = SimpleNamespace(func=lambda: next(giri), args=(), kwargs={})
    adesso = lambda: datetime(2026, 11, 3, 22, 0)  # noqa: E731
    esito = catena._esegui_lavoro(job, Passo("x", ripeti_minuti=40), datetime(2026, 11, 4, 7, 30), adesso)
    assert esito == ("completato", "Eseguito 3 volte.") and pause == [catena.PAUSA_TRA_GIRI_SECONDI] * 2


@pytest.mark.parametrize("intestazione", [
    "TRIBUNALE DI TORINO REPUBBLICA ITALIANA-IN NOME DEL POPOLO ITALIANO Il Tribunale di Torino, in composizione monocratica,",
    "TRIBUNALE DI TORINO IN NOME DEL POPOLO ITALIANO Il Giudice",
    "REPUBBLICA ITALIANA IN NOME DEL POPOLO ITALIANO TRIBUNALE ORDINARIO DI TORINO Sezione Prima civile",
])
def test_intestazione_su_una_riga_non_cambia_l_ufficio(intestazione):
    """Righe unite dall'estrazione del testo: la formula d'intestazione (art. 132 c.p.c.) chiude l'ufficio."""
    from pct.pec_case_identity import document_case_identity_evidence

    fascicolo = SimpleNamespace(nome_cliente="Anna Bianchi", numero_rg="777", anno_rg="2026", tribunale="Tribunale di Torino",
                                id_cliente="")
    esito = document_case_identity_evidence(intestazione + " SENTENZA nella causa R.G. n. 777/2026 tra BIANCHI ANNA (attrice)",
                                            fascicolo)
    assert esito["office_match"] and esito["complete_match"], esito


def test_lettura_in_sfondo_nello_studio_unico_non_si_ferma_sulle_discordanze():
    """Studio unico: le discordanze restano non disponibili (V48) con un errore riconoscibile, che la lettura in
    sfondo salta invece di chiudere in errore il fascicolo (l'avanzamento resta dimostrato dal test sopra)."""
    import inspect

    import web.services.archivio_letture_runtime as archivio
    from web.services.discordanze_letture_runtime import StudioNonIdentificato

    assert issubclass(StudioNonIdentificato, RuntimeError)
    assert "except StudioNonIdentificato" in inspect.getsource(archivio.avvia_lettura_in_background)


def test_recupero_pec_con_piu_studi_gira_nel_contesto_dello_studio(tmp_path, monkeypatch):
    """Gli eventi del registro nati dal salvataggio notturno vanno nel registro dello studio, non in quello globale."""
    from flask import g

    import pct.tenant as tenant_mod
    import web.services.pec_fascicolo_documenti_runtime as runtime
    from web.services.registro_letture_runtime import percorso_registro, tenant_corrente

    app = _app(tmp_path)
    app.config.update(MULTI_TENANT=True, TENANTS_REGISTRY=str(tmp_path / "tenants.json"))
    percorsi = {"FASCICOLI_DB": str(tmp_path / "studi" / "alfa" / "fascicoli" / "fascicoli.json"),
                "CLIENTI_DB": str(tmp_path / "studi" / "alfa" / "clienti" / "clienti.json")}
    studio = SimpleNamespace(slug="alfa", id="alfa")

    class _Gestione:
        def __init__(self, registry_path=""):
            pass

        def get(self, slug):
            return studio if slug == "alfa" else None

        def percorsi_dati(self, slug, **_):
            return dict(percorsi)

    visti: list[tuple[str, str, str]] = []

    def recupera(repo, *, limite):
        visti.append((str(g.get("tenant_context_slug") or ""), percorso_registro(), tenant_corrente()))
        return {"ok": True, "esaminati": 0, "restano": 0}

    monkeypatch.setattr(tenant_mod, "GestioneTenant", _Gestione)
    monkeypatch.setattr(runtime, "recupera_storico", recupera)
    monkeypatch.setattr(runtime, "repository_from_paths", lambda paths, tenant_label="": SimpleNamespace())
    monkeypatch.setattr(runtime, "_notifiche_l53", lambda repo: {})
    with app.app_context():
        esito = runtime.recupero_per_studi([("alfa", percorsi)], limite=10)
    assert esito["ok"], esito
    [(slug, registro, tenant)] = visti
    assert slug == "alfa" and tenant == "alfa"
    assert Path(registro) == Path(percorsi["FASCICOLI_DB"]).resolve().parent.parent / "intelligence" / "registro_letture.db"


def test_riletture_e_verifiche_periodiche_valgono_anche_nella_sera_della_catena():
    """La fase 4 della catena parte verso le 22: riletture, verifiche e riprese devono poter partire anche lì."""
    from datetime import time

    from pct.scheduler_notturno import finestra
    from web.services.archivio_letture_runtime import ORE_RILETTURA

    assert finestra.inizio() <= time(21, 59)
    assert {21, 22, 23, 0, 3, 5} <= set(ORE_RILETTURA)
    assert not {8, 11, 14, 18} & set(ORE_RILETTURA)


# --- sentenza scansionata: OCR nella stessa notte -------------------------------------------------------------

def _pdf_senza_testo() -> bytes:
    """Una scansione: solo grafica, nessun testo estraibile."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    pagina = canvas.Canvas(buffer, pagesize=A4)
    pagina.rect(60, 400, 400, 300, fill=1)
    pagina.save()
    return buffer.getvalue()


class _OcrSimulato:
    """Coda OCR finta con lo stesso contratto del worker: testo in cache dell'indice e consegna all'archivio."""

    def __init__(self, app, testo: str):
        self.app, self.testo, self.coda, self.letti = app, testo, [], 0

    def enqueue(self, **kwargs):
        from web.services.registro_letture_runtime import percorso_registro, tenant_corrente

        self.coda.append(SimpleNamespace(registro_path=percorso_registro(), tenant_id=tenant_corrente(), **kwargs))
        return True

    def lavora(self) -> None:
        from web.helpers import get_indice
        from web.services.archivio_letture_runtime import registra_lettura_ocr_nell_archivio

        while self.coda:
            job = self.coda.pop(0)
            with self.app.test_request_context("/__ocr-worker"):
                get_indice().set_ocr_cache(job.hash_sha256, self.testo)
                registra_lettura_ocr_nell_archivio(SimpleNamespace(id=job.id_doc, **vars(job)), self.testo)
            self.letti += 1


def test_sentenza_scansionata_arrivata_stanotte_e_letta_nella_stessa_notte(ambiente, monkeypatch):
    import web.services.archivio_letture_runtime as archivio
    from pct.scheduler_notturno import catena
    from pct.scheduler_notturno.registro import RegistroNotte

    app, fascicolo_id = ambiente.app, ambiente.fascicolo_id
    ocr = _OcrSimulato(app, "\n".join(RIGHE_SENTENZA))
    app.extensions["ocr_runtime"] = ocr
    sfondo = _LettureInSfondo()
    monkeypatch.setattr(archivio, "threading", SimpleNamespace(Thread=sfondo.Thread, Lock=threading.Lock, get_ident=threading.get_ident))
    monkeypatch.setattr(catena, "dormi", lambda _s: None)
    _ingesta_e_collega(app, fascicolo_id, sentenza=_pdf_senza_testo())

    def ocr_in_coda() -> int:
        in_coda = len(ocr.coda)
        ocr.lavora()  # il worker OCR lavora mentre la catena aspetta
        return in_coda

    esiti = _esegui_notte(RegistroNotte(ambiente.tmp / "scheduler_registry.sqlite"), _lavori(app), sfondo, ocr_in_coda=ocr_in_coda)
    passi = [e.get("lavoro") for e in esiti if e.get("lavoro")]
    assert passi.index("archivio_letture_automatico") < passi.index("__attesa_ocr_letture") < passi.index("archivio_letture_dopo_ocr")
    assert ocr.letti == 1, "la scansione va all'OCR dopo la prima lettura e prima della seconda"
    with app.app_context():
        fascicolo = app.extensions["core_runtime"]["get_fascicoli"]().get(fascicolo_id)
        assert fascicolo.stato == StatoFascicolo.DEFINITO, fascicolo.stato


def test_errore_del_controllo_economico_non_ferma_la_lettura(tmp_path, monkeypatch):
    """L'errore va nell'esito e nel registro (lettore «presidio_economico»), la lettura si chiude lo stesso."""
    import web.services.sentenza_economic_runtime as economia
    from tests.test_archivio_letture_runtime import _seed

    app = _app(tmp_path)
    fascicolo_id, _d, _r = _seed(app)

    def guasto(_fid):
        raise OSError("archivio economico non leggibile")

    monkeypatch.setattr(economia, "ensure_fascicolo_sentenza_economic_analysis", guasto)
    with app.test_request_context("/"):
        from web.services.archivio_letture_runtime import leggi_fascicolo
        from web.services.registro_letture_runtime import registro_corrente, tenant_corrente

        fascicolo = app.extensions["core_runtime"]["get_fascicoli"]().get(fascicolo_id)
        esito = leggi_fascicolo(fascicolo)
        assert esito["documenti"]["letti"] >= 2 and esito["fermo"]
        assert esito["economia"]["ok"] is False and "OSError" in esito["economia"]["errore"]
        righe = registro_corrente().righe_fascicoli(tenant_corrente(), lettore="presidio_economico")
        assert any(r.get("stato") == "errore" and r.get("fascicolo_id") == fascicolo_id for r in righe), righe
