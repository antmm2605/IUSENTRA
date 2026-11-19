"""Passo 4 dell'harness: regole processuali deterministiche (valore, giudice, foro, procedibilità, rito).

Le soglie non sono scritte qui: il limite del giudice di pace si legge dal testo vigente dell'art. 7 c.p.c. e la soglia
della negoziazione assistita dall'art. 3 d.l. 132/2014. Se il testo non si legge, la regola si astiene.
"""
from __future__ import annotations

from .fatti import Fatti, euro
from .modello import Punto, Rif
import re
from functools import lru_cache

from .norme import importo_in_lettere_dopo

# Materie dell'art. 5, comma 1, d.lgs. 28/2010 (mediazione obbligatoria): nome → parole letterali del testo vigente.
MATERIE_MEDIAZIONE = {
    "condominio": "condominio", "diritti reali": "diritti reali", "divisione": "divisione",
    "successioni ereditarie": "successioni ereditarie", "patti di famiglia": "patti di famiglia", "locazione": "locazione",
    "comodato": "comodato", "affitto di aziende": "affitto di aziende",
    "responsabilità medica e sanitaria": "responsabilita' medica e sanitaria",
    "diffamazione con la stampa o altro mezzo di pubblicità": "diffamazione con il mezzo della stampa",
    "contratti assicurativi, bancari e finanziari": "contratti assicurativi, bancari e finanziari",
    "associazione in partecipazione": "associazione in partecipazione", "consorzio": "consorzio",
    "franchising": "franchising", "contratti di opera": "opera", "contratti di rete": "rete",
    "somministrazione": "somministrazione", "società di persone": "societa' di persone", "subfornitura": "subfornitura",
}
_ELENCO_ART5 = "e' tenuto preliminarmente a esperire il procedimento di mediazione"


def limite_gdp_beni_mobili() -> int | None:
    return importo_in_lettere_dopo("cpc:7", "beni mobili di valore non superiore")


def limite_gdp_circolazione() -> int | None:
    return importo_in_lettere_dopo("cpc:7", "purche il valore della controversia non superi")


def soglia_negoziazione() -> int | None:
    return importo_in_lettere_dopo("dl132:3", "somme non eccedenti")


def valore_somma(capitale: float, *, interessi_scaduti: bool = False) -> list[Punto]:
    punti = [Punto(f"Valore della causa: {euro(capitale)}, cioè la somma domandata: nelle cause relative a somme di "
                   "danaro il valore si determina in base alla somma indicata dall'attore.",
                   [Rif("cpc:10", "si determina dalla domanda"), Rif("cpc:14", "in base alla somma indicata")])]
    if interessi_scaduti:
        punti.append(Punto("Gli interessi già scaduti, le spese e i danni anteriori alla domanda si sommano al capitale: "
                           "se si chiedono, il valore supera la somma capitale.",
                           [Rif("cpc:10", "gli interessi scaduti, le spese e i danni anteriori alla proposizione si sommano col capitale")]))
    return punti


def giudice_per_valore(valore: float, *, circolazione: bool = False) -> tuple[str, list[Punto]]:
    """Giudice di pace o tribunale per una causa su somme di danaro o beni mobili (art. 7 e art. 9 c.p.c.)."""
    limite = limite_gdp_circolazione() if circolazione else limite_gdp_beni_mobili()
    if limite is None:
        return "", [Punto("Il limite di valore del giudice di pace non si è potuto leggere dal testo vigente dell'art. 7 "
                          "c.p.c.: verificalo prima di scegliere il giudice.", [], False, "art. 7 c.p.c. non letto")]
    ancora = "circolazione di veicoli e di natanti" if circolazione else "beni mobili di valore non superiore"
    controllo = _calcolatore_competenza(valore, circolazione)
    if controllo and controllo != ("Giudice di pace" if valore <= limite else "Tribunale"):
        return "", [Punto("La competenza per valore letta dall'art. 7 c.p.c. vigente non coincide con quella del calcolatore "
                          f"di IUSENTRA ({controllo}): verificarla prima di scegliere il giudice.", [], False,
                          "calcolatore della competenza discordante")]
    if valore <= limite:
        return "Giudice di pace", [Punto(
            f"Competente per valore è il giudice di pace: la causa ({euro(valore)}) non supera il limite di "
            f"{euro(limite)} dell'art. 7, comma {'2' if circolazione else '1'}, c.p.c. vigente.", [Rif("cpc:7", ancora)])]
    return "Tribunale", [Punto(
        f"Competente per valore è il tribunale: {euro(valore)} supera il limite di {euro(limite)} del giudice di pace "
        f"(art. 7, comma {'2' if circolazione else '1'}, c.p.c. vigente) e il tribunale è competente per tutte le cause "
        "che non sono di competenza di altro giudice.",
        [Rif("cpc:7", ancora), Rif("cpc:9", "competente per tutte le cause che non sono di competenza di altro giudice")])]


def foro_convenuto(f: Fatti, *, obbligazione: bool = True) -> tuple[str, list[Punto]]:
    citta = f.residenza_convenuto
    pg = f.controparte.persona_giuridica
    punti: list[Punto] = []
    if pg:
        punti.append(Punto(f"Foro generale della persona giuridica: luogo della sede ({citta or '[sede da completare]'}).",
                           [Rif("cpc:19", "giudice del luogo dove essa ha sede")]))
    else:
        punti.append(Punto(f"Foro generale della persona fisica: luogo di residenza o domicilio del convenuto "
                           f"({citta or '[residenza da completare]'}). L'art. 19 c.p.c. riguarda le persone giuridiche e "
                           "qui non serve.", [Rif("cpc:18", "il convenuto ha la residenza o il domicilio")]))
    if obbligazione:
        punti.append(Punto("In alternativa, per le cause su diritti di obbligazione, è competente anche il giudice del "
                           "luogo in cui è sorta o deve eseguirsi l'obbligazione dedotta in giudizio.",
                           [Rif("cpc:20", "sorta o deve eseguirsi l'obbligazione dedotta in giudizio")]))
    return citta, punti


def mediazione_obbligatoria(materia: str | None) -> list[Punto]:
    if materia and materia in MATERIE_MEDIAZIONE:
        punti = [Punto(f"Mediazione obbligatoria: la controversia in materia di {materia} rientra nell'elenco dell'art. 5, "
                       "comma 1, d.lgs. 28/2010; l'esperimento del procedimento di mediazione è condizione di "
                       "procedibilità della domanda.", [Rif("dlgs28:5", MATERIE_MEDIAZIONE[materia], "1"),
                                                      Rif("dlgs28:5", "condizione di procedibilita", "2")])]
        if materia == "responsabilità medica e sanitaria":
            punti.append(Punto("Per la responsabilità sanitaria, in alternativa alla mediazione, si può proporre il ricorso per "
                               "consulenza tecnica preventiva ai fini della composizione della lite.",
                               [Rif("l24:8", "696-bis")]))
        return punti
    # Una negazione non si ancora a una parola dell'elenco: l'ancora è la regola del comma 1, e il confronto con le
    # 21 materie dell'elenco è scritto nel registro.
    return [Punto("Mediazione: la domanda non rientra fra le materie per cui chi agisce «è tenuto preliminarmente a "
                  "esperire il procedimento di mediazione» (art. 5, comma 1, d.lgs. 28/2010: " + ", ".join(MATERIE_MEDIAZIONE)
                  + "): non è condizione di procedibilità.", [Rif("dlgs28:5", _ELENCO_ART5, "1")])]


def negoziazione_pagamento(valore: float, *, consumatore: bool = False, mediazione: bool = False,
                           monitorio: bool = False) -> list[Punto]:
    soglia = soglia_negoziazione()
    if soglia is None:
        return [Punto("La soglia della negoziazione assistita non si è potuta leggere dal testo vigente dell'art. 3 "
                      "d.l. 132/2014: verificala.", [], False, "art. 3 d.l. 132/2014 non letto")]
    if monitorio:
        return [Punto("Negoziazione assistita: non si applica ai procedimenti per ingiunzione, inclusa l'opposizione.",
                      [Rif("dl132:3", "procedimenti per ingiunzione, inclusa l'opposizione")])]
    if mediazione:
        return [Punto("Negoziazione assistita: non è condizione di procedibilità, perché la controversia rientra nei casi "
                      "di mediazione obbligatoria, esclusi dall'art. 3, comma 1, d.l. 132/2014 (che rinvia ancora al «comma 1-bis» "
                      "dell'art. 5 d.lgs. 28/2010, oggi comma 1).",
                      [Rif("dl132:3", "articolo 5, comma 1-bis")])]
    if consumatore:
        return [Punto("Negoziazione assistita: non è obbligatoria, perché l'art. 3, comma 1, d.l. 132/2014 non si applica "
                      "alle controversie su obbligazioni contrattuali derivanti da contratti fra professionisti e consumatori.",
                      [Rif("dl132:3", "contratti conclusi tra professionisti e consumatori")])]
    if valore <= soglia:
        uguale = " (la domanda è esattamente pari alla soglia, quindi vi rientra: «non eccedenti»)" if valore == soglia else ""
        return [Punto(f"Negoziazione assistita obbligatoria: è una domanda di pagamento a qualsiasi titolo di somme non "
                      f"eccedenti {euro(soglia)}{uguale}. Prima della causa va inviato l'invito alla convenzione di "
                      "negoziazione assistita; la condizione si considera avverata se l'invito non è seguito da adesione o "
                      "è seguito da rifiuto entro trenta giorni dalla ricezione.",
                      [Rif("dl132:3", "pagamento a qualsiasi titolo di somme non eccedenti"),
                       Rif("dl132:3", "entro trenta giorni dalla sua ricezione")])]
    return [Punto(f"Negoziazione assistita: non è obbligatoria, perché la domanda ({euro(valore)}) supera la soglia di "
                  f"{euro(soglia)} delle somme «non eccedenti» dell'art. 3, comma 1, d.l. 132/2014.",
                  [Rif("dl132:3", "pagamento a qualsiasi titolo di somme non eccedenti")])]


def improcedibilita_rimedio() -> Punto:
    return Punto("Se la condizione di procedibilità manca, l'improcedibilità deve essere eccepita dal convenuto o rilevata "
                 "d'ufficio non oltre la prima udienza e il giudice assegna il termine per esperirla: non è una "
                 "decadenza, ma ritarda la causa.", [Rif("dlgs28:5", "non oltre la prima udienza"),
                                                    Rif("dl132:3", "non oltre la prima udienza")])


def rito_ordinario_o_semplificato(*, documentale: bool, monocratico: bool = True) -> list[Punto]:
    punti = [Punto("Rito ordinario di cognizione: citazione a udienza fissa, con termini a comparire non minori di "
                   "centoventi giorni e memorie integrative almeno quaranta, venti e dieci giorni prima dell'udienza.",
                   [Rif("cpc:163", "citazione a comparire a udienza fissa"), Rif("cpc:163bis", "centoventi giorni"),
                    Rif("cpc:171ter", "quaranta giorni prima dell'udienza")])]
    alternativa = Punto(
        "Rito semplificato di cognizione (ricorso): ammesso quando i fatti non sono controversi, la domanda è fondata "
        "su prova documentale, è di pronta soluzione o richiede un'istruzione non complessa; nelle cause in cui il "
        "tribunale giudica in composizione monocratica può sempre essere proposto.",
        [Rif("cpc:281decies", "fondata su prova documentale"), Rif("cpc:281undecies", "si propone con ricorso")]
        + ([Rif("cpc:281decies", "composizione monocratica")] if monocratico else []))
    punti.append(alternativa)
    return punti


@lru_cache(maxsize=1)
def _uffici() -> frozenset[str]:
    try:
        from pct.uffici_giudiziari import _build_bundle_completo

        return frozenset(u["nome"].lower() for u in _build_bundle_completo() if u.get("tipo") in {"TRIBUNALE", "GDP"})
    except Exception:
        return frozenset()


def ufficio(giudice: str, citta: str) -> str:
    """Ufficio competente per il comune: banca dati degli uffici per comune del Ministero (pct/uffici_competenti),
    che dà anche il circondario dei comuni che non sono sede (Modugno → Bari); in mancanza, il bundle dei 648 uffici."""
    if not citta:
        return giudice
    tipo = "giudice_pace" if giudice.lower().startswith("giudice di pace") else "tribunale"
    try:
        from pct.uffici_competenti import ricerca_uffici_competenti

        esito = ricerca_uffici_competenti(citta, timeout=4.0)
        uffici = [u for u in esito.get("offices", []) if u.get("kind") == tipo]
        if uffici:
            nome = str(uffici[0].get("name") or "")
            m = re.match(r"(?i)^(?:tribunale(?: ordinario)?|(?:ufficio del )?giudice di pace) di (.+)$", nome.strip())
            sede = m.group(1).title() if m else ""
            if sede.lower() == citta.lower():
                sede = citta
            base = "Giudice di pace" if tipo == "giudice_pace" else giudice
            if sede:
                return f"{base} di {sede}" + ("" if sede.lower() == citta.lower() else f" (competente per {citta})")
    except Exception:
        pass
    nome = (f"Ufficio del Giudice di Pace di {citta}" if tipo == "giudice_pace" else f"{giudice} di {citta}")
    if nome.lower() in _uffici():
        return nome.replace("Ufficio del Giudice di Pace", "Giudice di pace")
    return f"{giudice} nel cui circondario si trova {citta} [ufficio da verificare]"


def _calcolatore_competenza(valore: float, circolazione: bool) -> str:
    """Doppio controllo con il calcolatore della competenza per valore (pct/calcolatori/competenza_valore.py)."""
    try:
        from datetime import date

        from pct.calcolatori import competenza_valore

        esito = competenza_valore.calcola({"comp_materia": "danno_circolazione" if circolazione else "beni_mobili",
                                           "comp_valore": valore, "comp_data_introduzione": date.today().isoformat()})
        return str(esito.get("giudice_competente") or "")
    except Exception:
        return ""
