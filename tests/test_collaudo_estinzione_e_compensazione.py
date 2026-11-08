"""Processo estinto riconosciuto dalla Lettura e spese compensate nel presidio (collaudo 08/11/2026).

- RG 771/2025 Tribunale di Palmi (lavoro): ordinanza «Ordina la cancellazione della causa dal ruolo e dichiara
  l'estinzione del processo», ma la Lettura restava in «trattazione».
- RG 2962/2023 Giudice di Pace di Palmi: sentenza che «compensa interamente le spese», ma il presidio proponeva
  «Registrare liquidazione del giudice».
"""

from __future__ import annotations

from datetime import date

from pct.archivio_letture.estrazione_esito import estrai_esito
from pct.fascicolo_lettura.documenti import documenti
from pct.fascicolo_lettura.fase import CODICE_FASE_ESTINTA
from pct.fascicolo_operational_presidio import _economico_sector, spese_senza_liquidazione

ORDINANZA = (
    "R.G. 771 /2025 TRIBUNALE DI PALMI SEZIONE LAVORO ORDINANZA RESA A SEGUITO DI DEPOSITO DI NOTE SCRITTE IN SOSTITUZIONE "
    "DELL'UDIENZA DEL 08/09/2026 Il giudice dott. Carlo Gabutti, ... preso atto del mancato deposito delle note di "
    "trattazione scritta da parte dalle parti; visti gli art. 181 e 309 cod. proc. Civ.\nP.Q.M.\nOrdina la cancellazione "
    "della causa dal ruolo e dichiara l'estinzione del processo.\nSi comunichi. Palmi, 10/09/2026 Il giudice del lavoro "
    "dott. Carlo Gabutti")


def test_estinzione_letta_dal_dispositivo_dell_ordinanza():
    fatti = estrai_esito(ORDINANZA, origine="indice")
    assert [(f.campo, f.valore) for f in fatti] == [("estinzione_processo", "cancellazione_e_estinzione")]
    assert estrai_esito("ORDINANZA ... P.Q.M. rinvia la causa all'udienza del 10/12/2026.", origine="indice") == []


def _lettura_documenti():
    elenco = [{"id": "E1", "nome": "30733829s.pdf", "data_documento": "2026-09-11"}]
    catalogo = [{"document_id": "E1", "document_label": "Provvedimento dell'ufficio giudiziario", "document_section": "provvedimenti",
                 "status": "catalogued"}]
    fonti = [
        {"oggetto_id": "E1", "categoria": "ruolo", "campo": "numero_ruolo", "valore": "771/2025", "verifica": "verificata", "posizione": 5},
        {"oggetto_id": "E1", "categoria": "evento", "campo": "estinzione_processo", "valore": "cancellazione_e_estinzione",
         "verifica": "verificata", "posizione": 600},
        {"oggetto_id": "E1", "categoria": "data", "campo": "data_atto", "valore": "2026-09-10", "verifica": "verificata", "posizione": 700},
    ]
    return documenti(elenco, catalogo, rg="771/2025", fonti=fonti)


def test_la_lettura_riconosce_il_processo_estinto_con_i_passaggi():
    from pct.fascicolo_lettura.fase import fase
    from pct.fascicolo_lettura.prossimi_passi import _passi_estinzione

    letti = _lettura_documenti()
    assert letti["estinzione"]["data_estinzione"] == "2026-09-10"
    intestazione = {"stato_codice": "IN_CORSO", "rg": "771/2025"}
    risultato = fase(intestazione, letti, {"perfezionati": [], "importati": [], "tutti": []}, {"perfezionate": []}, [], [], date(2026, 11, 8))
    assert risultato["codice"] == CODICE_FASE_ESTINTA
    assert "processo estinto" in risultato["descrizione"] and "10/09/2026" in risultato["descrizione"]
    passi = _passi_estinzione(letti["estinzione"])
    azioni = [p.azione for p in passi]
    assert azioni[0].startswith("Verificare mezzo e termine per impugnare") and "10/09/2026" in azioni[0]
    assert "art. 308 c.p.c." in passi[0].motivo and "art. 327 c.p.c." in passi[0].motivo
    assert "Cass. civ., sez. III, n. 29852/2022" in passi[0].motivo  # appello, non reclamo, col giudice monocratico
    assert azioni[1].startswith("Riassunzione non più possibile") and "art. 310 c.p.c." in passi[1].motivo
    assert any("Chiudere il fascicolo" in a for a in azioni)


def test_ordinanza_di_altra_causa_non_estingue_questa():
    from pct.fascicolo_lettura.documenti import documenti as leggi

    letti = leggi([{"id": "E1", "nome": "x.pdf"}], [], rg="100/2026", fonti=[
        {"oggetto_id": "E1", "categoria": "ruolo", "campo": "numero_ruolo", "valore": "771/2025", "verifica": "verificata", "posizione": 5},
        {"oggetto_id": "E1", "categoria": "evento", "campo": "estinzione_processo", "valore": "estinzione", "verifica": "verificata"},
    ])
    assert letti["estinzione"] is None


def test_spese_compensate_niente_liquidazione_del_giudice_nel_presidio():
    items = {"liquidazione_giudice": {"status": "da_registrare", "label": "Liquidazione giudice"}}
    compensate = [{"regolazione": "compensazione"}]
    assert spese_senza_liquidazione(compensate) and not spese_senza_liquidazione([{"regolazione": "condanna"}])
    assert not spese_senza_liquidazione([])
    senza = _economico_sector({"items": items}, None, fid="F1", spese_sentenza=compensate)
    assert not any(a.get("id", "").endswith("liquidazione_giudice") or "liquidazione del giudice" in str(a.get("title")).lower()
                   for a in senza.get("actions") or [])
    con = _economico_sector({"items": items}, None, fid="F1", spese_sentenza=[{"regolazione": "condanna"}])
    assert any("liquidazione del giudice" in str(a.get("title")).lower() for a in con.get("actions") or [])
