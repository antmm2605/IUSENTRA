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

    esempi = list(documenti_inventati(per_voce=2))
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
    righe, corrispondenze, manifesto = righe_dataset(campioni, documenti_inventati(per_voce=1, voci={"Sentenza"}), voci)
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
