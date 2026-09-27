"""Migrazione React 2.413.0: checklist degli atti, percorso guidato, consultazione dai portali.

- `/checklist` e `/checklist/<id>`: catalogo e scheda dell'atto (documenti,
  controlli bloccanti, canale) nella shell React;
- `/fascicoli/<id>/wizard/<modello>[/step/<n>|/completa]`: percorso guidato di
  raccolta dei documenti, con caricamento dalla via comune del fascicolo e
  passaggio alla pagina React del deposito;
- `/polisWeb/documenti`, `/pdp/documenti` e `/polisWeb/fascicolo-wizard`
  portano all'acquisizione guidata React del portale (il PDP non ha servizi per
  i gestionali: art. 111-bis c.p.p., D.M. 217/2023).
"""

from __future__ import annotations

import io

from tests.test_revisione_2410_sicurezza import _app as _app_sessione
from tests.test_topbar_operational_api import _login

HTML = {"Accept": "text/html"}


def test_checklist_e_percorso_guidato_nella_shell_react():
    from web.blueprints import react_shell
    from web.bootstrap.react_route_gate import _excluded, _is_react_route

    for percorso in (
        "/checklist",
        "/checklist/decreto_ingiuntivo",
        "/fascicoli/F1/wizard/decreto_ingiuntivo",
        "/fascicoli/F1/wizard/decreto_ingiuntivo/step/2",
        "/fascicoli/F1/wizard/decreto_ingiuntivo/completa",
    ):
        assert _is_react_route(percorso) and not _excluded(percorso), percorso
        assert react_shell._route_component_key(percorso) == "src/components/ChecklistAttiPage.tsx", percorso
    # La generazione dell'indice storica (POST) e le altre azioni del fascicolo restano del server.
    assert _excluded("/fascicoli/F1/wizard/decreto_ingiuntivo/genera-indice")


def test_consultazione_dai_portali_porta_all_acquisizione_guidata(tmp_path):
    app = _app_sessione(tmp_path)
    with app.test_client() as client:
        _login(client)
        casi = {
            "/polisWeb/documenti?codice_ufficio=0580010&numero_rg=123&anno_rg=2026": "/portali/pst/acquisizione?ufficio_codice=0580010&numero=123&anno=2026",
            "/pdp/documenti?codice_ufficio=X1&numero_rg=9&anno_rg=2025": "/portali/pdp/acquisizione?ufficio_codice=X1&numero=9&anno=2025",
            "/polisWeb/fascicolo-wizard?codice_ufficio=0580010&numero_rg=1&anno_rg=2024&id_fasc=F7": "/portali/pst/acquisizione?ufficio_codice=0580010&numero=1&anno=2024&id_fasc=F7",
        }
        for origine, destinazione in casi.items():
            risposta = client.get(origine, headers=HTML)
            assert risposta.status_code == 302, origine
            assert risposta.headers["Location"].endswith(destinazione), (origine, risposta.headers["Location"])


def test_api_catalogo_e_scheda_checklist(tmp_path):
    from pct.checklist_atti import TUTTI_I_TEMPLATE

    app = _app_sessione(tmp_path)
    modello = TUTTI_I_TEMPLATE[0]
    with app.test_client() as client:
        _login(client)
        catalogo = client.get("/api/v1/ui/checklist").get_json()
        assert catalogo["ok"] is True and catalogo["totals"]["templates"] == len(TUTTI_I_TEMPLATE)
        filtrato = client.get("/api/v1/ui/checklist", query_string={"area": modello.area}).get_json()
        assert all(area["name"] == modello.area for area in filtrato["catalog"])
        scheda = client.get(f"/api/v1/ui/checklist/{modello.id}", query_string={"parte": "Rossi Mario", "rg": "123/2026"}).get_json()
        assert scheda["item"]["documents"][0]["fileName"] == modello.documenti[0].nome_file
        assert "Rossi_Mario" in scheda["item"]["folderName"] or "{parte}" not in modello.nome_cartella
        assert client.get("/api/v1/ui/checklist/inesistente").status_code == 404


def test_percorso_guidato_carica_salta_e_indice(tmp_path):
    from pct.checklist_atti import TUTTI_I_TEMPLATE
    from pct.fascicoli import TipoFascicolo
    from web.helpers import get_fascicoli

    modello = next(t for t in TUTTI_I_TEMPLATE if any(not d.obbligatorio for d in t.documenti) and any(d.obbligatorio for d in t.documenti))
    obbligatorio = next(d for d in modello.documenti if d.obbligatorio)
    facoltativo = next(d for d in modello.documenti if not d.obbligatorio)
    app = _app_sessione(tmp_path)
    with app.app_context():
        fascicolo = get_fascicoli().nuovo("Rossi c. Bianchi", TipoFascicolo.CIVILE, nome_cliente="Rossi", controparte="Bianchi")
    base = f"/api/v1/ui/checklist/percorso/{fascicolo.id}/{modello.id}"
    with app.test_client() as client:
        _login(client)
        for pagina in (f"/fascicoli/{fascicolo.id}/wizard/{modello.id}/step/1", f"/fascicoli/{fascicolo.id}/wizard/{modello.id}/completa", "/checklist"):
            risposta = client.get(pagina, headers=HTML)
            assert risposta.status_code == 200 and "react-shell-document" in risposta.get_data(as_text=True), pagina
        percorso = client.get(base).get_json()
        assert percorso["ok"] is True and percorso["complete"] is False
        passo = next(p for p in percorso["steps"] if p["number"] == obbligatorio.numero)
        assert passo["status"] == "pending" and passo["uploadNote"] == f"[wizard:{modello.id}:step{obbligatorio.numero}]"

        # Caricamento dalla via comune del fascicolo, con il nome e la nota del passo.
        caricato = client.post(
            percorso["matter"]["uploadAction"],
            data={"file": (io.BytesIO(b"contenuto del documento"), f"{passo['uploadName']}.txt"), "note": passo["uploadNote"]},
            content_type="multipart/form-data",
            headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"},
        )
        assert caricato.status_code == 200, caricato.get_data(as_text=True)[:300]
        dopo = client.get(base).get_json()
        assert next(p for p in dopo["steps"] if p["number"] == obbligatorio.numero)["status"] == "done"

        # Un obbligatorio non si salta; un facoltativo sì.
        assert client.post(f"{base}/salta", json={"numero": obbligatorio.numero}).status_code == 409
        saltato = client.post(f"{base}/salta", json={"numero": facoltativo.numero}).get_json()
        assert next(p for p in saltato["steps"] if p["number"] == facoltativo.numero)["status"] == "skipped"

        indice = client.post(f"{base}/indice", json={}).get_json()
        assert indice["ok"] is True and indice["fileName"] == f"00_Indice_{modello.id}.txt"
        assert "[non allegato]" in indice["text"] and obbligatorio.descrizione in indice["text"]
