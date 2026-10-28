"""Acquisizione automatica delle fonti richieste dalle schede e assenti dalla biblioteca.

Per ogni atto mancante (o con articoli richiesti che mancano nell'edizione presente):
1. si deduce la fonte ufficiale dalla chiave (``riferimenti``); le chiavi non deducibili restano nel rapporto;
2. si scarica il testo vigente alla data (Normattiva AKN o Ufficio delle pubblicazioni UE);
3. si controlla che contenga TUTTI gli articoli richiesti dalle schede: altrimenti non si importa nulla;
4. si scrive un pacchetto datato ``<cartella>/<AAAAMMGG>/atti/<chiave>.jsonl`` con URL, vigenza e impronte;
5. si importa con ``consultazione.importa_fonti`` (backup del database prima di scrivere, versioni precedenti
   conservate). L'esito di ogni atto e' registrato; nessuna eccezione interrompe gli altri atti.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field
from pathlib import Path

from .fabbisogno import Fabbisogno, Riferimento, calcola_fabbisogno, norm_articolo
from .riferimenti import fonte_per_chiave


@dataclass
class EsitoAcquisizione:
    chiave: str
    stato: str  # "importato" | "non_deducibile" | "non_scaricato" | "articoli_assenti" | "simulato"
    dettaglio: str = ""
    articoli: int = 0
    url: str = ""


@dataclass
class Rapporto:
    data: str
    esiti: list[EsitoAcquisizione] = field(default_factory=list)
    pacchetto: str = ""
    importazione: dict | None = None

    def to_dict(self) -> dict:
        return {"data": self.data, "pacchetto": self.pacchetto, "importazione": self.importazione,
                "esiti": [e.__dict__ for e in self.esiti]}


def _versione_con_partizioni(conn, *, urn: str, target: str, partizione: str | None):
    """Rilegge ogni parte con il validatore nativo, senza unire numeri omonimi.

    La query scopre soltanto nomi di partizione. Identità, data, catena, lettore
    e SHA di ciascun corpo restano verificati da leggi_versione.
    """
    from lex.normativa.versioni_akn import leggi_versione
    rows = leggi_versione(conn, urn=urn, data_riferimento=target, partizione=partizione)
    if rows or partizione is not None:
        return rows
    # Un atto con allegati può ripetere Art. 1. in parti diverse. Non si
    # sceglie il primo: ogni parte resta separata nel pacchetto nativo.
    parts = conn.execute("""SELECT DISTINCT a.partizione FROM normative_akn_articles a
        JOIN normative_akn_editions e ON e.id=a.edition_id
        JOIN normative_akn_chains c ON c.id=e.chain_id
        WHERE c.urn=? AND e.dal=(SELECT max(v.dal) FROM normative_akn_editions v
            WHERE v.chain_id=c.id AND v.dal<=?) ORDER BY a.partizione""", (urn, target)).fetchall()
    out = []
    for (part,) in parts:
        if not isinstance(part, str) or not part:
            continue
        checked = leggi_versione(conn, urn=urn, data_riferimento=target, partizione=part)
        out.extend(checked)
    if len({(x["partizione"], x["numero"]) for x in out}) != len(out):
        raise ValueError("Articoli omonimi dentro la stessa partizione: acquisizione non univoca")
    return out


def _righe_normattiva(chiave: str, urn: str, oggi: dt.date, opener, versione_al: dt.date | None = None,
                      archivio_locale: Path | None = None, cartella_prove: Path | None = None) -> list[dict]:
    from .normattiva_akn import converti, scarica

    cache_error = ""
    if archivio_locale is not None:
        import os
        import sqlite3
        from contextlib import closing
        path=Path(os.getenv("PCT_NORMATTIVA_VERSIONI_DB") or Path(archivio_locale).with_name("versioni_normattiva.sqlite"))
        target=(versione_al or oggi).isoformat()
        if path.is_file():
            from .riferimenti import PARTIZIONI_CODICI
            partitions = PARTIZIONI_CODICI
            try:
                with closing(sqlite3.connect(path.resolve().as_uri()+"?mode=ro",uri=True,timeout=3)) as conn:
                    cached=_versione_con_partizioni(conn,urn=urn,target=target,partizione=partitions.get(chiave))
            except (sqlite3.DatabaseError,ValueError) as exc:
                # Non si usa la cache non verificata e non la si sovrascrive.
                # Il medesimo identificatore pubblico viene acquisito dal sito.
                cached=[];cache_error=type(exc).__name__
            if cached:
                from lex.testi_ufficiali import collegamento_normattiva
                from .identita import chiave_partizione
                from lex.normativa.qualita_testo import qualita_testo
                from collections import Counter
                parts={row["partizione"] for row in cached}
                omonimi=Counter((row["partizione"],norm_articolo(row["numero"])) for row in cached)
                def key_for(row):
                    part=row["partizione"]
                    if omonimi[(part,norm_articolo(row["numero"]))]>1:
                        return chiave_partizione(chiave,part,row["localizzatore_xml"])
                    return chiave if chiave in partitions or part=="corpo_principale" or len(parts)==1 else chiave_partizione(chiave,part)
                return [{"chiave":key_for(row),"atto":chiave,"articolo":row["numero"],"rubrica":row["rubrica"],
                    "testo":row["testo"],"titolo_atto":row["titolo_atto"],"senza_testo":qualita_testo(row["testo"],solo_rubrica=bool(row["solo_intestazione"]))!="testo_acquisito",
                    "data_atto":row["urn"].rsplit(":",1)[1].split(";")[0],"urn":row["urn"],
                    "vigenza":"EDIZIONE_ACQUISITA","fonte_testo":"Normattiva AKN multiversione, archivio locale",
                    "url":collegamento_normattiva(row["urn"],row["numero"]),"consolidato_al":row["versione_dal"],
                    "raccolto_il":dt.datetime.fromisoformat(row["acquisita_utc"]).date().isoformat(),
                    "struttura_normativa":json.loads(row["struttura_json"]),
                    "provenienza_integrazione":{"vigenza_richiesta":target,"sha256_akn":row["xml_sha256"],
                        "sha256_payload_ufficiale":row["xml_sha256"],
                        "sha256_xml_decodificato":row["xml_decodificato_sha256"],
                        "codifica_trasporto":row["codifica_trasporto"],
                        "lettore_sha256":row["lettore_sha256"],
                        "acquisita_utc":row["acquisita_utc"],
                        "tipo_origine_archivio":row["tipo_origine"],
                        "zip_sha256":row["zip_sha256"],"xml_entry":row["xml_entry"],
                        "partizione_xml":row["partizione"],"localizzatore_xml":row["localizzatore_xml"],
                        "versione_formale_dal":row["versione_dal"],"versione_formale_al_escluso":row["versione_al_escluso"],
                        "espressione_dal":row["espressione_dal"],"catena_ufficiale_completa":True,
                        "urn_originale_akn":row.get("urn_originale_akn",row["urn"]),
                        "data_atto_riscontro":row.get("data_atto_riscontro"),
                        "identita_pubblicazione":row.get("identita_pubblicazione"),
                        "identita_metadata_non_datata":row.get("identita_metadata_non_datata",False),
                        "politica_lettori_sha256":row.get("politica_lettori_sha256"),
                        "rapporto_compatibilita_sha256":row.get("rapporto_compatibilita_sha256"),
                        "ordine_fotogramma_riscontro":row.get("ordine_fotogramma_riscontro"),
                        "lettore_riscontro_sha256":row.get("lettore_riscontro_sha256"),
                        "rilettura_catena_sha256":row.get("rilettura_catena_sha256"),
                        "applicabilita_al_fascicolo_verificata":False}}
                    for row in cached]
    atto = scarica(urn, (versione_al or oggi).strftime("%Y%m%d"), opener=opener)
    rows=converti(atto, chiave, oggi.isoformat())
    if cartella_prove is not None:
        import hashlib
        directory=Path(cartella_prove);directory.mkdir(parents=True,exist_ok=True)
        file=directory/(atto.sha256_xml+".xml")
        if file.exists():
            if hashlib.sha256(file.read_bytes()).hexdigest()!=atto.sha256_xml:
                raise ValueError("Fonte fisica AKN già archiviata con impronta discordante")
        else:
            with file.open("xb") as stream:stream.write(atto.xml)
        for row in rows:
            row["provenienza_integrazione"]["file_xml_originale"]="prove/"+file.name
    if cache_error:
        for row in rows:
            row["provenienza_integrazione"]["cache_locale_non_utilizzata"]=cache_error
    return rows


def _righe_ue(chiave: str, celex: str, oggi: dt.date, cache: Path) -> list[dict]:
    from lex.normativa.ue_regolamenti import RegolamentoUE, prepara, righe_jsonl

    esito = prepara(RegolamentoUE(celex, chiave), cache, oggi=oggi.isoformat())
    if not esito.valido:
        raise ValueError("; ".join(esito.errori + esito.note)[:300])
    url = f"https://eur-lex.europa.eu/legal-content/IT/TXT/?uri=CELEX:{esito.celex_usato}"
    righe = righe_jsonl(esito.atto, chiave=chiave, url=url, consolidato_al=esito.consolidato_al,
                        raccolto_il=oggi.isoformat())
    for r in righe:
        r["articolo"] = norm_articolo(r["articolo"])
        r["vigenza"] = "EDIZIONE_ACQUISITA"
        r["provenienza_integrazione"] = {
            "vigenza_richiesta": oggi.isoformat(), "celex_usato":esito.celex_usato,
            "data_consolidato":esito.consolidato_al,
            "elenco_consolidati_verificato":esito.elenco_consolidati_verificato,
            "consolidati_riscontrati":esito.consolidati_riscontrati,
            "note_acquisizione":esito.note,
            "applicabilita_al_fascicolo_verificata":False,
        }
    return righe


def atti_da_acquisire(fab: Fabbisogno) -> dict[str, list[Riferimento]]:
    """Atti assenti e atti presenti a cui mancano articoli richiesti (si riacquisisce l'edizione vigente)."""
    out = {k: list(v) for k, v in fab.atti_mancanti.items()}
    for r in fab.articoli_mancanti:
        out.setdefault(r.atto, []).append(r)
    return out


def acquisisci(db: Path, cartella: Path, *, oggi: dt.date | None = None, simula: bool = False,
               scarica_normattiva=None, scarica_ue=None, riferimenti: list[Riferimento] | None = None,
               versione_al: dt.date | None = None, fonti_note: dict | None = None) -> Rapporto:
    """``scarica_*`` sostituibili nei test: (chiave, urn|celex, oggi) -> righe."""
    oggi = oggi or dt.date.today()
    rapporto = Rapporto(oggi.isoformat())
    richiesti = atti_da_acquisire(calcola_fabbisogno(db) if riferimenti is None else calcola_fabbisogno(db, riferimenti))
    if versione_al is not None and riferimenti is not None:
        # Recupero esplicito della versione richiesta: non basta la presenza
        # di un'edizione diversa nell'archivio.
        richiesti = {}
        for ref in riferimenti:
            richiesti.setdefault(ref.atto, []).append(ref)
    pacchetto = Path(cartella) / oggi.strftime("%Y%m%d")
    opener = None
    pronti: list[tuple[str, list[dict]]] = []
    for chiave, refs in sorted(richiesti.items()):
        fonte = (fonti_note or {}).get(chiave) or fonte_per_chiave(chiave)
        if fonte.tipo == "non_deducibile":
            rapporto.esiti.append(EsitoAcquisizione(chiave, "non_deducibile", fonte.motivo))
            continue
        if simula:
            rapporto.esiti.append(EsitoAcquisizione(chiave, "simulato", fonte.urn or fonte.celex))
            continue
        try:
            if fonte.tipo == "normattiva":
                if scarica_normattiva:
                    righe = scarica_normattiva(chiave, fonte.urn, oggi)
                else:
                    if opener is None:
                        from .normattiva_akn import nuovo_opener
                        opener = nuovo_opener()
                    righe = _righe_normattiva(chiave, fonte.urn, oggi, opener, versione_al=versione_al, archivio_locale=Path(db), cartella_prove=pacchetto / "prove")
            else:
                righe = (scarica_ue or (lambda k, c, o: _righe_ue(k, c, o, Path(cartella) / "cache_ue")))(chiave, fonte.celex, versione_al or oggi)
                for row in righe:
                    row["raccolto_il"] = oggi.isoformat()
        except Exception as exc:  # noqa: BLE001 - un atto non scaricato non ferma gli altri
            rapporto.esiti.append(EsitoAcquisizione(chiave, "non_scaricato", f"{type(exc).__name__}: {str(exc)[:200]}"))
            continue
        from lex.normativa.qualita_testo import qualita_testo
        trovati = {norm_articolo(r["articolo"]) for r in righe
                   if r.get("chiave")==chiave and qualita_testo(r.get("testo", ""),solo_rubrica=r.get("senza_testo") in (True,1))=="testo_acquisito"}
        assenti = sorted({r.articolo for r in refs if norm_articolo(r.articolo) not in trovati})
        if not righe or assenti:
            rapporto.esiti.append(EsitoAcquisizione(chiave, "articoli_assenti",
                                                    f"articoli richiesti non trovati nel testo ufficiale: {assenti}"))
            continue
        pronti.append((chiave, righe))
        rapporto.esiti.append(EsitoAcquisizione(chiave, "importato", articoli=len(righe), url=righe[0].get("url", "")))
    if pronti:
        (pacchetto / "atti").mkdir(parents=True, exist_ok=True)
        for chiave, righe in pronti:
            per_partizione={}
            for row in righe:
                per_partizione.setdefault(row["chiave"],[]).append(row)
            for part_key,part_rows in per_partizione.items():
                (pacchetto / "atti" / f"{part_key.replace(chr(47), chr(95))}.jsonl").write_text(
                    "\n".join(json.dumps(r, ensure_ascii=False) for r in part_rows) + "\n", encoding="utf-8")
        from lex.normativa.consultazione import importa_fonti

        rapporto.pacchetto = str(pacchetto)
        rapporto.importazione = importa_fonti(pacchetto, Path(db), (versione_al or oggi).isoformat())
    return rapporto
