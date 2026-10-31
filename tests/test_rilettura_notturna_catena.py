"""Prova reale della rilettura notturna: tutta la catena, prima della prima notte in produzione (31/10/2026).

Documenti PDF veri letti dal motore, rilettura come se fossero stati letti dal motore del 17/09/2026,
consegna ai presìdi, nessun doppione, decisioni dell'avvocato conservate, fascicolo di nuovo «fermo»,
tempi misurati.
"""

from __future__ import annotations

import time
from pathlib import Path

from pct.fascicoli import TipoDocumento, TipoFascicolo
from tests.test_archivio_letture_runtime import _app, _fascicolo, _pdf

VECCHIA = "2026.09.16.motore-documenti.v7+2026.09.15.formulario-legale.v3"

DECRETO = _pdf([
    "TRIBUNALE DI TORINO - Sezione Lavoro - R.G. n. 777/2026",
    "Il Giudice dispone che l'udienza del 14/04/2027 sia sostituita dal deposito di note scritte",
    "ai sensi dell'art. 127 ter c.p.c. e assegna alle parti termine del 07/04/2027 per il deposito di note scritte.",
])
COPIA_DECRETO = _pdf([
    "TRIBUNALE DI TORINO - Sezione Lavoro - R.G. n. 777/2026 - copia",
    "Il Giudice dispone che l'udienza del 14/04/2027 sia sostituita dal deposito di note scritte",
    "ai sensi dell'art. 127 ter c.p.c. e assegna alle parti termine del 07/04/2027 per il deposito di note scritte.",
])
RELATA = _pdf([
    "RELATA DI NOTIFICA ai sensi dell'art. 3-bis della legge 21 gennaio 1994 n. 53",
    "Io sottoscritto avv. Mario Rossi notifico il presente atto a mezzo PEC.",
    "Ricevuta di accettazione del 05/09/2026 ore 10:15 e ricevuta di avvenuta consegna del 05/09/2026 ore 10:16.",
])
PRECEDENTE = _pdf([
    "REPUBBLICA ITALIANA - IN NOME DEL POPOLO ITALIANO",
    "TRIBUNALE DI COSENZA - Sezione Lavoro - R.G. n. 1234/2022",
    "SENTENZA n. 394/2023 - il Giudice del lavoro definitivamente pronunciando accoglie il ricorso.",
])


def _semina(app):
    with app.app_context():
        fascicoli = app.extensions["core_runtime"]["get_fascicoli"]()
        f = fascicoli.nuovo("Bianchi / Ministero", TipoFascicolo.LAVORO, nome_cliente="Anna Bianchi",
                            tribunale="Tribunale di Torino", numero_rg="777", anno_rg=2026)
        for nome, contenuto in (("decreto.pdf", DECRETO), ("decreto_copia_pec.pdf", COPIA_DECRETO), ("relata.pdf", RELATA),
                                ("Tribunale-di-Cosenza-Sentenza-n.-394-2023.pdf", PRECEDENTE)):
            fascicoli.aggiungi_documento(f.id, nome_file=nome, tipo=TipoDocumento.ALTRO, contenuto=contenuto)
        return f.id


def _invecchia(registro, tenant, fascicolo_id):
    """Come in produzione: letture e riga del fascicolo registrate dal motore del 17/09/2026."""
    from web.services.archivio_letture_runtime import LETTORE_DOCUMENTI

    letti = {(l.tipo, l.oggetto_id, l.sha256) for l in registro.letture(tenant, fascicolo_id, lettore=LETTORE_DOCUMENTI)}
    for oggetto in registro.oggetti(tenant, fascicolo_id):
        if (oggetto.tipo, oggetto.oggetto_id, oggetto.impronta) in letti:
            registro.segna_letto(tenant, fascicolo_id, oggetto, LETTORE_DOCUMENTI, versione=VECCHIA)
    riga = next(r for r in registro.righe_fascicoli(tenant, lettore=LETTORE_DOCUMENTI) if r["fascicolo_id"] == fascicolo_id)
    registro.segna_fascicolo(tenant, fascicolo_id, LETTORE_DOCUMENTI, impronta=riga["impronta"],
                             oggetti_totali=int(riga["oggetti_totali"]), oggetti_letti=int(riga["oggetti_letti"]), versione=VECCHIA)


def test_rilettura_notturna_dell_intera_catena(tmp_path: Path):
    app = _app(tmp_path)
    fascicolo_id = _semina(app)
    with app.app_context():
        from web.helpers import get_agenda, get_scadenziario
        from web.services import archivio_letture_runtime as runtime
        from web.services.registro_letture_runtime import registro_corrente, tenant_corrente

        registro, tenant = registro_corrente(), tenant_corrente()
        fascicolo = _fascicolo(app, fascicolo_id)
        primo = runtime.leggi_fascicolo(fascicolo)
        assert primo["documenti"]["letti"] == 4
        scadenze_prima = [s for s in get_scadenziario().tutte(id_fascicolo=fascicolo_id, solo_aperte=False)]
        agenda_prima = list(get_agenda().tutti())
        # Lo stesso termine letto dal decreto e dalla sua copia resta una sola scadenza.
        termini_07_04 = [s for s in scadenze_prima if s.data_scadenza == "2027-04-07"]
        assert len(termini_07_04) <= 1

        # Una decisione dell'avvocato prima della rilettura.
        fatti = runtime.fatti_fascicolo(fascicolo, canonico=False)
        deciso = next(f for f in fatti if f.categoria == "data")
        registro.decidi_fatto(tenant, deciso.id, verifica="corretta", valore=deciso.valore, utente_id="avvocato")

        _invecchia(registro, tenant, fascicolo_id)
        riga = next(r for r in registro.righe_fascicoli(tenant, lettore=runtime.LETTORE_DOCUMENTI) if r["fascicolo_id"] == fascicolo_id)
        assert runtime.stato_lettura_fascicolo(riga, {}) == "da_aggiornare"
        assert runtime.accoda_riletture_notturne(registro, tenant, ora=2) == 1

        avvio = time.monotonic()
        rilettura = runtime.leggi_fascicolo(_fascicolo(app, fascicolo_id), registro=registro, recupera_metadati=True,
                                            rileggi_superati=True)
        durata = time.monotonic() - avvio

        assert rilettura["documenti"]["riletti"] == 4 and rilettura["restano"] == 0 and rilettura["fermo"]
        assert not (rilettura.get("consegne") or {}).get("errore")
        # Nessun doppione nato dalla rilettura.
        scadenze_dopo = list(get_scadenziario().tutte(id_fascicolo=fascicolo_id, solo_aperte=False))
        assert len(scadenze_dopo) == len(scadenze_prima)
        assert len(list(get_agenda().tutti())) == len(agenda_prima)
        # La decisione dell'avvocato resta.
        assert next(f for f in registro.fatti(tenant, fascicolo_id, verifiche=None) if f.id == deciso.id).verifica == "corretta"
        # Il fascicolo torna «fermo» con la versione corrente; un secondo giro non rilegge nulla.
        riga = next(r for r in registro.righe_fascicoli(tenant, lettore=runtime.LETTORE_DOCUMENTI) if r["fascicolo_id"] == fascicolo_id)
        assert runtime.stato_lettura_fascicolo(riga, {}) == "fermo"
        secondo = runtime.leggi_fascicolo(_fascicolo(app, fascicolo_id), registro=registro, rileggi_superati=True)
        assert secondo["documenti"]["letti"] == 0
        assert durata < 60, f"rilettura troppo lenta: {durata:.1f} s"
        # Il precedente di un altro tribunale non diventa un obbligo di notifica.
        from web.services.obblighi_notifica_runtime import obblighi_fascicolo

        assert not any("Cosenza" in str(o.get("documento") or "") for o in obblighi_fascicolo(_fascicolo(app, fascicolo_id)))


def test_precedente_di_altro_ufficio_fuori_da_notifiche_ed_economia(tmp_path: Path):
    """Visto in produzione: liquidazione delle spese presa dalla sentenza di Vicenza allegata come precedente."""
    from types import SimpleNamespace

    from pct.archivio_letture.pertinenza_documentale import precedenti_del_fascicolo

    fascicolo = SimpleNamespace(tribunale="Tribunale di Torino", documenti=[
        SimpleNamespace(id="D1", nome="Sentenza_Tribunale_Vicenza_20-04-2023.PDF"),
        SimpleNamespace(id="D2", nome="decreto.pdf"),
        SimpleNamespace(id="D3", nome="nota.pdf"),
    ])
    fatti = [SimpleNamespace(oggetto_id="D3", campo="natura_documentale", valore="precedente_giurisprudenziale", verifica="verificata"),
             SimpleNamespace(oggetto_id="D2", campo="natura_documentale", valore="precedente_giurisprudenziale", verifica="respinta")]
    assert precedenti_del_fascicolo(fascicolo, fatti) == {"D1", "D3"}

    app = _app(tmp_path)
    fascicolo_id = _semina(app)
    with app.app_context():
        from web.services import archivio_letture_runtime as runtime
        from web.services.react_fascicoli_bridge import _importi_dall_archivio

        f = _fascicolo(app, fascicolo_id)
        runtime.leggi_fascicolo(f)
        voci = _importi_dall_archivio(_fascicolo(app, fascicolo_id), {})
        documenti = {d.id: d.nome for d in _fascicolo(app, fascicolo_id).documenti}
        for voce in voci.values():
            for fonte in voce.get("fontiVerifica") or []:
                assert "Cosenza" not in documenti.get(str(fonte.get("documentoId")), "")
