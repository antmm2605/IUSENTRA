"""La catena di alimentazione dentro l'app: documento → motore → archivio → presìdi; PEC → motore → archivio.

Il primo giro legge, il secondo non rilegge nulla; il presidio documentale e
il presidio notifiche attingono all'archivio senza rileggere i documenti; il
pannello «Letture e verifiche» espone l'archivio e la decisione sui fatti.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from pct.fascicoli import TipoDocumento, TipoFascicolo
from tests.test_react_shell import _app

HEADERS = {"X-API-Key": "react-test-key"}


def _pdf(righe: list[str]) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    pagina = canvas.Canvas(buffer, pagesize=A4)
    y = 780
    for riga in righe:
        pagina.drawString(60, y, riga)
        y -= 22
    pagina.save()
    return buffer.getvalue()


DECRETO = _pdf([
    "TRIBUNALE DI TORINO - Sezione Prima Civile - R.G. n. 777/2026",
    "Il Giudice fissa l'udienza di comparizione delle parti per il giorno 10/11/2026 alle ore 9.30",
    "e assegna termine perentorio fino al 31/10/2026 per il deposito delle memorie ex art. 171-ter c.p.c.",
    "Il sig. Rossi, nato a Roma il 12/03/1980, carta d'identita' rilasciata il 03/02/2020.",
    "Storico depositi: 01/01/2020 02/02/2021 03/03/2022",
])
RELATA = _pdf([
    "RELATA DI NOTIFICA ai sensi dell'art. 3-bis della legge 21 gennaio 1994 n. 53",
    "Io sottoscritto avv. Mario Rossi notifico il presente atto a mezzo PEC.",
    "Ricevuta di accettazione del 05/09/2026 ore 10:15 e ricevuta di avvenuta consegna del 05/09/2026 ore 10:16.",
])


def _seed(app) -> tuple[str, str, str]:
    with app.app_context():
        fascicoli = app.extensions["core_runtime"]["get_fascicoli"]()
        fascicolo = fascicoli.nuovo("Bianchi / Delta S.r.l.", TipoFascicolo.CIVILE, nome_cliente="Anna Bianchi", tribunale="Tribunale di Torino", numero_rg="777", anno_rg=2026)
        decreto = fascicoli.aggiungi_documento(fascicolo.id, nome_file="decreto.pdf", tipo=TipoDocumento.ALTRO, contenuto=DECRETO)
        relata = fascicoli.aggiungi_documento(fascicolo.id, nome_file="atto.pdf", tipo=TipoDocumento.ALTRO, contenuto=RELATA)
        return fascicolo.id, decreto.id, relata.id


def _fascicolo(app, fascicolo_id: str):
    return app.extensions["core_runtime"]["get_fascicoli"]().get(fascicolo_id)


def test_il_motore_documenti_alimenta_l_archivio_una_volta_sola_e_i_presidi_attingono(tmp_path: Path):
    app = _app(tmp_path)
    fascicolo_id, decreto_id, relata_id = _seed(app)
    with app.app_context():
        from web.services.archivio_letture_runtime import fatti_fascicolo, leggi_fascicolo, stato_archivio_payload
        from web.services.registro_letture_runtime import registro_corrente, tenant_corrente

        fascicolo = _fascicolo(app, fascicolo_id)
        primo = leggi_fascicolo(fascicolo)
        assert primo["documenti"]["da_leggere"] == 2 and primo["documenti"]["letti"] == 2 and primo["documenti"]["senza_testo"] == 0
        fatti = fatti_fascicolo(fascicolo)
        per = {(f.oggetto_id, f.campo, f.valore.split("T")[0]): f for f in fatti}
        assert per[(decreto_id, "udienza", "2026-11-10")].verifica == "verificata" and per[(decreto_id, "udienza", "2026-11-10")].origine == "nativo"
        assert per[(decreto_id, "termine", "2026-10-31")].verifica == "verificata"
        assert per[(decreto_id, "numero_ruolo", "777/2026")].verifica == "verificata"
        assert per[(relata_id, "relata", "relata")].verifica == "verificata"
        assert per[(relata_id, "accettazione", "2026-09-05")].valore == "2026-09-05T10:15"
        valori = {f.valore.split("T")[0] for f in fatti if f.categoria == "data"}
        assert not valori & {"1980-03-12", "2020-02-03", "2020-01-01", "2021-02-02", "2022-03-03", "1994-01-21"}
        # Secondo giro: nulla da leggere, nulla riletto.
        secondo = leggi_fascicolo(fascicolo)
        assert secondo["documenti"]["da_leggere"] == 0 and secondo["documenti"]["letti"] == 0
        assert secondo["documenti"]["senza_testo"] == 0 and secondo["documenti"]["assenti"] == 0
        assert secondo["pec"]["assenti"] == 0 and secondo["pec"]["fatti"] == 0
        stato = registro_corrente().stato_fascicolo(tenant_corrente(), fascicolo_id, lettori=("motore_documenti",))
        assert stato.lettori[0].letti == 2 and stato.lettori[0].completa
        # Il presidio documentale legge dall'archivio, senza testi indicizzati.
        from web.services.react_fascicoli_bridge import _document_presidio_for_fascicolo, _notification_relata, _prove_notifica_archivio

        presidio = _document_presidio_for_fascicolo(fascicolo)
        azioni = {(a["type"], a["dateIso"]): a for a in presidio["actions"]}
        assert azioni[("udienza_documento", "2026-11-10")]["fromArchivio"] and azioni[("udienza_documento", "2026-11-10")]["time"] == "09:30"
        assert azioni[("termine_documento", "2026-10-31")]["verifica"] == "verificata"
        assert presidio["dateAnomalie"] == []
        # Il presidio notifiche riconosce la relata dal contenuto: il nome del file non lo diceva.
        assert _prove_notifica_archivio(fascicolo) == {relata_id: "relata"}
        relata = _notification_relata(fascicolo, [])
        assert any(voce.get("kind") == "relata" for voce in relata.get("documents") or []), relata.get("documents")
        archivio = stato_archivio_payload(fascicolo)
        assert archivio["udienze"] == 1 and archivio["termini"] == 1 and archivio["prove_notifica"] >= 1 and archivio["lettura_automatica"]["completa"]


def test_il_motore_pec_alimenta_l_archivio_dal_presidio_pec(tmp_path: Path):
    app = _app(tmp_path)
    fascicolo_id, _decreto_id, _relata_id = _seed(app)
    with app.app_context():
        from web.services.archivio_letture_runtime import fatti_fascicolo, leggi_fascicolo
        from web.services.pec_pipeline_runtime import repository_for_current_request

        repository = repository_for_current_request()
        repository.ensure_schema()
        metadata = {"headers": {"subject": "Comunicazione di cancelleria: fissazione udienza", "from": "tribunale.torino@civile.ptel.giustiziacert.it", "to": "studio@pec.it"}}
        with repository.connect() as conn:
            conn.execute(
                "INSERT INTO pec_messages (id, tenant_id, account_email, folder, mime_sha256, mime_size, original_mime, received_at, ingested_at, status, quality_status, signature_status, linked_fascicolo_id, metadata_json) "
                "VALUES ('M1', 'default', 'studio@pec.it', 'INBOX', 'sha-m1', 10, X'00', '2026-09-02T09:00:00', '2026-09-02T09:00:00', 'linked', 'verde', 'valida', ?, ?)",
                (fascicolo_id, json.dumps(metadata)),
            )
            conn.execute("INSERT INTO pec_parsed_versions (id, message_id, version, parser_version, parsed_json, parsed_sha256, created_at) VALUES ('v1','M1',1,'1','{}','p1','2026-09-02T09:05:00')")
            conn.execute("INSERT INTO pec_legal_events (id, tenant_id, message_id, parsed_version_id, rulepack_version, family, primary_event, priority, confidence, human_review_required, event_json, event_sha256, created_at) VALUES ('E1','default','M1','v1','1','cancelleria','fissazione_udienza','alta',0.9,0,'{}','h1','2026-09-02T09:05:00')")
            conn.execute("INSERT INTO pec_legal_hearings (id, tenant_id, legal_event_id, hearing_date, hearing_time, mode, human_review_required, evidence_json, created_at) VALUES ('H1','default','E1','2026-11-10','09:30','presenza',0,'[]','2026-09-02T09:05:00')")
            conn.commit()
        fascicolo = _fascicolo(app, fascicolo_id)
        esito = leggi_fascicolo(fascicolo)
        assert esito["pec"]["letti"] == 1
        pec = [f for f in fatti_fascicolo(fascicolo, motore="pec")]
        per = {(f.categoria, f.campo): f for f in pec}
        assert per[("data", "udienza")].valore == "2026-11-10T09:30" and per[("data", "udienza")].verifica == "verificata"
        assert per[("evento", "fissazione_udienza")].verifica == "verificata"
        # La stessa udienza letta dal decreto (nativo) e dalla PEC: concordanza fra i due motori.
        documenti = {f.valore.split("T")[0]: f for f in fatti_fascicolo(fascicolo, motore="documenti", campo="udienza")}
        assert any(p["codice"] == "concordanza" and "presidio PEC" in p["dettaglio"] for p in documenti["2026-11-10"].prove)
        canoniche = [f for f in fatti_fascicolo(fascicolo, campo="udienza") if f.valore.startswith("2026-11-10")]
        assert len(canoniche) == 1
        assert canoniche[0].motore == "documenti+pec"
        assert any(p.get("codice") == "fonti_unite" for p in canoniche[0].prove)
        assert leggi_fascicolo(fascicolo)["pec"]["letti"] == 0


def test_endpoint_letture_espone_l_archivio_e_decide_un_fatto(tmp_path: Path):
    app = _app(tmp_path)
    fascicolo_id, decreto_id, _relata_id = _seed(app)
    with app.app_context():
        from web.services.archivio_letture_runtime import leggi_fascicolo
        from web.services.registro_letture_runtime import registro_corrente, tenant_corrente

        fascicolo = _fascicolo(app, fascicolo_id)
        leggi_fascicolo(fascicolo)
        registro = registro_corrente()
        tenant = tenant_corrente()
        # Un fatto reso plausibile a mano: il pannello lo chiede in conferma.
        termine = next(f for f in registro.fatti(tenant, fascicolo_id) if f.campo == "termine")
        with registro.connection() as conn:
            conn.execute('UPDATE "letture_fatti" SET "verifica" = ? WHERE "id" = ?', ("plausibile", termine.id))
    with app.test_client() as client:
        letture = client.get(f"/api/v1/ui/fascicoli/{fascicolo_id}/letture", headers=HEADERS).get_json()["letture"]
        archivio = letture["archivio"]
        assert archivio["totale"] >= 5 and archivio["udienze"] == 1 and archivio["per_motore"]["documenti"] >= 5
        assert [voce["campo"] for voce in archivio["da_confermare"]] == ["termine"]
        assert archivio["lettura_automatica"]["completa"] is True and archivio["collaudo_lettore"] == {"eseguito": False}
        per_lettore = {voce["lettore"]: voce for voce in letture["lettori"]}
        assert per_lettore["motore_documenti"]["letti"] == 2 and per_lettore["motore_documenti"]["da_leggere"] == 0
        fatto_id = archivio["da_confermare"][0]["id"]
        risposta = client.post(f"/api/v1/ui/fascicoli/{fascicolo_id}/letture/fatti/{fatto_id}", headers=HEADERS, json={"esito": "corretta", "valore": "02/11/2026"}).get_json()
        assert risposta["ok"] and risposta["fatto"]["verifica"] == "corretta" and risposta["fatto"]["valore"] == "2026-11-02"
        assert client.post(f"/api/v1/ui/fascicoli/{fascicolo_id}/letture/fatti/{fatto_id}", headers=HEADERS, json={"esito": "corretta", "valore": "non una data"}).get_json()["ok"] is False
        dopo = client.get(f"/api/v1/ui/fascicoli/{fascicolo_id}/letture", headers=HEADERS).get_json()["letture"]["archivio"]
        assert dopo["da_confermare"] == [] and dopo["per_verifica"]["corretta"] == 1
        lettura = client.get(f"/api/v1/ui/fascicoli/{fascicolo_id}/lettura?aggiorna=1", headers=HEADERS).get_json()["lettura"]
        assert lettura["archivio"]["disponibile"] and lettura["archivio"]["udienze"][0]["data"] == "10/11/2026" and lettura["archivio"]["udienze"][0]["ora"] == "09:30"
        assert lettura["archivio"]["termini"][0]["data"] == "02/11/2026" and lettura["archivio"]["termini"][0]["verifica"] == "corretta"


def test_il_caricamento_di_un_documento_fa_leggere_solo_quello(tmp_path: Path):
    app = _app(tmp_path)
    fascicolo_id, _decreto_id, _relata_id = _seed(app)
    with app.app_context():
        from web.services.archivio_letture_runtime import leggi_fascicolo

        fascicolo = _fascicolo(app, fascicolo_id)
        leggi_fascicolo(fascicolo)
        fascicoli = app.extensions["core_runtime"]["get_fascicoli"]()
        nuovo = fascicoli.aggiungi_documento(fascicolo_id, nome_file="ordinanza.pdf", tipo=TipoDocumento.ALTRO, contenuto=_pdf(["TRIBUNALE DI TORINO - Ordinanza nel procedimento R.G. 777/2026", "Il Giudice, sentite le parti, dispone: udienza rinviata al 20/01/2027 ore 10.00 per la discussione."]))
        esito = leggi_fascicolo(_fascicolo(app, fascicolo_id))
        assert esito["documenti"]["da_leggere"] == 1 and esito["documenti"]["letti"] == 1
        from web.services.archivio_letture_runtime import fatti_fascicolo

        assert {(f.oggetto_id, f.valore) for f in fatti_fascicolo(_fascicolo(app, fascicolo_id), campo="udienza")} >= {(nuovo.id, "2027-01-20T10:00")}


# ── Il ciclo chiuso: legge tutto, si ferma, riparte solo sugli eventi ────────

def test_il_ciclo_si_ferma_a_lettura_confermata_e_non_riapre_nulla(tmp_path: Path):
    """Secondo giro a fascicolo invariato: nessun inventario, nessun file aperto."""
    app = _app(tmp_path)
    fascicolo_id, _decreto_id, _relata_id = _seed(app)
    with app.app_context():
        from web.services import archivio_letture_runtime as runtime

        primo = runtime.leggi_fascicolo(_fascicolo(app, fascicolo_id))
        assert primo["documenti"]["letti"] >= 1
        assert primo["restano"] == 0
        assert primo["ciclo"]["stato"] == "fermo"

        # Il ciclo è fermo: il secondo giro non deve nemmeno toccare l'inventario.
        chiamate: list[str] = []
        originale = runtime.aggiorna_inventario
        runtime.aggiorna_inventario = lambda *a, **k: chiamate.append("inventario") or originale(*a, **k)
        try:
            secondo = runtime.leggi_fascicolo(_fascicolo(app, fascicolo_id))
        finally:
            runtime.aggiorna_inventario = originale
        assert secondo["fermo"] is True
        assert secondo["ciclo"]["stato"] == "fermo"
        assert secondo["documenti"]["letti"] == 0
        assert chiamate == [], "a ciclo fermo non si allinea nemmeno l'inventario"


def test_un_documento_nuovo_riattiva_il_ciclo_e_lo_richiude(tmp_path: Path):
    app = _app(tmp_path)
    fascicolo_id, _decreto_id, _relata_id = _seed(app)
    with app.app_context():
        from web.services.archivio_letture_runtime import leggi_fascicolo

        leggi_fascicolo(_fascicolo(app, fascicolo_id))
        assert leggi_fascicolo(_fascicolo(app, fascicolo_id))["fermo"] is True

        app.extensions["core_runtime"]["get_fascicoli"]().aggiungi_documento(
            fascicolo_id, nome_file="ordinanza.pdf", tipo=TipoDocumento.ALTRO,
            contenuto=_pdf(["TRIBUNALE DI TORINO - R.G. 777/2026", "Il Giudice rinvia l'udienza al 20/01/2027 ore 10.00."]),
        )
        risveglio = leggi_fascicolo(_fascicolo(app, fascicolo_id))
        assert risveglio["documenti"]["letti"] == 1, "il documento nuovo deve risvegliare il ciclo"
        assert risveglio["ciclo"]["stato"] == "fermo", "letto il documento nuovo, il ciclo si richiude"
        assert leggi_fascicolo(_fascicolo(app, fascicolo_id))["fermo"] is True


def test_un_giro_fallito_lascia_il_fascicolo_nel_ciclo_dichiarato_in_errore(tmp_path: Path):
    """Il ciclo non si spezza: un guasto si registra e si riprova, non sparisce."""
    app = _app(tmp_path)
    fascicolo_id, _decreto_id, _relata_id = _seed(app)
    with app.app_context():
        from web.services import archivio_letture_runtime as runtime
        from web.services.registro_letture_runtime import registro_corrente, tenant_corrente

        originale = runtime._leggi_documenti
        runtime._leggi_documenti = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("PDF illeggibile"))
        try:
            with pytest.raises(RuntimeError):
                runtime.leggi_fascicolo(_fascicolo(app, fascicolo_id))
        finally:
            runtime._leggi_documenti = originale

        stato = runtime.stato_ciclo_fascicolo(fascicolo_id, registro_corrente(), tenant_corrente())
        assert stato.stato == "in_errore"
        assert "PDF illeggibile" in stato.motivo
        assert stato.da_leggere is True, "un fascicolo in errore resta nel ciclo e si riprova"

        # Il giro successivo riprende e richiude il ciclo.
        ripreso = runtime.leggi_fascicolo(_fascicolo(app, fascicolo_id))
        assert ripreso["ciclo"]["stato"] == "fermo"
