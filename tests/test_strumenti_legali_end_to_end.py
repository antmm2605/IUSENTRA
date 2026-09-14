"""Prova di funzionamento dell'intera pagina Strumenti forensi.

Non e' un test di unita': apre l'applicazione, esegue il login e chiama i due
endpoint che la pagina usa davvero — il catalogo con gli schemi dei moduli e il
calcolo — per ognuno dei 73 strumenti. E' la verifica che, aperta la pagina e
premuto «Calcola», ogni strumento risponde con un risultato invece che con un
errore.

Serve perche' i test dei singoli calcolatori non vedono tre cose che rompono la
pagina e non il dominio: uno strumento non collegato all'endpoint, un campo
dichiarato nello schema che il calcolatore non legge, e — il caso trovato il
14/09/2026 — un menu a tendina che offre valori che il calcolatore rifiuta,
lasciando lo strumento inutilizzabile nonostante il codice di dominio sia
corretto.
"""

from __future__ import annotations

import pytest

from tests.dati_strumenti_legali import PAYLOAD_STRUMENTI


def _client(tmp_path):
    from tests.test_web_bootstrap import _cfg_web, _seed_tenant_admin, _write_studio_config
    from web.app import create_app

    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    studio, admin = _seed_tenant_admin(app)
    client = app.test_client()
    client.get("/login")
    client.post(
        "/login",
        data={"username": admin.username, "password": "PasswordSicura!123", "studio_slug": studio.slug},
    )
    return client


@pytest.fixture(scope="module")
def catalogo():
    from pct.strumenti_legali import GestioneStrumentiLegali

    # Gli strumenti con un componente React dedicato (riconoscimento del testo)
    # non sono moduli di calcolo: non hanno schema, metodo ne' dati di prova.
    return [voce["id"] for voce in GestioneStrumentiLegali().catalogo_moduli() if not voce.get("componente")]


def test_ogni_strumento_del_catalogo_ha_dati_di_prova(catalogo):
    """Uno strumento nuovo senza dati di prova non passa in produzione."""
    mancanti = sorted(set(catalogo) - set(PAYLOAD_STRUMENTI))
    assert not mancanti, f"strumenti senza dati di prova: {mancanti}"
    orfani = sorted(set(PAYLOAD_STRUMENTI) - set(catalogo))
    assert not orfani, f"dati di prova senza strumento nel catalogo: {orfani}"


def test_ogni_strumento_e_collegato_all_endpoint_di_calcolo(catalogo):
    from pct.calcolatori.schema import SCHEMI_CALCOLATORI
    from pct.strumenti_legali import GestioneStrumentiLegali
    from web.blueprints.strumenti_legali import TOOL_METHODS

    gestore = GestioneStrumentiLegali()
    for tool in catalogo:
        assert tool in SCHEMI_CALCOLATORI, f"{tool}: nessuno schema del modulo"
        assert tool in TOOL_METHODS, f"{tool}: non collegato all'endpoint"
        assert hasattr(gestore, TOOL_METHODS[tool]), f"{tool}: metodo {TOOL_METHODS[tool]} assente"


def test_ogni_campo_dichiarato_ha_un_valore_iniziale(catalogo):
    """La pagina precompila dal dominio: un campo senza default esce vuoto."""
    from pct.calcolatori.schema import SCHEMI_CALCOLATORI
    from pct.strumenti_legali import GestioneStrumentiLegali

    stato = GestioneStrumentiLegali().build_form_state({})
    for tool in catalogo:
        for campo in SCHEMI_CALCOLATORI[tool]["campi"]:
            assert campo["name"] in stato, f"{tool}: campo {campo['name']} senza valore iniziale"


def test_ogni_opzione_offerta_e_accettata_dal_calcolatore(catalogo):
    """Un menu a tendina non deve offrire scelte che il calcolatore rifiuta.

    E' il difetto trovato su «Maggior danno da svalutazione»: lo schema React
    dichiarava «rivalutato» e «nominale», il calcolatore accettava soltanto
    «rivalutato_annuale», «semisomma» e «originario». Ogni scelta possibile nella
    pagina falliva.
    """
    from pct.calcolatori.schema import SCHEMI_CALCOLATORI
    from pct.strumenti_legali import GestioneStrumentiLegali
    from web.blueprints.strumenti_legali import TOOL_METHODS

    gestore = GestioneStrumentiLegali()
    rifiutate: list[str] = []
    for tool in catalogo:
        base = PAYLOAD_STRUMENTI[tool]
        for campo in SCHEMI_CALCOLATORI[tool]["campi"]:
            for opzione in campo.get("options") or []:
                dati = {**base, campo["name"]: opzione["value"]}
                try:
                    getattr(gestore, TOOL_METHODS[tool])(dati)
                except ValueError as exc:
                    # Un dato incoerente con l'opzione e' legittimo; un valore
                    # «non riconosciuto» significa che lo schema e il calcolatore
                    # parlano due lingue diverse.
                    if "riconosciut" in str(exc).lower():
                        rifiutate.append(f"{tool}.{campo['name']} = «{opzione['value']}»: {exc}")
                except Exception:
                    pass
    assert not rifiutate, "opzioni offerte dalla pagina e rifiutate dal calcolatore:\n" + "\n".join(rifiutate)


def test_il_catalogo_react_espone_tutti_gli_strumenti(tmp_path, catalogo):
    client = _client(tmp_path)
    payload = client.get("/api/v1/ui/strumenti-legali").get_json()

    dedicati = [voce for voce in payload["strumenti"] if voce.get("componente")]
    moduli = [voce for voce in payload["strumenti"] if not voce.get("componente")]
    assert payload["totale"] == len(catalogo) + len(dedicati)
    assert payload["totale_in_react"] == payload["totale"], "qualche strumento non e' compilabile in pagina"
    esposti = {voce["id"] for voce in moduli}
    assert esposti == set(catalogo)
    for voce in moduli:
        assert voce["campi"], f"{voce['id']}: nessun campo nel modulo"
        assert voce["title"] and voce["categoria"], f"{voce['id']}: voce di catalogo incompleta"
    # La utility di riconoscimento del testo e' una pagina propria, nella categoria Utility.
    ocr = next(voce for voce in dedicati if voce["id"] == "ocr_documento_word")
    assert ocr["componente"] == "ocr-documento" and ocr["categoria"] == "Utility" and ocr["reso_in_react"]
    assert "Utility" in payload["categorie"]


@pytest.mark.parametrize("tool", sorted(PAYLOAD_STRUMENTI))
def test_lo_strumento_calcola_dall_endpoint_della_pagina(tmp_path, tool):
    """Aperta la pagina e premuto «Calcola», lo strumento risponde con un risultato."""
    client = _client(tmp_path)
    risposta = client.post(
        "/api/v1/ui/strumenti-legali/calcola",
        json={"tool": tool, "dati": PAYLOAD_STRUMENTI[tool]},
    )
    assert risposta.status_code == 200
    payload = risposta.get_json()
    assert payload["ok"] is True, f"{tool}: {payload.get('errore')}"
    assert payload["tool"] == tool
    risultato = payload["result"]
    assert isinstance(risultato, dict) and risultato, f"{tool}: risultato vuoto"
    # Ogni strumento deve dire su cosa si fonda: fonti, note o riferimento.
    assert any(
        chiave in risultato for chiave in ("sources", "notes", "warnings", "riferimento_normativo", "fonti")
    ), f"{tool}: risultato senza fonti ne' note"


def test_uno_strumento_inesistente_non_apre_un_errore_interno(tmp_path):
    client = _client(tmp_path)
    payload = client.post(
        "/api/v1/ui/strumenti-legali/calcola", json={"tool": "non_esiste", "dati": {}}
    ).get_json()
    assert payload["ok"] is False
    assert "non disponibile" in payload["errore"].lower()


def test_i_dati_mancanti_producono_un_messaggio_in_italiano(tmp_path):
    """Modulo vuoto: l'avvocato deve leggere cosa manca, non «errore interno»."""
    client = _client(tmp_path)
    payload = client.post(
        "/api/v1/ui/strumenti-legali/calcola", json={"tool": "valore_causa", "dati": {}}
    ).get_json()
    assert payload["ok"] is False
    assert "importo" in payload["errore"].lower()
