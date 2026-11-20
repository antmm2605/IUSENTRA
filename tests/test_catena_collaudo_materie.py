"""Collaudo end-to-end della catena per ogni materia (richiesta dell'avvocato del 19/11/2026).

Per ogni materia di ``lex/normativa/materie.py`` una pratica di prova, con dati fittizi costruiti sugli esempi delle
fonti ufficiali, attraversa la catena vera: documenti dal punto d'ingresso reale, ciclo delle letture, catalogo,
archivio dei fatti, modello della causa, Lettura, guardiano (scadenziario e agenda), quadro. A ogni passo valgono:

- le **invarianti della catena** (``catena_chiusa``): la Lettura c'è e contiene il modello; il guardiano ha controllato
  e ha riparato ciò che spettava a lui; un secondo giro non trova più nulla da riparare; ogni termine certo dello
  studio è una scadenza aperta con la stessa data e la sua norma; ogni udienza futura del modello è in agenda; nessuna
  scadenza aperta è un termine della controparte; nessun prossimo passo per ciò che risulta fatto con la prova;
- i **risultati attesi scritti dall'avvocato** per quel passo, con la norma vigente (testi verificati nell'archivio
  Normattiva del software, aggiornamento del 05/03/2026, il 19/11/2026).

Le materie il cui rito il motore non modella ancora (penale, amministrativo, tributario, ...) verificano che la catena
non si interrompa e non inventi termini: il limite resta dichiarato nel rapporto, non nascosto.
"""

from __future__ import annotations

import pytest

from lex.normativa.materie import MATERIE
from tests.catena_collaudo import Fotografia, Orologio, Pratica
from tests.catena_collaudo_pratiche import PRATICHE, Passo


@pytest.fixture(scope="module")
def studio(tmp_path_factory):
    from tests.test_archivio_letture_runtime import _app

    with pytest.MonkeyPatch.context() as monkeypatch:
        orologio = Orologio()
        orologio.installa(monkeypatch)
        app = _app(tmp_path_factory.mktemp("studio_catena"))
        # L'avvocato dello studio (Impostazioni): il modello riconosce gli atti dello studio dal suo nome.
        app.config["STUDIO_AVVOCATO"] = "Mario Rossi"
        yield app, orologio


def catena_chiusa(pratica: Pratica, foto: Fotografia) -> None:
    """Le invarianti della catena dopo ogni passo."""
    from pct.catena.guardiano import termine_certo_dello_studio

    assert foto.lettura and foto.ragionamento.get("impronta"), "la Lettura non contiene il modello della causa"
    assert foto.guardiano.get("esito") == "controllato", foto.guardiano
    non_riparate = [v for v in foto.guardiano["incoerenze"]
                    if v.get("riparazione") and not str(v.get("esito_riparazione", "")).startswith("riparata")]
    assert not non_riparate, non_riparate
    secondo = pratica.ricontrolla()
    da_riparare = [v["codice"] for v in secondo["incoerenze"] if v.get("riparazione") and not v.get("avviso")]
    assert not da_riparare, f"la catena non si è chiusa al primo giro: {secondo['incoerenze']}"
    oggi = pratica.orologio.oggi
    aperte = {(s["data"]) for s in foto.scadenze if s["stato"] == "APERTO"}
    for voce in foto.ragionamento.get("conclusioni") or []:
        giorno = termine_certo_dello_studio(voce, oggi)
        if giorno:
            assert giorno in aperte, f"termine certo «{voce['cosa']}» del {giorno} senza scadenza aperta: {foto.scadenze}"
    for udienza in foto.ragionamento.get("udienze") or []:
        from pct.catena.guardiano import iso

        if iso(udienza["data"]) >= oggi.isoformat():
            assert any(a["data"] == iso(udienza["data"]) for a in foto.udienze()), (udienza, foto.agenda)
    from pct.catena.guardiano import automatica, codice_scadenza

    for voce in foto.ragionamento.get("conclusioni") or []:
        giorno = ((voce.get("termine") or {}).get("scadenza_iso") or "")[:10]
        if voce.get("onerato_codice") == "controparte" and giorno:
            altrui = [s for s in foto.aperte() if s["data"] == giorno and automatica(s) and codice_scadenza(s) == voce["codice"]]
            assert not altrui, f"termine della controparte nello scadenziario: {altrui}"


def esegui(pratica: Pratica, passi: tuple[Passo, ...]) -> list[Fotografia]:
    foto = []
    for passo in passi:
        pratica.orologio.al(passo.giorno)
        for nome, righe in passo.documenti:
            pratica.documento(nome, righe)
        fotografia = pratica.leggi()
        catena_chiusa(pratica, fotografia)
        if passo.attese is not None:
            passo.attese(fotografia)
        foto.append(fotografia)
    return foto


def test_ogni_materia_ha_la_sua_pratica_di_prova():
    assert set(MATERIE) <= {p.materia for p in PRATICHE}, set(MATERIE) - {p.materia for p in PRATICHE}


# Il decreto ingiuntivo caricato dalla pagina è riconosciuto dal catalogo (v39-provvedimento-del-giudice,
# 20/11/2026): anche le pratiche monitorie percorrono la catena intera.
_PARAMETRI = [pytest.param(p, id=p.codice) for p in PRATICHE]


@pytest.mark.parametrize("definizione", _PARAMETRI)
def test_catena_della_pratica(studio, definizione):
    app, orologio = studio
    orologio.al(definizione.passi[0].giorno)
    pratica = Pratica(app, orologio, **definizione.fascicolo)
    esegui(pratica, definizione.passi)


def test_fine_pratica_definizione_archiviazione_e_giro_notturno(studio):
    """Dopo la sentenza e l'incasso l'avvocato definisce e archivia: il fascicolo archiviato esce dal giro notturno
    del guardiano, quelli ancora aperti restano controllati (stesso giro del lavoro ``guardiano_catena_notturno``)."""
    from pct.fascicoli import StatoFascicolo
    from tests.catena_collaudo_pratiche import LAVORO
    from web.services.catena_guardiano_runtime import giro

    app, orologio = studio
    orologio.al(LAVORO.passi[0].giorno)
    pratica = Pratica(app, orologio, **{**LAVORO.fascicolo, "rg": "1599", "cliente": "Anna Gialli Bis"})
    esegui(pratica, LAVORO.passi[:1])
    aperta = Pratica(app, orologio, titolo="Rossi / Delta", tipo=LAVORO.fascicolo["tipo"], cliente="Ugo Rossi",
                     controparte="Delta S.p.A.", ufficio="Tribunale di Vicenza", rg="1572")
    with app.app_context():
        fascicoli = app.extensions["core_runtime"]["get_fascicoli"]()
        fascicoli.cambia_stato(pratica.id, StatoFascicolo.DEFINITO, note="sentenza passata in giudicato, credito incassato")
        fascicoli.archivia(pratica.id, crea_zip=False)
    with app.app_context():
        esito = giro(app, origine="notte")
    assert esito["errori"] == 0 and esito["fascicoli"] >= 1, esito
    with app.test_request_context("/"):
        from web.services.catena_guardiano_runtime import registro_corrente

        registro = registro_corrente()
        notte = [r for r in registro.giri(limite=500) if r["origine"] == "notte"]
    controllati = {r["fascicolo_id"] for r in notte}
    assert aperta.id in controllati and pratica.id not in controllati, controllati
