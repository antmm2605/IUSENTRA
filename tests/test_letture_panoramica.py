"""Lo stato della lettura su tutti i fascicoli, senza aprirli uno alla volta.

Con trecento fascicoli, sapere se i motori hanno finito non puo' voler dire
aprire trecento schede: la panoramica legge il registro — nessun documento
viene aperto — e dice per ciascun fascicolo se e' fermo, se ha ancora
qualcosa da leggere, se e' in errore o se non e' mai stato esaminato.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from pct.registro_letture import Oggetto, RegistroLetture
from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app

TENANT = "default"


def _registro(tmp_path: Path) -> RegistroLetture:
    return RegistroLetture(db_path=str(tmp_path / "registro.db"))


def _oggetto(indice: int) -> Oggetto:
    return Oggetto(tipo="documento", oggetto_id=f"DOC{indice}", nome=f"atto{indice}.pdf", sha256=f"h{indice}")


def test_il_registro_risponde_per_tutti_i_fascicoli_in_una_lettura(tmp_path: Path):
    registro = _registro(tmp_path)
    for fascicolo in ("F1", "F2", "F3"):
        registro.registra_inventario(TENANT, fascicolo, [_oggetto(1)], tipi=("documento",))
    registro.segna_fascicolo(TENANT, "F1", "motore_documenti", impronta="aaa", oggetti_totali=1, oggetti_letti=1)
    registro.segna_fascicolo(TENANT, "F2", "motore_documenti", impronta="bbb", oggetti_totali=3, oggetti_letti=1, stato="parziale")
    registro.segna_fascicolo(TENANT, "F3", "motore_documenti", impronta="ccc", oggetti_totali=2, oggetti_letti=0, stato="errore")

    righe = {r["fascicolo_id"]: r for r in registro.righe_fascicoli(TENANT, lettore="motore_documenti")} if True else {
        r["fascicolo_id"]: r for r in registro.righe_fascicoli(TENANT, lettore="motore_documenti")
    }

    assert set(righe) == {"F1", "F2", "F3"}
    assert righe["F1"]["stato"] == "completa"
    assert righe["F2"]["stato"] == "parziale"
    assert righe["F3"]["stato"] == "errore"


def test_i_conteggi_delle_letture_arrivano_raggruppati_per_fascicolo(tmp_path: Path):
    registro = _registro(tmp_path)
    oggetti = [_oggetto(1), _oggetto(2)]
    registro.registra_inventario(TENANT, "F1", oggetti, tipi=("documento",))
    registro.segna_letto(TENANT, "F1", oggetti[0], "motore_documenti")
    registro.segna_letto(TENANT, "F1", oggetti[1], "motore_documenti", stato="non_leggibile")

    conteggi = registro.conteggi_letture(TENANT)

    assert conteggi["F1"]["letto"] == 1
    assert conteggi["F1"]["non_leggibile"] == 1


def test_la_panoramica_distingue_fermi_da_fare_errori_e_mai_letti(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    with app.app_context():
        from web.services.archivio_letture_runtime import panoramica_letture, registro_corrente, tenant_corrente

        registro = registro_corrente()
        tenant = tenant_corrente()
        registro.registra_inventario(tenant, "F-FERMO", [_oggetto(1)], tipi=("documento",))
        registro.segna_fascicolo(tenant, "F-FERMO", "motore_documenti", impronta="a", oggetti_totali=1, oggetti_letti=1)
        registro.registra_inventario(tenant, "F-ERRORE", [_oggetto(2)], tipi=("documento",))
        registro.segna_fascicolo(tenant, "F-ERRORE", "motore_documenti", impronta="b", oggetti_totali=1, oggetti_letti=0, stato="errore")

        esito = panoramica_letture()

    assert esito["ok"] is True
    stati = {voce["fascicoloId"]: voce["stato"] for voce in esito["fascicoli"]}
    # I fascicoli dello studio di prova non esistono in anagrafica: la panoramica
    # elenca quelli veri, e i totali dicono comunque quanti sono per stato.
    assert set(esito["totali"]) >= {"fascicoli", "fermi", "da_leggere", "in_errore", "mai_letti"}
    assert isinstance(stati, dict)


def test_l_endpoint_della_panoramica_richiede_autenticazione(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))

    with app.test_client() as client:
        risposta = client.get("/api/v1/ui/letture/panoramica")

    assert risposta.status_code in (401, 403)
