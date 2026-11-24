"""Harness di Lex: la domanda dell'avvocato passa sempre dai passi che consultano norme e regole.

1. comprensione — tipo di richiesta (redazione, parere, termine, norma, operativa), atto, racconto di fatti;
2. fatti — date, importi qualificati, parti e ruoli, luoghi, segnali giuridici, solo dal testo;
3. norme — testo vigente dall'archivio Normattiva del software (istantanea + lettura dal vivo);
4. regole — fattispecie e regole processuali deterministiche (valore, giudice, foro, procedibilità, rito, termini);
5. composizione — schema fisso: cosa ho capito, conclusione, come e perché, termini, cosa fare, dubbi, norme, bozza;
6. controllo — ogni affermazione confrontata con le parole della norma; ogni articolo citato deve esistere.

Le domande operative (scadenze, PEC, agenda, clienti dello studio) non passano di qui.
"""
from __future__ import annotations

import re

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from .comprensione import Comprensione, comprendi, e_richiesta_giuridica
from .composizione import componi
from .controllo import EsitoControllo, verifica_analisi, verifica_citazioni
from .fatti import leggi_fatti
from .fattispecie import scegli
from .modello import Punto
from .norme import NORME, piano, testo_norma

__all__ = ["RispostaHarness", "comprendi", "e_richiesta_giuridica", "rispondi"]


@dataclass
class RispostaHarness:
    testo: str
    tipo: str
    regola: str
    affidabilita: float
    fonti: list[dict[str, str]] = field(default_factory=list)
    norme_verificate: list[str] = field(default_factory=list)
    affermazioni_tolte: list[str] = field(default_factory=list)
    citazioni_non_verificate: list[str] = field(default_factory=list)
    bozza: str = ""
    registro: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"answer": self.testo, "kind": self.tipo, "rule": self.regola, "confidence": self.affidabilita,
                "sources": self.fonti, "verified_norms": self.norme_verificate,
                "removed_claims": self.affermazioni_tolte, "unverified_citations": self.citazioni_non_verificate,
                "draft": self.bozza, "deterministic": True, "registro": self.registro,
                **({"choices": self.registro["scelte"]} if self.registro.get("scelte") else {})}


def _affidabilita(esito: EsitoControllo, punti: int) -> float:
    if punti == 0:
        return 0.3
    base = 0.92 - 0.12 * len(esito.affermazioni_tolte) - 0.08 * len(esito.citazioni_non_verificate)
    return round(max(0.3, min(0.95, base)), 2)


def risposta_norma(domanda: str) -> RispostaHarness | None:
    """Testo di un articolo del catalogo dall'istantanea dell'archivio: risposta immediata, senza ricerche."""
    from lex.testi_ufficiali import riconosci_articolo

    richiesta = riconosci_articolo(domanda)
    if richiesta is None:
        return None
    sigla = {"codice civile": "cc", "codice di procedura civile": "cpc", "codice penale": "cp",
             "codice di procedura penale": "cpp"}.get(richiesta.etichetta_atto)
    if not sigla:
        return None
    chiave = f"{sigla}:{richiesta.chiave}"
    t = testo_norma(chiave)
    if chiave not in NORME or t is None:
        return None
    agg = f" (aggiornamento dell'archivio {t.aggiornamento})" if t.aggiornamento else ""
    testo = "\n".join([f"**{NORME[chiave].citazione} — {NORME[chiave].rubrica}**: testo vigente dall'archivio Normattiva "
                       f"di IUSENTRA{agg}.", "", "> " + " ".join(t.testo.split()), "", f"Fonte ufficiale: {t.url}"])
    return RispostaHarness(testo, "norma", "testo_articolo", 0.95,
                           [{"title": f"Normattiva — {NORME[chiave].citazione}", "url": t.url}], [chiave])


_SERVE_IMPORTO = frozenset({"consumatore", "competenza_pagamento", "negoziazione_obbligatoria"})


def _nome_regola(regola: str) -> str:
    from .significato import voci

    return next((v.nome for v in voci() if v.regola == regola), regola.replace("_", " "))


DISTACCO_MASSIMO = 0.12     # una proposta resta solo se non è più lontana di così dal primo strumento
SOGLIA_SIGNIFICATO = 0.22   # somiglianza minima per proporre uno strumento: fuori materia <= 0,16, in materia >= 0,26 (24/11)


def rispondi(domanda: str, *, oggi: date | None = None, comprensione: Comprensione | None = None) -> RispostaHarness | None:
    c = comprensione or comprendi(domanda)
    if not c.per_harness:
        return None
    if c.tipo == "norma":
        return risposta_norma(domanda)
    from .chiarimenti import (materia_da_chiarire, testo_chiarimento, testo_chiarimento_lato, testo_chiarimento_strumento,
                              testo_dati_mancanti, testo_fuori_materia)

    scelte = materia_da_chiarire(domanda)
    if scelte:
        return RispostaHarness(testo_chiarimento(scelte), "chiarimento", "chiarimento_materia", 1.0,
                               registro={"rule": "chiarimento_materia", "scelte": scelte})
    from .normalizzazione import normalizza_richiesta

    f = leggi_fatti(normalizza_richiesta(domanda), oggi=oggi)
    from .fattispecie import REGOLE
    from .significato import area, cerca, strumento_indicato

    indicata = strumento_indicato(domanda)
    regola = next((r for r in REGOLE if r[0] == indicata), None) if indicata else scegli(c, f)
    if regola is None:
        # Nessuna regola riconosce la fattispecie: la ricerca per significato propone gli strumenti più vicini, e
        # l'avvocato sceglie. Sotto la soglia la domanda non è materia delle regole di Lex.
        # Le domande di termine e di calcolo restano ai motori certi (calcolatori dei termini), che rispondono senza regola.
        if c.tipo not in {"parere", "redazione"}:
            return None
        vicine = cerca(domanda, 8)
        proposte: list = []
        if vicine and vicine[0][1] >= SOGLIA_SIGNIFICATO:
            # Solo strumenti della stessa area del più vicino e non troppo distanti da esso: mai proposte assurde.
            primo_area, primo_punteggio = area(vicine[0][0].regola), vicine[0][1]
            proposte = [v for v, s in vicine if area(v.regola) == primo_area and s >= max(SOGLIA_SIGNIFICATO,
                                                                                       primo_punteggio - DISTACCO_MASSIMO)][:4]
        racconto = c.racconto or f.importi or f.eventi or re.search(
            r"\b(?:mio|mia|miei|mie|nostr[oaie]|mi|ci|ho|abbiamo|hanno|e morto|e morta|il cliente|la cliente)\b", piano(domanda))
        if len(proposte) == 1 and not racconto:
            # Domanda di diritto senza fatti con un solo strumento vicino: rispondono i motori certi o la rubrica ufficiale.
            return None
        if len(proposte) == 1:
            # Una sola proposta vicina: si risponde con quella regola, chiedendo i dati se i fatti non bastano.
            regola = next(r for r in REGOLE if r[0] == proposte[0].regola)
            indicata = regola[0]
        elif not proposte:
            return RispostaHarness(testo_fuori_materia(), "chiarimento", "fuori_materia", 1.0,
                                   registro={"rule": "fuori_materia"})
    if regola is None:
        base = domanda.strip()
        scelte = [f"{base} (strumento: {v.nome})" for v in proposte[:4]]
        return RispostaHarness(testo_chiarimento_strumento(scelte, [v.nome for v in proposte[:4]]), "chiarimento",
                               "chiarimento_strumento", 1.0, registro={"rule": "chiarimento_strumento", "scelte": scelte})
    from .lato import scelte_sul_lato

    scelte_lato = (scelte_sul_lato(domanda, regola[0]) if c.tipo in {"parere", "termine"} and not indicata else None)
    if scelte_lato:
        return RispostaHarness(testo_chiarimento_lato(scelte_lato), "chiarimento", "chiarimento_lato", 1.0,
                               registro={"rule": "chiarimento_lato", "scelte": scelte_lato})
    # Regole che calcolano sul valore della causa: senza un importo nei fatti si chiede il dato invece di fallire.
    if regola[0] in _SERVE_IMPORTO and not f.importi:
        return RispostaHarness(testo_dati_mancanti(_nome_regola(regola[0]), ["valore della causa (l'importo chiesto o "
                               "contestato)"]), "chiarimento", "chiarimento_dati", 1.0,
                               registro={"rule": "chiarimento_dati", "regola_scelta": regola[0]})
    try:
        analisi = regola[2](c, f)
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        if not indicata:
            raise
        # Strumento scelto dall'avvocato fra le proposte, ma i fatti non bastano alla regola: si chiedono i dati.
        return RispostaHarness(testo_dati_mancanti(_nome_regola(regola[0]), ["fatti essenziali: parti, date, importi e atti "
                               "ricevuti o da proporre"]), "chiarimento", "chiarimento_dati", 1.0,
                               registro={"rule": "chiarimento_dati", "regola_scelta": regola[0]})
    from .coerenza import verifica as _coerenza

    analisi.dubbi += [d for d in _coerenza(analisi, f) if d not in analisi.dubbi]
    _requisiti_bozza(analisi)
    esito = verifica_analisi(analisi)
    _vigenza_alla_data_dei_fatti(analisi, f, esito)
    analisi.giurisprudenza = _giurisprudenza(c, analisi)
    testo = componi(c.tipo, analisi, esito, domanda)
    verifica_citazioni(testo, esito)
    if esito.citazioni_non_verificate:
        testo = componi(c.tipo, analisi, esito, domanda)
    fonti = []
    for chiave in esito.norme_verificate:
        t = testo_norma(chiave)
        if t and t.url:
            fonti.append({"title": f"Normattiva — {NORME[chiave].citazione}", "url": t.url})
    return RispostaHarness(testo, c.tipo, analisi.regola, _affidabilita(esito, len(analisi.punti())), fonti,
                           esito.norme_verificate, esito.affermazioni_tolte, esito.citazioni_non_verificate, analisi.bozza,
                           registro(c, f, analisi, esito))


def _giurisprudenza(c: Comprensione, a):
    """Fase 5: pronunce negli archivi (Cassazione SentenzeWeb e archivio dello studio) per le norme della conclusione."""
    import os

    if os.environ.get("LEX_HARNESS_GIURISPRUDENZA", "1") == "0" or c.tipo not in {"parere", "redazione"}:
        return None
    from .giurisprudenza import cerca

    chiavi = list(dict.fromkeys(r.chiave for p in a.conclusione for r in p.rif))[:2]
    if not chiavi:
        return None
    # Prima le pronunce precalcolate per norma (nessuna lettura dell'archivio nella richiesta); la ricerca dal vivo,
    # con il suo tempo massimo, solo se la norma non è nell'indice precalcolato.
    from .giurisprudenza import per_norme

    esito = per_norme(chiavi)
    if esito is not None:
        return esito
    domanda = " ".join(NORME[k].citazione for k in chiavi)
    return cerca(domanda)


def _vigenza_alla_data_dei_fatti(a, f, esito) -> None:
    """Il testo letto è quello vigente oggi: se una norma sostanziale citata è stata modificata con effetto dopo la
    data dei fatti, la risposta lo dichiara (la nota di aggiornamento è nel testo Normattiva)."""
    from .norme import modifiche_dopo

    date_fatti = sorted(e.data for e in getattr(f, "eventi", []) if getattr(e, "data", None))
    if not date_fatti:
        return
    primo = date_fatti[0]
    a.vigenza = {"data_fatti": primo.isoformat(), "modifiche_successive": {}}
    for chiave in esito.norme_verificate:
        dopo = modifiche_dopo(chiave, primo)
        if dopo:
            d, nota = dopo[-1]
            a.vigenza["modifiche_successive"][chiave] = [x.isoformat() for x, _ in dopo]
            a.dubbi.append(f"Vigenza: {NORME[chiave].citazione} è citato nel testo vigente, ma una modifica ha effetto dal "
                           f"{d.strftime('%d/%m/%Y')} e i fatti cominciano il {primo.strftime('%d/%m/%Y')}: verificare quale "
                           f"testo si applica (nota Normattiva: «{nota[:160]}…»).")


def requisiti_della_bozza(bozza: str) -> tuple[str, list[dict[str, str]]]:
    """Requisiti obbligatori dell'atto (lex/procedura_atti/requisiti_atti) non rilevati nella bozza.

    Il tipo d'atto si legge dal titolo della bozza con la stessa scelta della procedura atti."""
    from lex.procedura_atti.requisiti_atti import CATALOGO, COMUNI_RICORSO, SCELTA

    titolo = " ".join((bozza or "").strip().splitlines()[:3])  # ufficio, nome dell'atto, norme
    # Vince il nome d'atto che compare per primo («COMPARSA … OPPOSIZIONE ALLA CONVALIDA DI SFRATTO» è una comparsa).
    trovati = [(m.start(), nome) for nome, rx in SCELTA if (m := re.search(rx, titolo, re.I))]
    modello = min(trovati)[1] if trovati else "ricorso_generico"
    requisiti = CATALOGO.get(modello, COMUNI_RICORSO)
    mancanti = [{k: r[k] for k in ("id", "descrizione", "norma")} for r in requisiti
                if not any(re.search(sg, bozza, re.I) for sg in r["segnali"])]
    return modello, mancanti


def _requisiti_bozza(a) -> None:
    if not a.bozza:
        return
    modello, mancanti = requisiti_della_bozza(a.bozza)
    a.requisiti_bozza = {"modello": modello, "mancanti": mancanti}
    if mancanti:
        a.dubbi.append("Requisiti dell'atto non rilevati nella bozza (controllo della procedura atti): "
                       + "; ".join(f"{m['descrizione']}" + (f" ({m['norma']})" if m["norma"] else "") for m in mancanti) + ".")


def _punti(lista) -> list[dict[str, Any]]:
    return [{"testo": p.testo, "fonti": [{"norma": NORME[r.chiave].citazione, "comma": r.comma, "ancora": r.ancora}
                                          for r in p.rif]} for p in lista]


def registro(c: Comprensione, f, a, esito: EsitoControllo) -> dict[str, Any]:
    """Il registro della risposta: il risultato strutturato di ogni fase, con le fonti di ogni affermazione."""
    from pathlib import Path

    norme = []
    for chiave in esito.norme_verificate:
        t = testo_norma(chiave)
        norme.append({"chiave": chiave, "citazione": NORME[chiave].citazione, "url": t.url if t else "",
                      "aggiornamento_archivio": t.aggiornamento if t else "", "origine": t.origine if t else "",
                      "vigente": bool(t and t.vigente)})
    scheda = Path(__file__).resolve().parents[2] / "pct" / "template_atti_schede" / f"{a.modello}.json" if a.modello else None
    return {
        "1_comprensione": {"tipo": c.tipo, "atto": c.atto, "racconto_di_fatti": c.racconto, "motivi": c.motivi},
        "2_fatti": {"data_di_oggi": f.oggi.strftime("%d/%m/%Y"), "parte_assistita": vars(f.assistita),
                    "controparte": vars(f.controparte), "residenza_o_sede_controparte": f.residenza_convenuto,
                    "luogo_immobile": f.luogo_immobile, "luogo_lavoro": f.luogo_lavoro,
                    "importi": [{"valore": i.valore, "qualifica": i.qualifica} for i in f.importi],
                    "eventi": [{"data": e.data.strftime("%d/%m/%Y"), "testo": e.testo[:200]} for e in f.eventi],
                    "segnali": sorted(f.segnali), "fonte": "testo della richiesta"},
        "3_qualificazione": {"regola": a.regola, "materia": a.materia},
        "4_norme": norme,
        "5_giurisprudenza": (a.giurisprudenza.to_dict() if getattr(a, "giurisprudenza", None) is not None else
                             {"stato": "non consultata per questo tipo di domanda"}),
        "6_rimedio": {"forma": a.forma, "rimedio": a.rimedio, "conclusione": _punti(a.conclusione)},
        "7_competenza": {"giudice": a.giudice, "valore": a.valore, "punti": _punti(a.competenza)},
        "8_rito": _punti(a.rito),
        "9_procedibilita": _punti(a.procedibilita),
        "10_termini": _punti(a.termini),
        "11_inquadramento": _punti(a.inquadramento),
        "12_tranelli_e_avvertenze": [_punti([x])[0] if isinstance(x, Punto) else x for x in a.avvertenze],
        "13_dati_mancanti": list(a.dati_mancanti),
        "14_modello_atto": {"scheda": a.modello, "presente_nel_catalogo": bool(scheda and scheda.is_file()),
                            "bozza": bool(a.bozza), "requisiti": getattr(a, "requisiti_bozza", None)},
        "4b_vigenza_alla_data_dei_fatti": getattr(a, "vigenza", None),
        "15_controlli": {"affermazioni_non_verificate_escluse": esito.affermazioni_tolte,
                         "citazioni_non_verificate": esito.citazioni_non_verificate, "dubbi": list(a.dubbi)},
    }
