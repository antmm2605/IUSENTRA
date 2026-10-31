"""Pacchetto di addestramento del modello di catalogazione: pseudonimi, esempi inventati, esportazione, misure."""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

from pct.document_intelligence.catalog_lex import NESSUNA_VOCE, citazione_nel_testo, domanda, voci_catalogo
from pct.document_intelligence.verita.esperimento import Campione
from pct.document_intelligence.verita.esportazione import FORMATO, citazione, righe_dataset
from pct.document_intelligence.verita.pseudonimi import parole_da_nascondere, pseudonimizza
from pct.document_intelligence.verita.sintetici import documenti_inventati

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "addestramento_catalogo"))
import dati as dati_pc

TESTO = ("TRIBUNALE DI PALMI - Sezione Lavoro\nIl Giudice Dott.ssa Laura Neri ha pronunciato la seguente SENTENZA\n"
         "nella causa iscritta al R.G. n. 1428/2026 promossa da ROMEO MARIA, nata a Gioia Tauro (RC) il 12/03/1980, "
         "C.F. RMOMRA80C52E041X, residente in Via Roma 12, rappresentata dall'Avv. Anna Bianchi (anna.bianchi@pec.it), "
         "tel. 333 1234567, P.IVA 01234567890, contro MINISTERO DELL'ISTRUZIONE E DEL MERITO. Il giudice Verdi rigetta.")


def test_pseudonimizzazione_toglie_i_dati_e_conserva_l_atto():
    nomi = parole_da_nascondere(["Romeo Maria", "Ministero dell'Istruzione e del Merito", "Verdi Giuseppe"])
    uscita = pseudonimizza(TESTO, nomi)
    for dato in ("Romeo", "ROMEO", "MARIA", "Neri", "Bianchi", "Verdi", "RMOMRA80C52E041X", "Gioia Tauro", "12/03/1980",
                 "Via Roma", "anna.bianchi", "333 1234567", "01234567890", "1428/2026"):
        assert dato not in uscita, dato
    for resta in ("TRIBUNALE DI PALMI", "SENTENZA", "MINISTERO DELL'ISTRUZIONE E DEL MERITO", "rigetta"):
        assert resta in uscita, resta


def test_esempi_inventati_classificati_dal_catalogo_con_la_voce_prevista():
    from pct.document_intelligence.catalog_resolver import _classify_indexed_content

    esempi = list(documenti_inventati(per_voce=2, modelli_atti=False))
    assert len({e.voce for e in esempi}) >= 140
    for esempio in esempi[::25]:
        assert _classify_indexed_content(esempio.testo).label == esempio.voce
    assert documenti_inventati.__defaults__  # firma stabile per l'esportazione


def test_citazione_dell_intestazione_verificata_dal_catalogo():
    testo = "TRIBUNALE DI ESEMPIO\n\nATTO DI PRECETTO\nIntimo di pagare entro dieci giorni."
    assert citazione(testo) == "TRIBUNALE DI ESEMPIO ATTO DI PRECETTO"
    assert citazione_nel_testo(citazione(testo), testo)


def _campione(n: int, voce: str, **kw) -> Campione:
    base = {"document_id": f"D{n}", "fascicolo_id": "F1", "voce": voce, "confidenza": 99, "stato": "proposed",
            "testo": f"PROCURA ALLE LITI\nIo sottoscritto ROMEO MARIA nomino {n}", "origine": "verified_snapshot",
            "nomi": frozenset(parole_da_nascondere(["Romeo Maria"]))}
    base.update(kw)
    return Campione(**base)


def test_esportazione_gruppi_codici_opachi_e_testi_pseudonimizzati():
    voci = {v.label for v in voci_catalogo()}
    campioni = [_campione(n, "Procura alle liti") for n in range(40)]
    campioni.append(_campione(100, "Procura alle liti", confidenza=80))
    campioni.append(_campione(101, "Sentenza", confidenza=80, voce_avvocato="Procura alle liti"))
    righe, corrispondenze, manifesto = righe_dataset(campioni, documenti_inventati(per_voce=1, voci={"Sentenza"}, modelli_atti=False), voci)
    assert manifesto["formato"] == FORMATO
    gruppi = {r["gruppo"] for r in righe}
    assert gruppi == {"addestramento", "verifica", "verifica_avvocato", "da_rivedere"}
    testo = json.dumps(righe, ensure_ascii=False)
    assert "ROMEO" not in testo and "MARIA" not in testo and "D101" not in testo and "F1" not in testo
    assert {c["document_id"] for c in corrispondenze.values()} >= {"D100", "D101"}
    assert all("risposta" not in r for r in righe if r["gruppo"] == "da_rivedere")
    assert any(r["fonte"] == "inventato" for r in righe)


def test_funzioni_del_pc_leggono_il_pacchetto_e_misurano(tmp_path):
    voci = voci_catalogo()
    prefisso = domanda("", voci)
    assert dati_pc.NESSUNA_VOCE == NESSUNA_VOCE
    assert dati_pc.voci_del_prefisso(prefisso) == {v.label for v in voci}
    breve = dati_pc.prefisso_breve(prefisso)
    assert not dati_pc.voci_del_prefisso(breve) and breve.endswith("DOCUMENTO:\n") and len(breve) < len(prefisso) / 2
    righe, _, manifesto = righe_dataset([_campione(n, "Procura alle liti") for n in range(30)], [], {v.label for v in voci})
    (tmp_path / "manifesto.json").write_text(json.dumps(manifesto), encoding="utf-8")
    (tmp_path / "prefisso_domanda.txt").write_text(prefisso, encoding="utf-8")
    (tmp_path / "dataset.jsonl.gz").write_bytes(gzip.compress("\n".join(json.dumps(r) for r in righe).encode()))
    letto_prefisso, lette, _ = dati_pc.leggi_pacchetto(tmp_path)
    assert letto_prefisso == prefisso and len(lette) == len(righe)
    conversazione = dati_pc.conversazione(prefisso, lette[0])
    assert conversazione[0]["content"].endswith(lette[0]["testo"]) and conversazione[1]["role"] == "assistant"
    giusta = json.loads(lette[0]["risposta"])
    risposte = {r["id"]: dati_pc.leggi_risposta(json.dumps(giusta), dati_pc.voci_del_prefisso(prefisso)) for r in lette}
    esito = dati_pc.misura(lette, risposte)
    assert esito["modello_giuste"] == esito["documenti"] == len(lette)
    assert dati_pc.leggi_risposta('{"etichetta": "Voce inventata"}', {"A"})["etichetta"] == ""


def test_banco_confronta_regole_lineare_e_modelli_sulle_stesse_righe(tmp_path):
    import banco  # tools/addestramento_catalogo, già nel percorso

    voci = voci_catalogo()
    etichette = {v.label for v in voci}
    from pct.document_intelligence.verita.sintetici import SEME_BANCO

    scelte = {"Sentenza", "Procura alle liti", "Verbale di udienza"}
    righe, _, manifesto = righe_dataset([], documenti_inventati(20, voci=scelte, modelli_atti=False), etichette,
                                        banco=documenti_inventati(3, voci=scelte, seme=SEME_BANCO, modelli_atti=False))
    assert manifesto["per_gruppo"]["banco_inventati"] >= 6
    pacchetto = tmp_path / "pacchetto"
    pacchetto.mkdir()
    (pacchetto / "manifesto.json").write_text(json.dumps(manifesto), encoding="utf-8")
    (pacchetto / "prefisso_domanda.txt").write_text(domanda("", voci), encoding="utf-8")
    (pacchetto / "dataset.jsonl.gz").write_bytes(gzip.compress("\n".join(json.dumps(r) for r in righe).encode()))
    finto = tmp_path / "qwen"
    finto.mkdir()
    (finto / "predizioni.jsonl").write_text("\n".join(
        json.dumps({"id": r["id"], "gruppo": r["gruppo"], "etichetta": "Sentenza"}) for r in righe
        if r["gruppo"] == "banco_inventati"), encoding="utf-8")
    sys_argv = ["banco.py", "--pacchetto", str(pacchetto), "--risultati", f"qwen={finto}", "--uscita", str(tmp_path / "esito")]
    import sys as _sys

    vecchi, _sys.argv = _sys.argv, sys_argv
    try:
        assert banco.main() == 0
    finally:
        _sys.argv = vecchi
    risultati = json.loads((tmp_path / "esito" / "banco.json").read_text(encoding="utf-8"))["risultati"]
    assert risultati["regole"]["banco_inventati"]["accuratezza"] == 100.0
    assert risultati["qwen"]["banco_inventati"]["giuste"] < risultati["qwen"]["banco_inventati"]["valutate"]
    assert risultati["lineare"]["banco_inventati"]["valutate"] == manifesto["per_gruppo"]["banco_inventati"]


def test_decisioni_sui_disaccordi_diventano_verifica_con_la_fonte(tmp_path):
    righe = [{"id": "a", "gruppo": "da_rivedere", "voce": "", "voce_lineare": "Sentenza"},
             {"id": "b", "gruppo": "da_rivedere", "voce": ""},
             {"id": "c", "gruppo": "addestramento", "voce": "Procura alle liti"}]
    file = tmp_path / "decisioni.jsonl"
    file.write_text("\n".join(json.dumps(d) for d in [
        {"id": "a", "voce": "Verbale di udienza", "fonte": "claude"},
        {"id": "c", "voce": "Sentenza", "fonte": "claude"}]), encoding="utf-8")
    uscita = {r["id"]: r for r in dati_pc.applica_decisioni(righe, file)}
    assert uscita["a"]["gruppo"] == "verifica_decisioni" and uscita["a"]["voce"] == "Verbale di udienza"
    assert uscita["a"]["fonte"] == "decisione_claude"
    assert uscita["b"]["gruppo"] == "da_rivedere"
    # Una riga di addestramento non diventa verifica: resterebbe vista dal modello.
    assert uscita["c"]["gruppo"] == "addestramento" and uscita["c"]["voce"] == "Procura alle liti"


def test_la_citazione_salta_numeri_di_pagina_e_non_mozza_le_parole():
    for testo in ("TRIBUNALE ORDINARIO DI MILANO SEZIONE QUARTA CIVILE " * 8 + "\nricorso",
                  "1\n2\n- - -\nATTO DI CITAZIONE\nper il sig. X",
                  "Pag. 1 di 3\n\nALL'ILL.MO TRIBUNALE DI ROMA\nricorso ex art. 702-bis"):
        assert citazione_nel_testo(citazione(testo), testo)
    assert citazione("Pag. 1 di 3\n\nALL'ILL.MO TRIBUNALE DI ROMA\nricorso").startswith("ALL'ILL.MO")


def test_gli_esempi_inventati_coprono_le_nuove_voci():
    nuove = {"Nota di iscrizione a ruolo", "Contributo unificato / pagamento", "Relazione peritale CTU",
             "Avviso di ricevimento postale", "Fattura", "Procura speciale per la mediazione"}
    voci = {d.voce for d in documenti_inventati(3, voci=nuove, modelli_atti=False)}
    assert voci == nuove


def test_i_modelli_di_atti_danno_documenti_solo_con_la_voce_riconosciuta_dal_catalogo():
    from pct.document_intelligence.verita.sintetici import documenti_dai_modelli

    def classifica(testo: str) -> tuple[str, int]:
        return ("Atto di citazione", 96) if "CITAZIONE" in testo.upper() else ("Atto difensivo", 99)

    documenti = list(documenti_dai_modelli(2, voci={"Atto di citazione"}, per_voce=5, classifica=classifica))
    assert documenti and len(documenti) <= 5
    assert {d.voce for d in documenti} == {"Atto di citazione"}
    assert all(d.origine.startswith("modello_atto:") and "avv. studio prova" in d.testo.lower() for d in documenti)


def test_la_voce_si_legge_anche_con_sezione_maiuscole_o_risposta_troncata():
    """Misura del 31/10/2026: il Qwen di partenza risultava illeggibile al 100% per il formato della voce."""
    from tools.addestramento_catalogo.dati import NESSUNA_VOCE, leggi_risposta

    voci = {"Sentenza", "Nota di deposito", "Decreto di fissazione udienza"}
    assert leggi_risposta('{"etichetta": "Sentenza [atti]", "citazione": "x"}', voci)["etichetta"] == "Sentenza"
    assert leggi_risposta('Risposta: {"etichetta": "nota di deposito"}', voci)["etichetta"] == "Nota di deposito"
    troncata = '{"etichetta": "Decreto di fissazione udienza", "citazione": "il giudice fissa", "motivo": "il decreto'
    assert leggi_risposta(troncata, voci)["etichetta"] == "Decreto di fissazione udienza"
    assert leggi_risposta('{"etichetta": "Nessuna voce del catalogo"}', voci)["etichetta"] == NESSUNA_VOCE
    # Nessuna voce indovinata per somiglianza.
    assert leggi_risposta('{"etichetta": "Sentenze"}', voci)["etichetta"] == ""


def test_il_modello_di_partenza_riceve_lo_schema_della_risposta():
    from tools.addestramento_catalogo.dati import prefisso_per_modello_di_partenza

    domanda = prefisso_per_modello_di_partenza("Voci del catalogo (etichetta [sezione]):\n- Sentenza [atti]\nRispondi solo con il JSON richiesto.")
    assert '"etichetta"' in domanda and '"citazione"' in domanda and domanda.index("Sentenza") < domanda.index('"etichetta"')
