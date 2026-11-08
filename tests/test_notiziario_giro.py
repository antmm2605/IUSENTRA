"""Giro delle Notizie utili, archivio, inoltro alla revisione, pertinenza ai fascicoli e vista della pagina."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import requests

from pct.notiziario import fonti
from pct.notiziario.adattatori import identificativo_notizia
from pct.notiziario.alimentazione import STATO_ACQUISIZIONE, inoltra_alla_revisione
from pct.notiziario.archivio import ArchivioNotiziario
from pct.notiziario.giro import esegui_giro, fonti_scadute
from pct.notiziario.pertinenza import costruisci_indice, fascicoli_pertinenti
from web.services import notiziario_runtime as vista

FIXTURE = Path(__file__).parent / "fixtures" / "notiziario"
_FILE = {
    "gu_serie_generale": "gu_serie_generale.xml", "gu_corte_costituzionale": "gu_corte_costituzionale.xml",
    "eurlex_gu_l": "eurlex_gu_l.xml", "curia": "curia.xml", "cedu_italia": "hudoc_italia.xml",
    "entrate_prassi": "entrate_prassi.xml", "inps_circolari": "inps_circolari.xml",
    "inps_messaggi": "inps_messaggi.xml", "garante_privacy": "garante_privacy.xml",
}
ADESSO = datetime(2026, 11, 8, 10, 0, tzinfo=timezone.utc)


class _Risposta:
    status_code = 200
    headers: dict = {}

    def __init__(self, corpo: bytes):
        self._corpo = corpo

    def iter_content(self, chunk_size: int):
        yield self._corpo


def _rete_registrata(giu: frozenset[str] = frozenset()):
    per_url = {fonti.fonte(fid).url: fid for fid in _FILE}

    def _get(url, **_kwargs):
        fonte_id = per_url[url]
        if fonte_id in giu:
            raise requests.ConnectionError("giù")
        return _Risposta((FIXTURE / _FILE[fonte_id]).read_bytes())

    return _get


def _pagine_istituzionali(monkeypatch, *, giu: frozenset[str] = frozenset()):
    def _raccogli(source_id, **_kwargs):
        if source_id in giu:
            raise ValueError("pagina non leggibile")
        url = f"https://{fonti.fonte(source_id).host_ammessi[0]}/{source_id}"
        return [{
            "id": identificativo_notizia(source_id, url),
            "title": f"Notizia {source_id}",
            "source_url": url,
            "published_at": "2026-11-07",
            "short_summary": "Testo pubblicato.",
        }]

    monkeypatch.setattr("pct.notizie_utili.raccogli_pagina_istituzionale", _raccogli)


def test_giro_completo_con_una_fonte_giu_che_non_ferma_le_altre(tmp_path: Path, monkeypatch):
    _pagine_istituzionali(monkeypatch, giu=frozenset({"cnf"}))
    archivio = ArchivioNotiziario(tmp_path / "notiziario.sqlite")

    esito = esegui_giro(archivio, request_get=_rete_registrata(frozenset({"curia"})), adesso=ADESSO)

    assert esito["fonti_interrogate"] == len(fonti.FONTI)
    assert esito["fonti_non_raggiungibili"] == ["cnf", "curia"]
    assert esito["notizie_nuove"] > 30
    stato = archivio.stato_fonti()
    assert stato["curia"]["ultimo_esito_ok"] is False
    assert stato["curia"]["messaggio"] == "La fonte non è raggiungibile in questo momento."
    assert stato["gu_serie_generale"]["ultimo_esito_ok"] is True
    assert stato["gu_serie_generale"]["ultima_pubblicazione"] == "2026-11-07"


def test_giro_successivo_interroga_solo_le_fonti_scadute_e_non_duplica(tmp_path: Path, monkeypatch):
    _pagine_istituzionali(monkeypatch)
    archivio = ArchivioNotiziario(tmp_path / "notiziario.sqlite")
    esegui_giro(archivio, request_get=_rete_registrata(), adesso=ADESSO)
    totale = len(archivio.elenco())

    subito = esegui_giro(archivio, request_get=_rete_registrata(), adesso=ADESSO + timedelta(minutes=30))
    assert subito["status"] == "nessuna_fonte_scaduta"

    dopo_due_ore = esegui_giro(archivio, request_get=_rete_registrata(), adesso=ADESSO + timedelta(hours=2))
    assert set(dopo_due_ore["esiti"]) == {"gu_serie_generale", "cassazione"}
    assert dopo_due_ore["notizie_nuove"] == 0
    assert len(archivio.elenco()) == totale


def test_fonte_in_errore_si_ritenta_dopo_un_ora_anche_se_la_frequenza_e_piu_lunga():
    stato = {"cedu_italia": {"ultimo_tentativo": "2026-11-08T10:00:00Z", "ultimo_esito_ok": False}}
    scadute = {f.id for f in fonti_scadute(stato, ADESSO + timedelta(minutes=61))}
    assert "cedu_italia" in scadute


class _Repository:
    def __init__(self):
        self.salvati: list[dict] = []
        self.sorgenti = {
            "gazzetta_ufficiale": {"id": 1, "code": "gazzetta_ufficiale"},
            "inps_circolari": {"id": 26, "code": "inps_circolari"},
        }

    def get_source_by_code(self, code):
        return self.sorgenti.get(code)

    def get_raw_document_by_external(self, source_id, external_id):
        return next((r for r in self.salvati if r["source_id"] == source_id and r["external_id"] == external_id), None)

    def save_raw_document(self, payload):
        self.salvati.append(dict(payload))
        return payload


def test_inoltro_alla_revisione_solo_norme_pronunce_prassi_di_fonti_censite_e_una_volta(tmp_path: Path, monkeypatch):
    _pagine_istituzionali(monkeypatch)
    archivio = ArchivioNotiziario(tmp_path / "notiziario.sqlite")
    esegui_giro(archivio, request_get=_rete_registrata(), adesso=ADESSO)
    repository = _Repository()

    inoltrate = inoltra_alla_revisione(archivio, repository)

    assert inoltrate == 5 + 3  # Gazzetta Serie generale + circolari INPS
    assert {r["source_id"] for r in repository.salvati} == {1, 26}
    primo = repository.salvati[0]
    assert primo["fetch_status"] == STATO_ACQUISIZIONE
    assert primo["source_url"].startswith("https://")
    assert primo["published_at"] and primo["raw_text"].startswith(primo["title"])
    assert inoltra_alla_revisione(archivio, repository) == 0
    assert len(repository.salvati) == 8


def _fascicoli():
    return [
        {"id": "F1", "etichetta": "RG 10/2026 - Rossi c. MIM", "titolo": "Rossi c. MIM",
         "oggetto": "Carta del docente ai docenti precari, art. 1 c. 121 L. 107/2015", "tipo": "LAVORO", "area_pratica": ""},
        {"id": "F2", "etichetta": "RG 11/2026 - Bianchi c. Banca", "titolo": "Bianchi c. Banca",
         "oggetto": "Usura bancaria nel contratto di mutuo", "tipo": "CIVILE", "area_pratica": "banca"},
    ]


def test_pertinenza_per_atto_citato_e_per_tema_con_il_motivo():
    indice = costruisci_indice(_fascicoli())
    per_atto = fascicoli_pertinenti(
        {"titolo": "Sentenza n. 1/2026", "sintesi": "", "atti": ["legge:107:2015"], "materia": ""}, indice,
    )
    assert per_atto == [{"id": "F1", "etichetta": "RG 10/2026 - Rossi c. MIM", "motivo": "Il fascicolo RG 10/2026 cita L. 107/2015 nel titolo o nell'oggetto"}]
    per_tema = fascicoli_pertinenti(
        {"titolo": "Usura nei contratti di mutuo bancario", "sintesi": "", "atti": [], "materia": "Banca, finanza e assicurazioni"},
        indice,
    )
    assert [voce["id"] for voce in per_tema] == ["F2"]
    assert per_tema[0]["motivo"].startswith("Stesso tema dell'oggetto: «usura»")


def test_pertinenza_non_basta_una_parola_ne_la_sola_materia():
    indice = costruisci_indice(_fascicoli())
    assert fascicoli_pertinenti(
        {"titolo": "Mutuo agevolato per le imprese agricole", "sintesi": "", "atti": [], "materia": "Diritto civile"}, indice,
    ) == []
    assert fascicoli_pertinenti(
        {"titolo": "Decreto del Ministero sul lavoro", "sintesi": "", "atti": [], "materia": "Lavoro e previdenza"}, indice,
    ) == []


def test_vista_filtri_pagine_pertinenti_e_nuove(tmp_path: Path, monkeypatch):
    _pagine_istituzionali(monkeypatch)
    archivio = ArchivioNotiziario(tmp_path / "notiziario.sqlite")
    esegui_giro(archivio, request_get=_rete_registrata(), adesso=ADESSO)
    fascicoli = _fascicoli() + [{
        "id": "F3", "etichetta": "RG 12/2026 - Verdi c. INPS", "titolo": "Verdi c. INPS",
        "oggetto": "Cessione del quinto della pensione e traslazione del contratto", "tipo": "LAVORO", "area_pratica": "previdenza",
    }]

    def _vista(**argomenti):
        return vista.costruisci_vista(
            archivio, interazioni={}, fascicoli=fascicoli, filtri=vista.filtri_richiesti(argomenti), oggi=date(2026, 11, 8),
        )

    tutte = _vista()
    # i comunicati di servizio della Gazzetta (AIFA, cambi) sono nascosti finché non si chiedono
    assert tutte["total"] + tutte["serviceCount"] == len(archivio.elenco()) and tutte["serviceCount"] > 0
    assert len(tutte["items"]) == vista.PER_PAGINA and tutte["hasMore"] is True
    seconda = _vista(pagina="2")
    assert {v["id"] for v in seconda["items"]}.isdisjoint({v["id"] for v in tutte["items"]})

    prassi = _vista(tipo="prassi", fonte="inps_circolari")
    assert prassi["total"] == 3 and all(v["kindLabel"] == "Prassi e circolari" for v in prassi["items"])

    pertinenti = _vista(pertinenti="1")
    assert pertinenti["total"] >= 1
    cessione = next(v for v in pertinenti["items"] if v["title"] == "Circolare numero 109 del 02-11-2026")
    assert cessione["relatedCases"][0]["id"] == "F3"

    nuove = _vista(nuove="1")
    assert nuove["total"] and all(v["publishedAt"] >= "2026-11-07" for v in nuove["items"])

    materie = {voce["id"]: voce["count"] for voce in tutte["facets"]["matters"]}
    assert materie["Diritto dell’Unione europea"] >= 4
    assert vista.MATERIA_NON_INDICATA in materie
    assert {riga["id"] for riga in tutte["sourceStates"]} == set(fonti.PER_ID)


def test_fascicoli_aperti_esclude_gli_archiviati_e_tiene_tipo_e_oggetto():
    righe = [
        SimpleNamespace(id="A", numero="2026/2", titolo="Rossi", oggetto="Carta docente", tipo=SimpleNamespace(value="LAVORO"),
                        stato="APERTO", numero_rg="3", anno_rg="2025", area_pratica="", codice_oggetto_pst="222050"),
        SimpleNamespace(id="B", numero="2026/1", titolo="Chiuso", oggetto="", tipo="CIVILE", stato="ARCHIVIATO",
                        numero_rg="", anno_rg="", area_pratica=""),
    ]
    assert vista.fascicoli_aperti(righe) == [{
        "id": "A", "etichetta": "RG 3/2025 - Rossi", "titolo": "Rossi", "oggetto": "Carta docente",
        "tipo": "LAVORO", "area_pratica": "", "codice_oggetto_pst": "222050",
    }]


def test_pertinenza_usa_la_descrizione_ufficiale_del_codice_oggetto_pst():
    # «222050» nel catalogo degli XSD PST: «retribuzione», codice padre «Pubblico impiego»
    indice = costruisci_indice([{
        "id": "M1", "etichetta": "Contarino c. Miur", "titolo": "Contarino c. Miur", "oggetto": "222050 - Retribuzione",
        "tipo": "LAVORO", "area_pratica": "", "codice_oggetto_pst": "222050",
    }])
    pertinenti = fascicoli_pertinenti(
        {"titolo": "Retribuzione di risultato nel pubblico impiego", "sintesi": "", "atti": [], "materia": "Lavoro e previdenza"},
        indice,
    )
    assert [voce["id"] for voce in pertinenti] == ["M1"]
    assert "«retribuzione»" in pertinenti[0]["motivo"] and "«impiego»" in pertinenti[0]["motivo"]
