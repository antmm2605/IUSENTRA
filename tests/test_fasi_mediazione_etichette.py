"""Fasi della mediazione: all'avvocato si mostrano le denominazioni dell'art. 20, comma 1-bis.

Base normativa: D.M. 10 marzo 2014, n. 55, art. 20, comma 1-bis (testo vigente dal
23/10/2022): fasi «dell'attivazione», «di negoziazione» e «di conciliazione»; con
l'accordo aumentano del 30% le fasi dell'attivazione e di negoziazione. La chiave
interna storica «rivitalizzazione» (colonna Istruttoria della Tabella 27) resta
invariata nei dati salvati; nessuna etichetta visibile la deve mostrare.
"""

from __future__ import annotations

import json
from pathlib import Path

from pct.motore_preventivo import _adr_variation_policy
from pct.tariffario import Fase, Materia, Grado, calcola_compenso, etichetta_fase
from pct.tariffario_catalogo import PHASE_LABEL_BY_KEY, phase_catalog_by_materia
from web.services.react_tariffario_compute import build_react_tariffario_run_payload

REPO = Path(__file__).resolve().parents[1]


class _Tabelle:
    def __getattr__(self, name):
        return lambda: []


def _visibile(testo: str) -> bool:
    return "rivitalizz" not in testo.lower()


def test_chiave_interna_invariata_ed_etichetta_della_norma():
    assert Fase.RIVITALIZZAZIONE.value == "Fase di rivitalizzazione"
    assert etichetta_fase(Fase.RIVITALIZZAZIONE.value) == "Fase di negoziazione"
    assert etichetta_fase("Rivitalizzazione") == "Negoziazione"
    assert PHASE_LABEL_BY_KEY["rivitalizzazione"] == "Negoziazione"


def test_catalogo_fasi_mediazione_mostra_attivazione_negoziazione_conciliazione():
    etichette = [row["label"] for row in phase_catalog_by_materia()[Materia.MEDIAZIONE.value]]
    assert etichette == ["Attivazione", "Negoziazione", "Conciliazione"]


def test_politica_adr_e_bonus_accordo_senza_rivitalizzazione():
    policy = _adr_variation_policy("mediazione")
    assert [row["key"] for row in policy["phase_controls"]] == ["attivazione", "rivitalizzazione", "conciliazione"]
    assert [row["label"] for row in policy["phase_controls"]] == [
        "Fase di attivazione",
        "Fase di negoziazione",
        "Fase di conciliazione",
    ]
    assert _visibile(policy["agreement_bonus"]["description"])


def test_risultato_tariffario_mediazione_righe_metadati_e_note():
    payload = build_react_tariffario_run_payload(
        {"materia": Materia.MEDIAZIONE.value, "valore": "30000", "adr_accordo": "1"},
        get_normative_tables=_Tabelle,
    )
    assert payload["ok"] is True
    result = payload["result"]
    # Testi mostrati: etichette delle righe, metadati, note e note di conformità
    # (gli identificativi e l'audit tecnico conservano la chiave interna).
    visibili = [row.get("label", "") for row in result["table"]["rows"]]
    visibili += [row["value"] for row in result["metadata"]]
    visibili += [str(result.get(key, "")) for key in ("note", "engineText", "complianceNote", "title")]
    testo = json.dumps(visibili, ensure_ascii=False)
    assert "Fase di negoziazione" in testo
    assert _visibile(testo)


def test_note_motore_con_maggiorazione_accordo():
    risultato = calcola_compenso(
        Materia.MEDIAZIONE,
        Grado.PROCEDURA_ADR,
        30000,
        [Fase.ATTIVAZIONE, Fase.RIVITALIZZAZIONE, Fase.CONCILIAZIONE],
        maggiorazioni_fasi={Fase.ATTIVAZIONE.value: 1.3, Fase.RIVITALIZZAZIONE.value: 1.3},
    )
    assert Fase.RIVITALIZZAZIONE.value in risultato.dettaglio  # chiave interna invariata
    assert _visibile(risultato.note)


def test_etichette_nei_template_e_nel_frontend():
    for rel in (
        "frontend/src/preventivoWizardUtils.ts",
        "web/templates/preventivi/wizard.html",
        "web/templates/preventivi/form_preventivo.html",
    ):
        testo = (REPO / rel).read_text(encoding="utf-8")
        assert "'Rivitalizzazione'" not in testo, rel
        assert "label: 'Fase di rivitalizzazione'" not in testo, rel


def test_pdf_preventivo_mostra_fase_di_negoziazione():
    import pdfplumber

    from pct.preventivi import Preventivo, VocePreventivo
    from web.blueprints.preventivi import _genera_pdf_preventivo

    preventivo = Preventivo(
        id="prova", numero="2026/999", id_cliente="", id_fascicolo=None,
        data_emissione="2026-11-02", data_scadenza="2026-12-02", oggetto="Mediazione",
        voci=[VocePreventivo(descrizione="Compenso Fase di rivitalizzazione", importo=100.0)],
    )
    buf = _genera_pdf_preventivo(preventivo, None, None, {})
    with pdfplumber.open(buf) as pdf:
        testo = "\n".join(page.extract_text() or "" for page in pdf.pages)
    assert "negoziazione" in testo
    assert _visibile(testo)
