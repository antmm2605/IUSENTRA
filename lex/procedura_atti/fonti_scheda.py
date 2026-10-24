"""Fonti di Lex dalla scheda del modello d'atto: testo vigente, provenienza e impronta, senza ricerca libera.

Per il modello scelto (``pct/template_atti_schede/<ID>.json``) si prendono la base normativa e le norme dei campi
obbligatori, si legge il testo vigente nella biblioteca «Codici e leggi» e si costruiscono ``fonti`` e
``fonti_ref`` nel formato della procedura atti (provenienza obbligatoria, 2.449.1). Le norme non ancora approvate
dall'avvocato per quell'impronta, o con una proposta di revisione aperta, restano utilizzabili ma vengono elencate
in ``pendenze``: la consegna non potra' risultare «pronta per la revisione» finche' non sono risolte.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field
from pathlib import Path

from lex.normativa.biblioteca.fabbisogno import CARTELLA_SCHEDE, norm_articolo

from .provenienza import sha256_testo

SIGLE = {"codice_civile": "c.c.", "codice_procedura_civile": "c.p.c.", "codice_penale": "c.p.",
         "codice_procedura_penale": "c.p.p.", "codice_processo_amministrativo": "c.p.a.", "costituzione": "Cost.",
         "codice_crisi": "CCII", "codice_consumo": "cod. consumo", "codice_strada": "cod. strada",
         "codice_privacy": "cod. privacy", "preleggi": "disp. prel. c.c.",
         "28/2010": "d.lgs. 28/2010", "115/2002": "d.P.R. 115/2002"}  # chiavi storiche dell'archivio senza tipo


@dataclass
class FontiScheda:
    scheda: str
    titolo: str
    fonti: dict[int, str] = field(default_factory=dict)
    fonti_ref: list[dict] = field(default_factory=list)
    requisiti: list[dict] = field(default_factory=list)
    pendenze: list[str] = field(default_factory=list)


def _sigla(atto: str) -> str:
    if atto in SIGLE:
        return SIGLE[atto]
    parti = atto.split("_")
    if len(parti) == 3 and parti[1].isdigit():
        tipo = {"legge": "l.", "dlgs": "d.lgs.", "dpr": "d.P.R.", "dl": "d.l.", "rd": "r.d."}.get(parti[0], parti[0])
        return f"{tipo} {parti[1]}/{parti[2]}"
    if atto.startswith("reg_ue_"):
        return f"Reg. UE {parti[2]}/{parti[3]}"
    return atto.replace("_", " ")


def fonti_per_scheda(scheda_id: str, db: Path, *, repository=None, cartella: Path = CARTELLA_SCHEDE,
                     oggi: dt.date | None = None) -> FontiScheda:
    from pct.schede_fonti.verifica import verifica_schede

    oggi = oggi or dt.date.today()
    d = json.loads((Path(cartella) / f"{scheda_id}.json").read_text(encoding="utf-8"))
    out = FontiScheda(scheda_id, str(d.get("titolo") or ""))
    esiti = verifica_schede(db, cartella, solo_scheda=scheda_id)
    visti: dict[tuple[str, str], int] = {}
    for e in esiti:
        k = (e.atto, norm_articolo(e.articolo))
        if e.stato != "presente":
            out.pendenze.append(f"{_sigla(e.atto)} art. {e.articolo}: {e.stato.replace('_', ' ')}")
            continue
        if k not in visti:
            n = len(visti) + 1
            visti[k] = n
            testo = f"{_sigla(e.atto)} · art. {e.articolo} · testo vigente (biblioteca aggiornata al {e.aggiornato_al})\n{e.testo}"
            out.fonti[n] = testo
            out.fonti_ref.append({"n": n, "atto": e.atto, "articolo": e.articolo, "sigla": _sigla(e.atto),
                                  "provenienza": {"tipo": "norma", "url": e.url, "versione": f"vigente, edizione {e.aggiornato_al}",
                                                  "acquisita_il": oggi.strftime("%d/%m/%Y"), "sha256": sha256_testo(testo)}})
            if repository is not None:
                stato = repository.norma(scheda_id, e.atto, k[1]) or {}
                if stato.get("sha256_approvato") != e.sha256:
                    out.pendenze.append(f"{_sigla(e.atto)} art. {e.articolo}: testo vigente non ancora approvato per questa scheda")
        if e.origine.startswith("campo:"):
            out.requisiti.append({"campo": e.origine[6:], "norma": f"art. {e.articolo} {_sigla(e.atto)}", "perche": e.perche,
                                  "fonte": visti[k]})
    if repository is not None:
        out.pendenze += [f"proposta aperta: {p['motivo'][:160]}" for p in repository.proposte(scheda=scheda_id)]
    return out
