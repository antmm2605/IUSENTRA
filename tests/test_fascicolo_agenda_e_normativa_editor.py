"""Agenda compatta in testa al fascicolo e consultazione della normativa nell'editor degli atti (richiesta del 01/11/2026)."""

from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1] / "frontend" / "src" / "components"


def _testo(nome: str) -> str:
    return (FRONTEND / nome).read_text(encoding="utf-8")


def test_agenda_compatta_visibile_in_testa_al_fascicolo_e_caricata_subito():
    pagina = _testo("FascicoliPage.tsx")
    inizio = pagina.index('<div className="iu-fas-detail-main">')
    regia = pagina.index("<RegiaOperativaSection", inizio)
    assert "<AgendaFascicoloCompatta" in pagina[inizio:regia], "l'agenda compatta deve precedere le sezioni richiudibili"
    assert "loadLazySection('scadenze')\n    // eslint-disable-next-line" in pagina, "le scadenze si caricano senza aprire la sezione"


def test_agenda_compatta_usa_le_stesse_voci_dell_agenda_del_fascicolo():
    compatta = _testo("fascicoli/AgendaFascicoloCompatta.tsx")
    assert "vociAgendaFascicolo" in compatta and "prossimiImpegni" in compatta
    assert "style=" not in compatta


def test_editor_atti_ha_il_pulsante_normativa_e_il_pannello():
    editor = _testo("DocumentEditorPage.tsx")
    assert "setNormativaOpen(value => !value)}><BookOpen size={15}/> Normativa</button>" in editor
    assert "{normativaOpen && <EditorNormativaPanel" in editor


def test_pannello_normativa_legge_solo_l_archivio_dei_codici_e_non_scrive_nell_atto():
    pannello = _testo("EditorNormativaPanel.tsx")
    assert "/api/v1/ui/ricerca-legale/normativa" in pannello
    assert "`${base}/atti`" in pannello and "`${base}/articoli?${params}`" in pannello and "`${base}/articoli/${id}`" in pannello
    assert "navigator.clipboard.writeText" in pannello
    assert "execCommand" not in pannello and "style=" not in pannello
