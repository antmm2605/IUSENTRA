"""Pagina del fascicolo in otto sezioni numerate, quadro e testata (struttura approvata dall'avvocato il 10/11/2026)."""

from pathlib import Path

COMPONENTI = Path(__file__).resolve().parents[1] / "frontend" / "src" / "components"


def _pagina() -> str:
    sorgente = (COMPONENTI / "FascicoliPage.tsx").read_text(encoding="utf-8")
    return sorgente.split("function DetailPage", 1)[1].split("function QuadroPage", 1)[0] if "function QuadroPage" in sorgente else sorgente.split("function DetailPage", 1)[1]


def _sezione(pagina: str, sezione_id: str) -> str:
    return pagina.split(f'<SezioneFascicolo id="{sezione_id}"', 1)[1].split("</SezioneFascicolo>", 1)[0]


SEZIONI = [
    ("sezione-pratica", ['<DetailSection id="profilo"', '<DetailSection id="cliente"', '<DetailSection id="soggetti"', '<DetailSection id="uffici-competenti"']),
    ("sezione-andamento", ['<DetailSection id="lettura-fascicolo"', '<DetailSection id="attivita"', 'id="avanzamento"', '<DetailSection id="mediazione"', '<DetailSection id="ctu"']),
    ("sezione-termini", ["<AgendaFascicoloCompatta", '<DetailSection id="udienze"']),
    ("sezione-documenti", ['<DetailSection id="documenti"', '<DetailSection id="editor-fascicolo"']),
    ("sezione-comunicazioni", ['<DetailSection id="comunicazioni-notifica"']),
    ("sezione-economia", ['<DetailSection id="conto-economico"', "<PresidioEconomicoSection"]),
    ("sezione-deposito", ["<RegiaOperativaSection", '<DetailSection id="penale-pdp"', '<DetailSection id="pat-formweb"', '<DetailSection id="ptt-sigit"', '<DetailSection id="telematico"']),
    ("sezione-registro", ["<ControlliFascicoloSection", "<AuditTrailSection", '<DetailSection id="eventi-tecnici"', '<DetailSection id="conservazione"', '<DetailSection id="gestione"']),
]


def test_otto_sezioni_in_ordine_con_i_pannelli_esistenti():
    pagina = _pagina()
    posizioni = [pagina.index(f'<SezioneFascicolo id="{sezione_id}"') for sezione_id, _ in SEZIONI]
    assert posizioni == sorted(posizioni)
    for sezione_id, pannelli in SEZIONI:
        corpo = _sezione(pagina, sezione_id)
        for pannello in pannelli:
            assert pannello in corpo, f"{pannello} deve stare in {sezione_id}"
    # Ogni pannello compare una sola volta: nessun doppione fra sezioni.
    for pannello in ['<DetailSection id="documenti"', '<DetailSection id="udienze"', '<DetailSection id="conto-economico"', '<DetailSection id="gestione"', "<RegiaOperativaSection", "<AuditTrailSection"]:
        assert pagina.count(pannello) == 1, pannello
    assert '<aside className="iu-fas-detail-side">' not in pagina


def test_barra_e_ids_delle_sezioni():
    sezioni = (COMPONENTI / "fascicoli" / "SezioneFascicolo.tsx").read_text(encoding="utf-8")
    for sezione_id, _ in SEZIONI:
        assert f"id: '{sezione_id}'" in sezioni
    pagina = _pagina()
    assert "{SEZIONI_FASCICOLO.map((sezione) => <a key={sezione.id} href={`#${sezione.id}`}" in pagina
    # Un collegamento diretto a un pannello apre anche la sezione che lo contiene.
    assert "current instanceof HTMLDetailsElement && !current.open" in sezioni
    assert "style=" not in sezioni


def test_deposito_aperto_solo_con_un_deposito_da_preparare():
    pagina = _pagina()
    assert "loadLazySection('regia')" in pagina
    assert "faseDeposito === 'preparazione'" in pagina
    assert "avviso: data.regia.page_state === 'profilo_da_confermare' ? 'Nessun deposito da preparare · profilo della procedura da confermare' : 'Nessun deposito da preparare'" in pagina
    assert 'apriQuando={depositoSezione.apri} evidenza={depositoSezione.evidenza} avviso={depositoSezione.avviso}' in pagina


def test_ctu_e_mediazione_solo_se_presenti_altrimenti_un_pulsante():
    pagina = _pagina()
    andamento = _sezione(pagina, "sezione-andamento")
    assert "{mostraMediazione ? (" in andamento and "{mostraCtu ? (" in andamento
    assert andamento.count("Aggiungi CTU / mediazione") == 1
    presenza = (COMPONENTI / "fascicoli" / "usePresenzaCtuMediazione.ts").read_text(encoding="utf-8")
    assert ".catch(() => true)" in presenza, "un errore di lettura non deve nascondere CTU o mediazione"


def test_quadro_e_testata_con_stato_unico():
    quadro = (COMPONENTI / "fascicoli" / "QuadroFascicolo.tsx").read_text(encoding="utf-8")
    assert "/api/v1/ui/fascicoli/${encodeURIComponent(fascicoloId)}/quadro" in quadro
    assert "error.status === 404 || error.status === 405" in quadro
    assert "'prossimo_passo', 'termini', 'economia', 'notifiche', 'documenti'" in quadro
    assert "style=" not in quadro
    sorgente = (COMPONENTI / "FascicoliPage.tsx").read_text(encoding="utf-8")
    pagina = _pagina()
    assert "<TestataFascicolo" in pagina and "<QuadroFascicolo" in pagina
    assert "statoQuadro?.etichetta" in pagina
    # Niente diciture contraddittorie accanto allo stato unico.
    assert "Pronto per archivio" not in sorgente
    assert "<Button href=\"#presidio-fascicolo\">" not in sorgente
    testata = (COMPONENTI / "fascicoli" / "TestataFascicolo.tsx").read_text(encoding="utf-8")
    assert testata.count("<Badge") == 1
