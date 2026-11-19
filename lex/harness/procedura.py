"""Passo 4 dell'harness: regole processuali deterministiche (valore, giudice, foro, procedibilità, rito).

Le soglie non sono scritte qui: il limite del giudice di pace si legge dal testo vigente dell'art. 7 c.p.c. e la soglia
della negoziazione assistita dall'art. 3 d.l. 132/2014. Se il testo non si legge, la regola si astiene.
"""
from __future__ import annotations

from .fatti import Fatti, euro
from .modello import Punto, Rif
from functools import lru_cache

from .norme import importo_in_lettere_dopo

# Materie dell'art. 5, comma 1, d.lgs. 28/2010 (mediazione obbligatoria): nome → parole letterali del testo vigente.
MATERIE_MEDIAZIONE = {
    "condominio": "condominio", "diritti reali": "diritti reali", "divisione": "divisione",
    "successioni ereditarie": "successioni ereditarie", "locazione": "locazione", "comodato": "comodato",
    "affitto di aziende": "affitto di aziende", "responsabilità medica e sanitaria": "responsabilita medica e sanitaria",
    "contratti assicurativi, bancari e finanziari": "contratti assicurativi, bancari e finanziari",
    "contratti di opera": "opera", "somministrazione": "somministrazione", "franchising": "franchising",
    "subfornitura": "subfornitura",
}


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
        return [Punto(f"Mediazione obbligatoria: la controversia in materia di {materia} rientra nell'elenco dell'art. 5, "
                      "comma 1, d.lgs. 28/2010; l'esperimento del procedimento di mediazione è condizione di "
                      "procedibilità della domanda.", [Rif("dlgs28:5", MATERIE_MEDIAZIONE[materia]),
                                                     Rif("dlgs28:5", "condizione di procedibilita")])]
    return [Punto("Mediazione: la domanda non rientra fra le materie dell'art. 5, comma 1, d.lgs. 28/2010 "
                  "(condominio, diritti reali, divisione, successioni, locazione, comodato, contratti bancari e "
                  "assicurativi e le altre elencate): non è condizione di procedibilità.",
                  [Rif("dlgs28:5", "diritti reali")])]


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
    """«Tribunale di Bari» solo se l'ufficio esiste nel bundle dei 648 uffici; altrimenti il circondario resta da verificare.

    Il comune del fatto («Modugno») non è sempre sede di tribunale: la geografia giudiziaria (d.lgs. 155/2012) decide il
    circondario, che qui non si indovina.
    """
    if not citta:
        return giudice
    nome = (f"Ufficio del Giudice di Pace di {citta}" if giudice.lower().startswith("giudice di pace")
            else f"{giudice} di {citta}")
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
