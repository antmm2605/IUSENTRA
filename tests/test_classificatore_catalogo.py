"""Classificatore piccolo del catalogo: addestramento deterministico, misura e disaccordi, riepilogo senza dati."""
from __future__ import annotations

import json

from pct.document_intelligence.verita.classificatore import addestra, in_verifica, parole
from pct.document_intelligence.verita.esperimento import Campione, misura

INTESTAZIONI = {
    "Sentenza": "TRIBUNALE ORDINARIO REPUBBLICA ITALIANA IN NOME DEL POPOLO ITALIANO il giudice ha pronunciato la seguente sentenza",
    "Procura alle liti": "PROCURA ALLE LITI nomino e costituisco mio procuratore e difensore conferendo ogni facolta di legge",
    "Relata di notifica": "RELATA DI NOTIFICA io sottoscritto avvocato ho notificato il presente atto mediante posta elettronica certificata",
}


def _campione(n: int, voce: str, *, confidenza: int = 99, stato: str = "proposed", testo: str | None = None,
              voce_avvocato: str = "") -> Campione:
    return Campione(document_id=f"{voce[:3]}-{n}", fascicolo_id=f"F{n % 7}", testo=testo or f"{INTESTAZIONI[voce]} numero {n}",
                    voce=voce, confidenza=confidenza, stato=stato, origine="verified_snapshot", voce_avvocato=voce_avvocato)


def test_parole_senza_accenti_e_con_coppie():
    assert parole("Procura alle LITI, facoltà") == ["procura", "alle", "liti", "facolta",
                                                    "procura_alle", "alle_liti", "liti_facolta"]


def test_addestramento_deterministico_e_corretto():
    testi = [f"{INTESTAZIONI[v]} {n}" for v in INTESTAZIONI for n in range(20)]
    etichette = [v for v in INTESTAZIONI for _ in range(20)]
    primo, secondo = addestra(testi, etichette), addestra(testi, etichette)
    assert (primo.pesi == secondo.pesi).all()
    previsione = primo.predici(["il giudice ha pronunciato la seguente sentenza nella causa"])[0]
    assert previsione[0] == "Sentenza" and previsione[1] > 0.5


def test_separazione_stabile_della_verifica():
    assert in_verifica("doc-1") == in_verifica("doc-1")
    quota = sum(in_verifica(f"doc-{n}") for n in range(2000)) / 2000
    assert 0.15 < quota < 0.25


def test_misura_trova_il_disaccordo_sicuro_e_non_porta_testi_nel_riepilogo():
    campioni = [_campione(n, v) for v in INTESTAZIONI for n in range(60)]
    # Una proposta incerta delle regole («Procura alle liti») su un testo che è chiaramente una sentenza.
    campioni.append(_campione(999, "Procura alle liti", confidenza=80, testo=INTESTAZIONI["Sentenza"] + " Mario Rossi"))
    campioni.append(_campione(998, "Sentenza", confidenza=80, stato="review_required"))
    # Una decisione dell'avvocato documento per documento.
    campioni.append(_campione(997, "Procura alle liti", confidenza=80, testo=INTESTAZIONI["Sentenza"], voce_avvocato="Sentenza"))
    esito = misura(campioni, minimo=30)
    riepilogo = esito["riepilogo"]
    assert riepilogo["esito"] == "misurato"
    assert riepilogo["verifica_quasi_certe"]["accordo_totale"] == riepilogo["esempi_verifica"]
    assert riepilogo["fascia_incerta"]["concorda"] >= 1
    assert riepilogo["disaccordi_sicuri"] == 2
    assert riepilogo["disaccordi_per_coppia"] == {"Procura alle liti → Sentenza": 2}
    assert riepilogo["decisioni_avvocato"] == {"documenti": 1, "giuste_modello": 1, "giuste_regole": 0}
    assert {d["document_id"] for d in esito["disaccordi"]} == {"Pro-999", "Pro-997"}
    testo = json.dumps(riepilogo, ensure_ascii=False)
    assert "Rossi" not in testo and "Pro-999" not in testo and "giudice" not in testo


def test_voci_con_pochi_esempi_restano_fuori_e_senza_due_voci_non_si_addestra():
    campioni = [_campione(n, "Sentenza") for n in range(40)] + [_campione(n, "Procura alle liti") for n in range(5)]
    esito = misura(campioni, minimo=30)
    assert esito["riepilogo"]["voci_del_modello"] == ["Sentenza"]
    assert esito["riepilogo"]["esito"] == "esempi insufficienti per addestrare"
    assert esito["disaccordi"] == []


def test_runtime_salva_i_disaccordi_nella_cartella_dello_studio(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from web.services import classificatore_catalogo_runtime as runtime

    db = tmp_path / "fascicoli" / "fascicoli.json"
    monkeypatch.setattr("web.helpers.get_fascicoli", lambda: SimpleNamespace(db_path=db))
    runtime._salva_disaccordi([{"document_id": "D1", "voce_regole": "A", "voce_modello": "B"}])
    salvati = json.loads((tmp_path / "intelligence" / runtime.FILE_DISACCORDI).read_text(encoding="utf-8"))
    assert salvati == [{"document_id": "D1", "voce_regole": "A", "voce_modello": "B"}]
