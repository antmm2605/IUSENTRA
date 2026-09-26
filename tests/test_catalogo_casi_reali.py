"""Catalogo: i casi che nel fascicolo reale finivano a 55 «da verificare» (testi sintetici).

- una sentenza o ordinanza si riconosce da «ha pronunciato la presente …»;
- la procura alle liti dal titolo e dalla formula di delega;
- la nota di deposito dal foliario del deposito TAR;
- il profilo del catalogo segue il tipo del fascicolo quando area e branca mancano.
"""

from __future__ import annotations

import pytest

from pct.document_intelligence.catalog_resolver import resolve_document_catalog

CTX_AMMINISTRATIVO = {"tipo_fascicolo": "amministrativo", "tribunale": "TAR Lombardia"}


def _cataloga(testo: str, contesto: dict | None = None, nome: str = "documento.pdf"):
    return resolve_document_catalog(
        tenant_id="t", fascicolo_id="F", document_id=nome, document_sha256="", filename=nome,
        extracted_text=testo, document_metadata={}, fascicolo_context=dict(contesto or CTX_AMMINISTRATIVO),
    )


@pytest.mark.parametrize(
    ("testo", "etichetta"),
    [
        (
            "N. 00457/2026 REG.RIC.\nREPUBBLICA ITALIANA\nIN NOME DEL POPOLO ITALIANO\nIl Tribunale Amministrativo Regionale per la Lombardia\n"
            "ha pronunciato la presente SENTENZA sul ricorso numero di registro generale 457 del 2026, proposto da Anna Rosa, "
            "rappresentata e difesa dall'avvocato Carlo Bianchi;\ncontro\nComune di Alfa;",
            "Sentenza",
        ),
        (
            "N. 00458/2026 REG.RIC.\nIl Tribunale Amministrativo Regionale per la Lombardia\nha pronunciato la presente ORDINANZA "
            "sul ricorso numero di registro generale 458 del 2026, proposto da Marco Viola;",
            "Ordinanza",
        ),
        (
            "PROCURA ALLE LITI\nIl sottoscritto Marco Viola, c.f. VLIMRC70A01F205X, delega a rappresentarlo e difenderlo nel presente "
            "procedimento l'Avv. Carlo Bianchi, conferendogli ogni facoltà di legge.",
            "Procura alle liti",
        ),
        (
            "Tribunale Amministrativo Regionale per la Lombardia\nFoliario Deposito ricorso - Atto principale: Ricorso per l'ottemperanza - "
            "Atti secondari: Procura, Sentenza, Notifiche.\n02.03.2026 Avv. Carlo Bianchi",
            "Nota di deposito",
        ),
        (
            "ECC.MO TRIBUNALE AMMINISTRATIVO REGIONALE PER LA LOMBARDIA\nRICORSO PER L'OTTEMPERANZA\nex art. 112 e ss. c.p.a.\n"
            "PER Marco Viola, rappresentato e difeso dall'Avv. Carlo Bianchi\nCONTRO Comune di Alfa\nper l'esecuzione della sentenza "
            "n. 100/2025 passata in giudicato.",
            "Ricorso per l'ottemperanza (art. 114 c.p.a.)",
        ),
    ],
)
def test_casi_del_fascicolo_amministrativo(testo, etichetta):
    esito = _cataloga(testo)
    assert esito.document_label.startswith(etichetta), (esito.document_label, esito.reason)
    assert esito.status == "proposed"
    assert esito.profile_id == "PAT"
    assert esito.confidence > 55


@pytest.mark.parametrize(
    ("tipo", "profilo"),
    [("amministrativo", "PAT"), ("tributario", "TRIB"), ("lavoro", "LAV"), ("civile", "CIV-PCT")],
)
def test_il_profilo_segue_il_tipo_del_fascicolo(tipo, profilo):
    esito = _cataloga("PROCURA ALLE LITI\nIl sottoscritto Marco Viola delega a rappresentarlo e difenderlo l'Avv. Carlo Bianchi.", {"tipo_fascicolo": tipo})
    assert esito.profile_id == profilo
