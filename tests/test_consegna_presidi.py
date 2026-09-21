"""La consegna ai presìdi: l'archivio dà, il presidio scrive, conferma, si ferma.

La catena: i due motori leggono e scrivono i fatti nell'archivio; l'archivio
sa quali presìdi usano quali fatti e glieli consegna una volta sola; il
presidio scrive la riga nel proprio registro e conferma con il riferimento; da
quel momento l'archivio non ripropone più quel fatto. Questi test fissano
l'unica cosa che conta: **niente doppioni e niente fatti persi**.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from pct.archivio_letture.distribuzione import (
    PRESIDI,
    PRESIDI_CHE_SCRIVONO,
    VERIFICHE_CONSEGNABILI,
    categorie_senza_presidio,
    distribuzione_attesa,
    fatti_per_presidio,
)
from pct.archivio_letture.deduplica import fatti_canonici
from pct.fascicoli import TipoDocumento, TipoFascicolo
from pct.archivio_letture.presidi import eventi_letti
from pct.registro_letture import Fatto
from tests.test_react_shell import _app

DECRETO = [
    "TRIBUNALE ORDINARIO DI VICENZA - R.G. 1084/2026",
    "Il Giudice fissa l'udienza di discussione per il giorno 16/12/2026 alle ore 9.30",
    "e assegna termine perentorio fino al 30/11/2026 per il deposito delle note.",
]


def _pdf(righe: list[str]) -> bytes:
    buffer = io.BytesIO()
    pagina = canvas.Canvas(buffer, pagesize=A4)
    y = 780
    for riga in righe:
        pagina.drawString(60, y, riga)
        y -= 22
    pagina.save()
    return buffer.getvalue()


def _fascicolo_con_decreto(app):
    with app.app_context():
        fascicoli = app.extensions["core_runtime"]["get_fascicoli"]()
        fascicolo = fascicoli.nuovo(
            "Marchetti c. MIM", TipoFascicolo.LAVORO, nome_cliente="Marchetti Lucia",
            tribunale="Tribunale di Vicenza", numero_rg="1084", anno_rg=2026,
        )
        fascicoli.aggiungi_documento(fascicolo.id, nome_file="Decreto.PDF", tipo=TipoDocumento.ALTRO, contenuto=_pdf(DECRETO))
        return fascicolo.id


# ── Il registro dei presìdi ─────────────────────────────────────────────────

def test_ogni_presidio_dichiara_che_cosa_usa_e_se_scrive():
    assert PRESIDI, "senza presìdi censiti l'archivio non consegna a nessuno"
    for presidio in PRESIDI:
        assert presidio.nome and presidio.etichetta and presidio.versione
        assert presidio.categorie, f"{presidio.nome} non dichiara alcuna categoria"
        assert presidio.modo in {"scrive", "consulta"}
        assert presidio.descrizione, f"{presidio.nome} non dichiara che cosa ne fa"
    assert {p.nome for p in PRESIDI_CHE_SCRIVONO} == {"scadenziario", "agenda"}
    nomi = {p.nome for p in PRESIDI}
    assert {
        "agenda", "scadenziario", "calendario", "presidio_fascicolo",
        "catalogo_documentale", "lettura_fascicolo", "presidio_economico",
        "contesto_economico", "fatture_proforme", "presidio_notifiche",
    } <= nomi


def test_documento_e_pec_con_stessa_informazione_diventano_un_fatto_canonico():
    documento = Fatto(
        categoria="data", campo="udienza", valore="2026-12-16T09:30",
        verifica="verificata", id="doc-u1", motore="documenti", tipo="documento",
        oggetto_id="D1", origine="nativo", contesto="decreto di fissazione",
        prove=[{"codice": "ancoraggio", "esito": "ok", "dettaglio": "udienza del"}],
    )
    pec = Fatto(
        categoria="data", campo="udienza", valore="2026-12-16T09:30",
        verifica="verificata", id="pec-u1", motore="pec", tipo="pec",
        oggetto_id="M1", origine="presidio_pec", contesto="PEC di cancelleria",
        prove=[{"codice": "concordanza", "esito": "ok", "dettaglio": "presidio PEC"}],
    )

    canonici = fatti_canonici([documento, pec])

    assert len(canonici) == 1
    fuso = canonici[0]
    assert fuso.id.startswith("canon-")
    assert fuso.motore == "documenti+pec"
    assert fuso.valore == "2026-12-16T09:30"
    assert any(prova.get("codice") == "fonti_unite" and "documento:D1" in prova.get("dettaglio", "") and "pec:M1" in prova.get("dettaglio", "") for prova in fuso.prove)
    assert [f.id for f in fatti_per_presidio([documento, pec], "agenda")] == [fuso.id]


def test_la_fusione_canonica_non_attraversa_fascicoli_diversi():
    primo = Fatto(
        categoria="data", campo="udienza", valore="2026-12-16T09:30",
        verifica="verificata", id="doc-u1", motore="documenti", tipo="documento",
        oggetto_id="D1", fascicolo_id="FASC-1",
    )
    secondo = Fatto(
        categoria="data", campo="udienza", valore="2026-12-16T09:30",
        verifica="verificata", id="pec-u2", motore="pec", tipo="pec",
        oggetto_id="M2", fascicolo_id="FASC-2",
    )

    canonici = fatti_canonici([primo, secondo])

    assert len(canonici) == 2
    assert {fatto.fascicolo_id for fatto in canonici} == {"FASC-1", "FASC-2"}
    assert len({fatto.id for fatto in canonici}) == 2


def test_un_fatto_solo_plausibile_non_si_consegna():
    """Una data non riscontrata si chiede all'avvocato, non si scrive nello scadenziario."""
    plausibile = Fatto(categoria="data", campo="termine", valore="2026-11-30", verifica="plausibile", id="f1")
    verificato = Fatto(categoria="data", campo="termine", valore="2026-12-01", verifica="verificata", id="f2")
    corretto = Fatto(categoria="data", campo="termine", valore="2026-12-02", verifica="corretta", id="f3")
    consegnabili = fatti_per_presidio([plausibile, verificato, corretto], "scadenziario")
    assert [f.id for f in consegnabili] == ["f2", "f3"]
    assert "plausibile" not in VERIFICHE_CONSEGNABILI


def test_ogni_presidio_riceve_solo_i_suoi_fatti():
    fatti = [
        Fatto(categoria="data", campo="udienza", valore="2026-12-16", verifica="verificata", id="u1"),
        Fatto(categoria="data", campo="termine", valore="2026-11-30", verifica="verificata", id="t1"),
        Fatto(categoria="importo", campo="contributo_unificato", valore="43.00", verifica="verificata", id="i1"),
        Fatto(categoria="ruolo", campo="numero_ruolo", valore="1084/2026", verifica="verificata", id="r1"),
        Fatto(categoria="prova_notifica", campo="relata", valore="relata", verifica="verificata", id="p1"),
    ]
    attesa = distribuzione_attesa(fatti)
    assert [f.id for f in attesa["agenda"]] == ["u1"]
    assert [f.id for f in attesa["scadenziario"]] == ["t1"]
    assert [f.id for f in attesa["presidio_economico"]] == ["i1"]
    assert [f.id for f in attesa["contesto_economico"]] == ["i1"]
    assert [f.id for f in attesa["fatture_proforme"]] == ["i1"]
    assert [f.id for f in attesa["intestazione_fascicolo"]] == ["r1"]
    assert [f.id for f in attesa["presidio_notifiche"]] == ["p1"]
    assert [f.id for f in attesa["calendario"]] == ["u1", "t1"]
    assert [f.id for f in attesa["lettura_fascicolo"]] == ["u1", "t1", "i1", "r1", "p1"]


def test_nessuna_categoria_prodotta_resta_senza_presidio():
    """Un motore che legge un dato che nessuno usa sta lavorando per niente."""
    from pct.registro_letture.fatti_repository import CATEGORIE

    fatti = [Fatto(categoria=categoria, campo="x", valore="1", verifica="verificata", id=categoria) for categoria in CATEGORIE]
    assert categorie_senza_presidio(fatti) == {}, "ogni categoria prodotta deve avere un presidio che la usa"


# ── La consegna vera ────────────────────────────────────────────────────────

def test_i_fatti_diventano_una_scadenza_e_un_appuntamento(tmp_path: Path):
    app = _app(tmp_path)
    fascicolo_id = _fascicolo_con_decreto(app)
    with app.app_context():
        from web.helpers import get_agenda, get_scadenziario
        from web.services.archivio_letture_runtime import leggi_fascicolo

        fascicoli = app.extensions["core_runtime"]["get_fascicoli"]()
        esito = leggi_fascicolo(fascicoli.get(fascicolo_id))

        assert esito["consegne"]["consegnati"] == 2
        assert esito["consegne"]["rifiutati"] == 0
        scadenze = get_scadenziario().tutte(id_fascicolo=fascicolo_id, solo_aperte=False)
        assert [s.data_scadenza for s in scadenze] == ["2026-11-30"]
        assert "lettura automatica" in scadenze[0].note
        appuntamenti = [a for a in get_agenda().tutti() if "1084/2026" in (a.procedimento or "")]
        assert [a.data_ora for a in appuntamenti] == ["2026-12-16T09:30:00"]


def test_un_fatto_consegnato_non_viene_riconsegnato(tmp_path: Path):
    """La prova che conta: nessun doppione, nemmeno forzando la rilettura."""
    app = _app(tmp_path)
    fascicolo_id = _fascicolo_con_decreto(app)
    with app.app_context():
        from web.helpers import get_agenda, get_scadenziario
        from web.services.archivio_letture_runtime import leggi_fascicolo

        fascicoli = app.extensions["core_runtime"]["get_fascicoli"]()
        leggi_fascicolo(fascicoli.get(fascicolo_id))
        primo = len(get_scadenziario().tutte(id_fascicolo=fascicolo_id, solo_aperte=False)), len(get_agenda().tutti())

        assert leggi_fascicolo(fascicoli.get(fascicolo_id))["fermo"] is True
        forzato = leggi_fascicolo(fascicoli.get(fascicolo_id), forza=True)
        assert forzato["consegne"]["consegnati"] == 0, "l'archivio non riconsegna ciò che ha già dato"

        dopo = len(get_scadenziario().tutte(id_fascicolo=fascicolo_id, solo_aperte=False)), len(get_agenda().tutti())
        assert dopo == primo, "scadenze e appuntamenti non devono moltiplicarsi"


def test_una_scadenza_gia_presente_non_si_duplica(tmp_path: Path):
    """Se l'avvocato l'ha già registrata, il presidio la dichiara non pertinente."""
    app = _app(tmp_path)
    fascicolo_id = _fascicolo_con_decreto(app)
    with app.app_context():
        from pct.scadenziario import TipoTermine
        from web.helpers import get_scadenziario
        from web.services.archivio_letture_runtime import leggi_fascicolo

        get_scadenziario().nuova(titolo="Note difensive", tipo=TipoTermine.TERMINE_PERENTORIO, data_scadenza="2026-11-30", id_fascicolo=fascicolo_id)
        fascicoli = app.extensions["core_runtime"]["get_fascicoli"]()
        esito = leggi_fascicolo(fascicoli.get(fascicolo_id))

        assert esito["consegne"]["presidi"]["scadenziario"]["non_pertinenti"] == 1
        assert esito["consegne"]["presidi"]["scadenziario"]["consegnati"] == 0
        assert len(get_scadenziario().tutte(id_fascicolo=fascicolo_id, solo_aperte=False)) == 1


def test_la_conferma_del_presidio_resta_scritta_con_il_riferimento(tmp_path: Path):
    app = _app(tmp_path)
    fascicolo_id = _fascicolo_con_decreto(app)
    with app.app_context():
        from web.helpers import get_scadenziario
        from web.services.archivio_letture_runtime import leggi_fascicolo
        from web.services.registro_letture_runtime import registro_corrente, tenant_corrente

        fascicoli = app.extensions["core_runtime"]["get_fascicoli"]()
        leggi_fascicolo(fascicoli.get(fascicolo_id))

        registro, tenant = registro_corrente(), tenant_corrente()
        consegne = registro.consegne(tenant, fascicolo_id, presidio="scadenziario")
        assert len(consegne) == 1
        consegna = consegne[0]
        assert consegna.stato == "consegnato" and consegna.chiusa is True
        assert consegna.consegnato_il, "la consegna registra quando è avvenuta"
        identificativi = {s.id for s in get_scadenziario().tutte(id_fascicolo=fascicolo_id, solo_aperte=False)}
        assert consegna.riferimento in identificativi, "il riferimento deve ritrovare la riga creata"
        assert registro.riassunto_consegne(tenant, fascicolo_id)["scadenziario"]["consegnato"] == 1


def test_un_presidio_che_fallisce_non_ferma_la_catena(tmp_path: Path):
    """Il fatto resta da consegnare con il motivo: al giro dopo si riprova."""
    app = _app(tmp_path)
    fascicolo_id = _fascicolo_con_decreto(app)
    with app.app_context():
        from web.services import consegna_presidi_runtime as consegna
        from web.services.archivio_letture_runtime import leggi_fascicolo
        from web.services.registro_letture_runtime import registro_corrente, tenant_corrente

        fascicoli = app.extensions["core_runtime"]["get_fascicoli"]()
        originale = consegna.CONSEGNATARI["scadenziario"]
        consegna.CONSEGNATARI["scadenziario"] = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("scadenziario non scrivibile"))
        try:
            esito = leggi_fascicolo(fascicoli.get(fascicolo_id))
        finally:
            consegna.CONSEGNATARI["scadenziario"] = originale

        assert esito["consegne"]["presidi"]["scadenziario"]["rifiutati"] == 1
        registro, tenant = registro_corrente(), tenant_corrente()
        rifiutata = registro.consegne(tenant, fascicolo_id, presidio="scadenziario")[0]
        assert rifiutata.stato == "rifiutato"
        assert "non scrivibile" in rifiutata.motivo
        assert rifiutata.chiusa is False, "una consegna rifiutata torna: il presidio deve poterci riprovare"

        # Il giro successivo ci riprova e ci riesce.
        ripreso = leggi_fascicolo(fascicoli.get(fascicolo_id), forza=True)
        assert ripreso["consegne"]["presidi"]["scadenziario"]["consegnati"] == 1


@pytest.mark.parametrize("stato", ["consegnato", "non_pertinente"])
def test_una_consegna_chiusa_non_torna_mai(tmp_path: Path, stato: str):
    app = _app(tmp_path)
    fascicolo_id = _fascicolo_con_decreto(app)
    with app.app_context():
        from web.services.registro_letture_runtime import registro_corrente, tenant_corrente

        registro, tenant = registro_corrente(), tenant_corrente()
        registro.segna_consegna(tenant, fascicolo_id, "fatto-x", "scadenziario", stato=stato, riferimento="rif-1")

        class FattoFinto:
            id = "fatto-x"

        assert registro.da_consegnare(tenant, fascicolo_id, "scadenziario", [FattoFinto()]) == []


def test_un_evento_letto_dalla_pec_arriva_in_cronologia():
    """Un evento comunicato dalla cancelleria è un fatto della causa, non un conteggio.

    Il motore PEC lo legge dalla classificazione del presidio e gli allega il
    giorno di ricezione certificato (D.P.R. 68/2005 art. 6): senza quella data
    l'evento non avrebbe posto nel tempo e resterebbe invisibile all'avvocato.
    """
    from datetime import date

    from pct.archivio_letture import eventi_letti
    from pct.archivio_letture.collaudo import Contesto
    from pct.archivio_letture.motore_pec import fatti_da_messaggio
    from pct.fascicolo_lettura.archivio import archivio
    from pct.fascicolo_lettura.cronologia import cronologia

    messaggio = {
        "received_at": "2026-09-10T11:20:00",
        "subject": "COMUNICAZIONE DI CANCELLERIA - RG 5120/2025",
        "from": "tribunale.castrovillari@giustiziacert.it",
        "eventi": [{"primary_event": "rinvio", "family": "udienza", "priority": "alta"}],
    }
    fatti = fatti_da_messaggio(messaggio, Contesto(oggi=date(2026, 9, 15)))
    for fatto in fatti:
        fatto.oggetto_id, fatto.tipo = "pec-1", "pec"

    letti = eventi_letti(fatti, oggi=date(2026, 9, 15))
    assert [voce["data_iso"] for voce in letti] == ["2026-09-10"], "l'evento porta con sé il giorno della PEC"

    vista = archivio({"riassunto": {}, "azioni": [], "ruoli": [], "eventi": letti, "stato": {}})
    voci = cronologia([], [], [], [], [], "2026-09-15", vista)
    assert [(voce["data_it"], voce["titolo"]) for voce in voci] == [("10/09/2026", "rinvio")]
    assert voci[0]["fonte"] == "archivio delle letture"


def test_un_evento_senza_data_non_entra_in_cronologia():
    """Un evento senza giorno non si mostra: in cronologia non avrebbe posto."""
    fatti = [Fatto(categoria="evento", campo="rinvio", valore="udienza", verifica="verificata", id="e1")]
    assert eventi_letti(fatti) == []



def test_dedup_indicizzato_non_confronta_fatti_certamente_incompatibili(monkeypatch):
    import pct.archivio_letture.deduplica as deduplica

    original = deduplica._compatibile
    confronti = 0

    def contato(gruppo, fatto):
        nonlocal confronti
        confronti += 1
        return original(gruppo, fatto)

    monkeypatch.setattr(deduplica, "_compatibile", contato)
    fatti = [
        Fatto(
            categoria="ruolo", campo="numero_ruolo", valore=f"{indice}/2026",
            verifica="verificata", id=f"f-{indice}", fascicolo_id="F1",
        )
        for indice in range(2000)
    ]

    canonici = deduplica.fatti_canonici(fatti)

    assert [f.id for f in canonici] == [f"f-{indice}" for indice in range(2000)]
    assert confronti == 0


def test_riconciliazione_dry_run_non_scrive_e_applica_solo_riga_automatica_intatta(tmp_path: Path):
    from web.services.consegna_presidi_runtime import riconcilia_consegne
    from web.services.registro_letture_runtime import registro_corrente, tenant_corrente
    from web.helpers import get_scadenziario

    app = _app(tmp_path)
    fascicolo_id = _fascicolo_con_decreto(app)
    with app.app_context():
        from web.services.archivio_letture_runtime import leggi_fascicolo

        fascicolo = app.extensions["core_runtime"]["get_fascicoli"]().get(fascicolo_id)
        leggi_fascicolo(fascicolo)
        registro = registro_corrente()
        tenant = tenant_corrente()
        fatto = next(f for f in registro.fatti(tenant, fascicolo_id) if f.campo == "termine")
        prove = list(fatto.prove) + [{"codice": "fonte_non_ancorata", "esito": "respinta", "dettaglio": "prova test"}]
        import json
        with registro.connection() as conn:
            conn.execute(
                'UPDATE "letture_fatti" SET "verifica" = ?, "prove_json" = ? WHERE "tenant_id" = ? AND "id" = ?',
                ("respinta", json.dumps(prove, ensure_ascii=False), tenant, fatto.id),
            )
        scadenza = get_scadenziario().tutte(id_fascicolo=fascicolo_id, solo_aperte=False)[0]

        piano = riconcilia_consegne(fascicolo, registro, tenant, applica=False)

        assert piano["dry_run"] is True
        assert piano["da_rettificare"] == [{
            "presidio": "scadenziario", "riferimento": scadenza.id,
            "fatto_id": fatto.id, "motivo": "prova test",
        }]
        assert str(get_scadenziario().get(scadenza.id).stato.value) == "APERTO"
        assert next(c for c in registro.consegne(tenant, fascicolo_id) if c.fatto_id == fatto.id).stato == "consegnato"

        applicato = riconcilia_consegne(fascicolo, registro, tenant, applica=True)

        assert applicato["scadenze_rettificate"] == 1
        assert str(get_scadenziario().get(scadenza.id).stato.value) == "ANNULLATO"
        assert next(c for c in registro.consegne(tenant, fascicolo_id) if c.fatto_id == fatto.id).stato == "non_pertinente"


def test_nature_documentali_uguali_di_oggetti_diversi_hanno_identita_distinte():
    fatti = [
        Fatto(
            fascicolo_id="F1",
            categoria="classificazione",
            campo="natura_documentale",
            valore="provvedimento",
            verifica="verificata",
            id=f"{oggetto}-{fonte}",
            motore=fonte,
            tipo="documento" if fonte == "documenti" else "allegato_pec",
            oggetto_id=oggetto,
        )
        for oggetto in ("D1", "D2")
        for fonte in ("documenti", "pec")
    ]

    canonici = fatti_canonici(fatti)

    assert len(canonici) == 2
    assert {fatto.oggetto_id for fatto in canonici} == {"D1", "D2"}
    assert len({fatto.id for fatto in canonici}) == 2
