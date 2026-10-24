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


def _righe_normattiva(chiave: str, urn: str, oggi: dt.date, opener) -> list[dict]:
    from .normattiva_akn import converti, scarica

    atto = scarica(urn, oggi.strftime("%Y%m%d"), opener=opener)
    return converti(atto, chiave, oggi.isoformat())


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
        r["vigenza"] = "VIGENTE"
    return righe


def atti_da_acquisire(fab: Fabbisogno) -> dict[str, list[Riferimento]]:
    """Atti assenti e atti presenti a cui mancano articoli richiesti (si riacquisisce l'edizione vigente)."""
    out = {k: list(v) for k, v in fab.atti_mancanti.items()}
    for r in fab.articoli_mancanti:
        out.setdefault(r.atto, []).append(r)
    return out


def acquisisci(db: Path, cartella: Path, *, oggi: dt.date | None = None, simula: bool = False,
               scarica_normattiva=None, scarica_ue=None) -> Rapporto:
    """``scarica_*`` sostituibili nei test: (chiave, urn|celex, oggi) -> righe."""
    oggi = oggi or dt.date.today()
    rapporto = Rapporto(oggi.isoformat())
    richiesti = atti_da_acquisire(calcola_fabbisogno(db))
    pacchetto = Path(cartella) / oggi.strftime("%Y%m%d")
    opener = None
    pronti: list[tuple[str, list[dict]]] = []
    for chiave, refs in sorted(richiesti.items()):
        fonte = fonte_per_chiave(chiave)
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
                    righe = _righe_normattiva(chiave, fonte.urn, oggi, opener)
            else:
                righe = (scarica_ue or (lambda k, c, o: _righe_ue(k, c, o, Path(cartella) / "cache_ue")))(chiave, fonte.celex, oggi)
        except Exception as exc:  # noqa: BLE001 - un atto non scaricato non ferma gli altri
            rapporto.esiti.append(EsitoAcquisizione(chiave, "non_scaricato", f"{type(exc).__name__}: {str(exc)[:200]}"))
            continue
        trovati = {norm_articolo(r["articolo"]) for r in righe}
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
            (pacchetto / "atti" / f"{chiave}.jsonl").write_text(
                "\n".join(json.dumps(r, ensure_ascii=False) for r in righe) + "\n", encoding="utf-8")
        from lex.normativa.consultazione import importa_fonti

        rapporto.pacchetto = str(pacchetto)
        rapporto.importazione = importa_fonti(pacchetto, Path(db), oggi.isoformat())
    return rapporto
