"""Archivio completo della Corte costituzionale (open data) nel corpus giurisprudenziale di Lex.

Fonte: https://dati.cortecostituzionale.it — dataset «Pronunce» (JSON) e «Massime» (XML), licenza
Creative Commons BY-SA 3.0 (attribuzione: Corte costituzionale). I file sono zip di zip annuali:

- ``P_json<periodo>.zip`` → ``Cc_Opendata_Pronunce_AAAA_json.zip`` → ``Cc_Opendata_Pronunce_AAAA.json``
  (cp1252, chiave ``elenco_pronunce``);
- ``CC_OpenMassime_<periodo>.zip`` → ``Cc_OpenData_Massime_AAAA.zip`` → ``Cc_OpenData_Massime_AAAA.xml``
  (UTF-8, ``<pronuncia><pronuncia_testata>…</pronuncia_testata><massime><massima>…``).

Pronunce e massime si uniscono per (anno, numero): la Consulta numera sentenze e ordinanze in un'unica
serie annuale. Ogni pronuncia diventa una riga di ``sentenze`` nel corpus SQLite FTS5
(:class:`pct.giurisprudenza_corpus.GestioneCorpusGiurisprudenza`) con massime ufficiali, dispositivo,
testo integrale, ECLI e scheda ufficiale ``https://www.cortecostituzionale.it/scheda-pronuncia/AAAA/N``.
La scrittura e' a blocchi (una transazione per blocco) e idempotente: chiave ECLI, righe invariate saltate.
"""

from __future__ import annotations

import hashlib
import html
import io
import json
import re
import time
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator

FONTE_CODICE = "corte_costituzionale"
ORGANO = "Corte costituzionale"
URL_DATI = "https://dati.cortecostituzionale.it/opendata/distribuzione"
URL_SCHEDA = "https://www.cortecostituzionale.it/scheda-pronuncia/{anno}/{numero}"
PERIODI = ("1956_1980", "1981_2000", "2001_oggi")
LICENZA = "CC BY-SA 3.0 — dati open della Corte costituzionale (dati.cortecostituzionale.it)"
BLOCCO_PREDEFINITO = 500
IMPORT_COMPLETO = "cortecost_opendata:completo"
IMPORT_PARZIALE = "cortecost_opendata:parziale"

TIPI_PRONUNCIA = {"S": "sentenza", "O": "ordinanza", "D": "decreto"}

FONTE_PAYLOAD = {
    "codice": FONTE_CODICE,
    "nome": ORGANO,
    "tipo_fonte": "ufficiale",
    "ente": ORGANO,
    "url_home": "https://www.cortecostituzionale.it/",
    "url_ricerca": "https://dati.cortecostituzionale.it/Scarica_i_dati/Scarica_i_dati",
    "paese": "IT",
    "note": f"Archivio completo delle pronunce e delle massime ufficiali. Licenza {LICENZA}.",
}


def url_pronunce(periodo: str) -> str:
    return f"{URL_DATI}/pronunce/P_json{periodo}.zip"


def url_massime(periodo: str) -> str:
    return f"{URL_DATI}/CC_OpenMassime_{periodo}.zip"


def nome_file_pronunce(periodo: str) -> str:
    return f"P_json{periodo}.zip"


def nome_file_massime(periodo: str) -> str:
    return f"CC_OpenMassime_{periodo}.zip"


# ---------------------------------------------------------------------------
# Pulizia del testo
# ---------------------------------------------------------------------------

_SPAZI_RIGA = re.compile(r"[ \t ]+")
_RIGHE_VUOTE = re.compile(r"\n{3,}")
_APERTURA_DISPOSITIVO = re.compile(r"^\s*per\s+questi\s+motivi\s*[,:]?\s*la\s+corte\s+costituzionale\s*[,:]?\s*", re.IGNORECASE)
_CHIUSURA_DISPOSITIVO = re.compile(r"\s*(?:Cos[iì]\s+deciso\s+in\s+Roma|F\.to:).*$", re.IGNORECASE | re.DOTALL)


def pulisci_testo(value: Any) -> str:
    """Testo leggibile: ``&#13;`` e ``\\r`` diventano a capo, entita' HTML decodificate, spazi compattati."""

    text = str(value or "")
    if not text:
        return ""
    text = text.replace("&#13;", "\n").replace("\r\n", "\n").replace("\r", "\n")
    text = unicodedata.normalize("NFC", html.unescape(text))
    righe = [_SPAZI_RIGA.sub(" ", riga).strip() for riga in text.split("\n")]
    return _RIGHE_VUOTE.sub("\n\n", "\n".join(righe)).strip()


def nucleo_dispositivo(dispositivo: Any) -> str:
    """Il dispositivo senza la formula d'apertura e senza luogo, data e firme."""

    text = " ".join(pulisci_testo(dispositivo).split())
    text = _APERTURA_DISPOSITIVO.sub("", text)
    text = _CHIUSURA_DISPOSITIVO.sub("", text)
    return text.strip()


def data_iso(value: Any) -> str:
    text = str(value or "").strip()
    match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", text)
    if match:
        giorno, mese, anno = (int(part) for part in match.groups())
        try:
            return date(anno, mese, giorno).isoformat()
        except ValueError:
            return ""
    if re.match(r"^\d{4}-\d{2}-\d{2}", text):
        return text[:10]
    return ""


def _intero(value: Any) -> int:
    try:
        return int(str(value or "").strip())
    except ValueError:
        return 0


# ---------------------------------------------------------------------------
# Lettura degli zip (zip di zip annuali, oppure cartella/file gia' estratti)
# ---------------------------------------------------------------------------

_ANNO_NEL_NOME = re.compile(r"(?<!\d)(1[89]\d{2}|20\d{2})(?!\d)")


def _anno_dal_nome(nome: str) -> int:
    trovati = _ANNO_NEL_NOME.findall(Path(nome).name)
    return int(trovati[-1]) if trovati else 0


def _file_annuali(percorso: str | Path, estensione: str, dal_anno: int = 0) -> Iterator[tuple[str, bytes]]:
    """(nome, contenuto) dei file annuali .json/.xml dentro uno zip di zip, uno zip o una cartella."""

    path = Path(percorso)
    if path.is_dir():
        for figlio in sorted(path.iterdir()):
            if figlio.suffix.lower() in {estensione, ".zip"}:
                yield from _file_annuali(figlio, estensione, dal_anno)
        return
    if path.suffix.lower() == estensione:
        if not dal_anno or _anno_dal_nome(path.name) >= dal_anno or not _anno_dal_nome(path.name):
            yield path.name, path.read_bytes()
        return
    with zipfile.ZipFile(path) as archivio:
        yield from _da_zip(archivio, estensione, dal_anno)


def _da_zip(archivio: zipfile.ZipFile, estensione: str, dal_anno: int) -> Iterator[tuple[str, bytes]]:
    for nome in sorted(archivio.namelist()):
        anno = _anno_dal_nome(nome)
        if dal_anno and anno and anno < dal_anno:
            continue
        minuscolo = nome.lower()
        if minuscolo.endswith(estensione):
            yield nome, archivio.read(nome)
        elif minuscolo.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(archivio.read(nome))) as interno:
                yield from _da_zip(interno, estensione, dal_anno)


def leggi_pronunce(percorso: str | Path, *, dal_anno: int = 0) -> Iterator[dict[str, Any]]:
    for nome, contenuto in _file_annuali(percorso, ".json", dal_anno):
        try:
            testo = contenuto.decode("cp1252")
        except UnicodeDecodeError:
            testo = contenuto.decode("utf-8", errors="replace")
        payload = json.loads(testo)
        for riga in list(payload.get("elenco_pronunce") or []):
            if dal_anno and _intero(riga.get("anno_pronuncia")) < dal_anno:
                continue
            yield dict(riga)


def _testo_xml(elemento: ET.Element | None, tag: str) -> str:
    if elemento is None:
        return ""
    figlio = elemento.find(tag)
    return (figlio.text or "").strip() if figlio is not None and figlio.text else ""


def leggi_massime(percorso: str | Path, *, dal_anno: int = 0) -> dict[tuple[int, int], dict[str, Any]]:
    """{(anno, numero): {"tipologia_giudizio": ..., "massime": [{numero, titolo, testo}, ...]}}."""

    out: dict[tuple[int, int], dict[str, Any]] = {}
    for _nome, contenuto in _file_annuali(percorso, ".xml", dal_anno):
        radice = ET.fromstring(contenuto)
        for pronuncia in radice.iter("pronuncia"):
            testata = pronuncia.find("pronuncia_testata")
            anno = _intero(_testo_xml(testata, "anno_pronuncia"))
            numero = _intero(_testo_xml(testata, "numero_pronuncia"))
            if not anno or not numero or (dal_anno and anno < dal_anno):
                continue
            voce = out.setdefault((anno, numero), {"tipologia_giudizio": "", "massime": []})
            voce["tipologia_giudizio"] = voce["tipologia_giudizio"] or _testo_xml(testata, "tipologia_giudizio")
            contenitore = pronuncia.find("massime")
            for massima in list(contenitore) if contenitore is not None else []:
                testo = pulisci_testo(_testo_xml(massima, "testo"))
                if not testo:
                    continue
                voce["massime"].append(
                    {
                        "numero": _testo_xml(massima, "numero"),
                        "titolo": pulisci_testo(_testo_xml(massima, "titolo")),
                        "testo": testo,
                    }
                )
    return out


# ---------------------------------------------------------------------------
# Riga del corpus
# ---------------------------------------------------------------------------


def _titolo_giudizio(value: str) -> str:
    text = " ".join(str(value or "").split())
    return text[:1].upper() + text[1:].lower() if text.isupper() else text


def componi_record(pronuncia: dict[str, Any], massime: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Payload per ``GestioneCorpusGiurisprudenza.salva_sentenze_blocco`` (None se mancano gli estremi)."""

    anno = _intero(pronuncia.get("anno_pronuncia"))
    numero = _intero(pronuncia.get("numero_pronuncia"))
    if not anno or not numero:
        return None
    tipo = TIPI_PRONUNCIA.get(str(pronuncia.get("tipologia_pronuncia") or "").strip().upper(), "provvedimento")
    etichetta = tipo if tipo != "provvedimento" else "pronuncia"
    ecli = " ".join(str(pronuncia.get("ecli") or "").split()) or f"ECLI:IT:COST:{anno}:{numero}"
    info = massime or {}
    voci_massime = list(info.get("massime") or [])
    tipologia_giudizio = _titolo_giudizio(info.get("tipologia_giudizio") or "")
    titoli = [voce["titolo"] for voce in voci_massime if voce.get("titolo")]
    epigrafe = pulisci_testo(pronuncia.get("epigrafe"))
    testo = pulisci_testo(pronuncia.get("testo"))
    dispositivo = pulisci_testo(pronuncia.get("dispositivo"))
    dispositivo_breve = nucleo_dispositivo(dispositivo) or " ".join(dispositivo.split())
    massima_ufficiale = "\n\n".join(voce["testo"] for voce in voci_massime)
    testo_integrale = "\n\n".join(parte for parte in (epigrafe, testo, dispositivo) if parte)
    url = URL_SCHEDA.format(anno=anno, numero=numero)
    collegio = " ".join(pulisci_testo(pronuncia.get("collegio")).split())
    collegio = re.sub(r"^composta\s+da\s*:\s*", "", collegio, flags=re.IGNORECASE)
    record = {
        "fonte": FONTE_PAYLOAD,
        "uuid_interno": ecli,
        "ecli": ecli,
        "organo_giudicante": ORGANO,
        "tipo_provvedimento": tipo,
        "numero_sentenza": str(numero),
        "anno_sentenza": anno,
        "relatore": " ".join(str(pronuncia.get("relatore_pronuncia") or pronuncia.get("redattore_pronuncia") or "").split()),
        "presidente": " ".join(str(pronuncia.get("presidente") or "").split()),
        "collegio": collegio,
        "data_decisione": data_iso(pronuncia.get("data_decisione")),
        "data_deposito": data_iso(pronuncia.get("data_deposito")),
        "grado_giudizio": "Corte costituzionale",
        "rito": tipologia_giudizio,
        "titolo": f"{ORGANO}, {etichetta} n. {numero}/{anno}",
        "oggetto": tipologia_giudizio or " | ".join(titoli),
        "abstract": " | ".join(titoli),
        "principio_sintetico": dispositivo_breve,
        "massima_ufficiale": massima_ufficiale,
        "testo_integrale": testo_integrale,
        "esito": dispositivo_breve,
        "stato_verifica": "verificata",
        "fonte_ufficiale_confermata": True,
        "testo_integrale_presente": bool(testo_integrale),
        "url_pagina_ufficiale": url,
        "url_html_ufficiale": url,
        "massime": [
            {
                "testo": voce["testo"],
                "sintetica": voce.get("titolo") or "",
                "ufficiale": True,
                "fonte_massima": ORGANO,
                "numero_massima": voce.get("numero") or "",
                "anno_massima": anno,
                "stato_verifica": "verificata",
                "principale": indice == 0,
            }
            for indice, voce in enumerate(voci_massime)
        ],
        "documenti": [
            {
                "tipo_documento": "scheda",
                "titolo": "Scheda ufficiale della pronuncia",
                "url_origine": url,
                "mime_type": "text/html",
                "ufficiale": True,
                "valido": True,
            }
        ],
    }
    impronta = json.dumps(
        {k: record[k] for k in ("ecli", "tipo_provvedimento", "titolo", "oggetto", "abstract", "massima_ufficiale",
                                "testo_integrale", "relatore", "presidente", "collegio", "data_decisione",
                                "data_deposito", "url_pagina_ufficiale")},
        ensure_ascii=False,
        sort_keys=True,
    )
    record["hash_contenuto"] = "cc1:" + hashlib.sha256(impronta.encode("utf-8")).hexdigest()
    return record


# ---------------------------------------------------------------------------
# Download (solo su richiesta)
# ---------------------------------------------------------------------------


def scarica(
    cartella: str | Path,
    periodi: Iterable[str] = PERIODI,
    *,
    massime: bool = True,
    timeout: int = 300,
    getter: Callable[..., Any] | None = None,
) -> list[Path]:
    """Scarica gli zip ufficiali nella cartella (scrittura atomica). TLS sempre verificato."""

    if getter is None:
        import requests

        getter = requests.get
    destinazione = Path(cartella)
    destinazione.mkdir(parents=True, exist_ok=True)
    scaricati: list[Path] = []
    for periodo in periodi:
        coppie = [(url_pronunce(periodo), nome_file_pronunce(periodo))]
        if massime:
            coppie.append((url_massime(periodo), nome_file_massime(periodo)))
        for url, nome in coppie:
            risposta = getter(url, timeout=timeout, stream=True, headers={"User-Agent": "IUSENTRA-Lex/1.0 (open data)"})
            risposta.raise_for_status()
            finale = destinazione / nome
            temporaneo = finale.with_suffix(".zip.part")
            with open(temporaneo, "wb") as handle:
                for pezzo in risposta.iter_content(chunk_size=1 << 20):
                    if pezzo:
                        handle.write(pezzo)
            if not zipfile.is_zipfile(temporaneo):
                temporaneo.unlink(missing_ok=True)
                raise ValueError(f"Il file scaricato da {url} non e' uno zip valido")
            temporaneo.replace(finale)
            scaricati.append(finale)
    return scaricati


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------


@dataclass
class EsitoImport:
    pronunce_lette: int = 0
    pronunce_scartate: int = 0
    con_massime: int = 0
    massime: int = 0
    inserite: int = 0
    aggiornate: int = 0
    invariate: int = 0
    secondi: float = 0.0
    db: list[str] = field(default_factory=list)
    dimensione_db_mb: dict[str, float] = field(default_factory=dict)
    file: list[str] = field(default_factory=list)
    dry_run: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def file_periodo(cartella: str | Path, periodo: str) -> tuple[Path | None, Path | None]:
    base = Path(cartella)
    pronunce = base / nome_file_pronunce(periodo)
    massime = base / nome_file_massime(periodo)
    return (pronunce if pronunce.exists() else None, massime if massime.exists() else None)


def record_da_file(
    coppie: Iterable[tuple[str | Path, str | Path | None]],
    *,
    dal_anno: int = 0,
    esito: EsitoImport | None = None,
) -> Iterator[dict[str, Any]]:
    """Record del corpus da coppie (zip pronunce, zip massime|None)."""

    esito = esito or EsitoImport()
    for pronunce_path, massime_path in coppie:
        esito.file.append(str(pronunce_path))
        indice = leggi_massime(massime_path, dal_anno=dal_anno) if massime_path else {}
        if massime_path:
            esito.file.append(str(massime_path))
        for pronuncia in leggi_pronunce(pronunce_path, dal_anno=dal_anno):
            esito.pronunce_lette += 1
            chiave = (_intero(pronuncia.get("anno_pronuncia")), _intero(pronuncia.get("numero_pronuncia")))
            record = componi_record(pronuncia, indice.get(chiave))
            if record is None:
                esito.pronunce_scartate += 1
                continue
            if record["massime"]:
                esito.con_massime += 1
                esito.massime += len(record["massime"])
            yield record


def importa(
    coppie: Iterable[tuple[str | Path, str | Path | None]],
    db_paths: Iterable[str | Path],
    *,
    dal_anno: int = 0,
    dry_run: bool = False,
    blocco: int = BLOCCO_PREDEFINITO,
    progresso: Callable[[str], None] | None = None,
    completo: bool = False,
) -> EsitoImport:
    """Legge una volta i file e scrive i record a blocchi in ogni corpus indicato.

    Con ``completo`` (tutti i periodi, nessun limite di anno) a fine lavoro ogni corpus registra
    l'import completo in ``importazioni_giurisprudenza``: e' il segno che il deploy controlla.
    """

    from pct.giurisprudenza_corpus import GestioneCorpusGiurisprudenza

    inizio = time.monotonic()
    esito = EsitoImport(dry_run=dry_run)
    gestori = [] if dry_run else [GestioneCorpusGiurisprudenza(str(path)) for path in db_paths]
    esito.db = [str(path) for path in db_paths]
    buffer: list[dict[str, Any]] = []

    def _scrivi() -> None:
        for gestore in gestori:
            conteggi = gestore.salva_sentenze_blocco(buffer, chiave_naturale=True)
            esito.inserite += conteggi["inserite"]
            esito.aggiornate += conteggi["aggiornate"]
            esito.invariate += conteggi["invariate"]
        buffer.clear()
        if progresso:
            progresso(f"{esito.pronunce_lette} pronunce lette")

    for record in record_da_file(coppie, dal_anno=dal_anno, esito=esito):
        buffer.append(record)
        if len(buffer) >= max(1, int(blocco)):
            _scrivi()
    if buffer:
        _scrivi()
    for gestore in gestori:
        gestore.ottimizza_fts()
        gestore.registra_importazione(
            fonte_codice=FONTE_CODICE,
            tipo_importazione="api",
            stato="completata",
            query_origine=IMPORT_COMPLETO if completo and not dal_anno else f"{IMPORT_PARZIALE}:dal_{dal_anno or 'tutti'}",
            url_origine=URL_DATI,
            file_origine=", ".join(Path(path).name for path in esito.file),
            record_letti=esito.pronunce_lette,
            record_creati=esito.inserite,
            record_aggiornati=esito.aggiornate,
            record_scartati=esito.pronunce_scartate,
        )
    esito.secondi = round(time.monotonic() - inizio, 1)
    for path in esito.db:
        file_db = Path(path)
        if file_db.exists():
            totale = file_db.stat().st_size
            wal = file_db.with_name(file_db.name + "-wal")
            if wal.exists():
                totale += wal.stat().st_size
            esito.dimensione_db_mb[path] = round(totale / (1024 * 1024), 1)
    return esito


def archivio_completo_presente(db_path: str | Path) -> bool:
    """True se il corpus ha gia' registrato un import completo riuscito dell'archivio della Consulta.

    Un import interrotto (riavvio del container a meta') non lascia il segno: il deploy successivo
    lo riprende, e le righe gia' scritte risultano invariate.
    """

    import sqlite3

    path = Path(db_path)
    if not path.exists():
        return False
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM importazioni_giurisprudenza WHERE query_origine = ? AND stato = 'completata'",
                (IMPORT_COMPLETO,),
            ).fetchone()
            return bool(row and row[0])
    except sqlite3.Error:
        return False


def corpus_ha_pronunce(db_path: str | Path) -> int:
    """Quante pronunce della Corte costituzionale contiene il corpus (0 se il file non esiste)."""

    import sqlite3

    path = Path(db_path)
    if not path.exists():
        return 0
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM sentenze WHERE organo_giudicante = ? AND COALESCE(ecli, '') LIKE 'ECLI:IT:COST:%'",
                (ORGANO,),
            ).fetchone()
            return int(row[0] or 0)
    except sqlite3.Error:
        return 0


__all__ = [
    "BLOCCO_PREDEFINITO",
    "IMPORT_COMPLETO",
    "archivio_completo_presente",
    "EsitoImport",
    "FONTE_CODICE",
    "LICENZA",
    "ORGANO",
    "PERIODI",
    "componi_record",
    "corpus_ha_pronunce",
    "data_iso",
    "file_periodo",
    "importa",
    "leggi_massime",
    "leggi_pronunce",
    "nucleo_dispositivo",
    "pulisci_testo",
    "record_da_file",
    "scarica",
    "url_massime",
    "url_pronunce",
]
