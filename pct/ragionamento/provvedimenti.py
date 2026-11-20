"""La lettura dei provvedimenti del giudice: udienze con la loro modalità, termini assegnati, ordini.

Come legge un avvocato:
1. nel provvedimento collettivo (più gruppi di numeri di ruolo) vale solo il periodo che nomina il nostro
   ruolo; le date degli altri gruppi non ci riguardano (G-2);
2. la data d'udienza si legge con la sua modalità nella stessa frase: in presenza, da remoto (art. 127-bis
   c.p.c.) o sostituita da note scritte (art. 127-ter c.p.c.); un'udienza dichiarata «non tenuta» o già
   tenuta non è un'udienza futura;
3. il termine si legge con l'adempimento, la parte onerata («a cura della creditrice», «il convenuto ha
   l'onere») e la perentorietà dichiarata («termine perentorio», «a pena di decadenza») o di legge (le note
   dell'art. 127-ter sono sempre in termine perentorio, secondo comma);
4. per le note scritte il termine è quello assegnato dal giudice, non la data dell'udienza sostituita (G-1);
5. un termine con data anteriore all'atto che lo assegna è un errore materiale, non un termine (G-11).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from pct.provvedimenti.collettivi import testo_per_il_ruolo
from pct.provvedimenti.termine_scritto import parte_dispositiva, rischio_estinzione

from .modello import Atto, Fonte, TermineAssegnato, Udienza
from .testo import date_nel_testo, frasi, giorno, pulito, semplice

_NUMERI = {"cinque": 5, "dieci": 10, "quindici": 15, "venti": 20, "trenta": 30, "quaranta": 40, "sessanta": 60, "novanta": 90}
_PARTE_ATTIVA = ("creditrice", "creditore", "procedente", "istante", "ricorrente", "attore", "attrice", "parte ricorrente")
_PARTE_PASSIVA = ("debitrice", "debitore", "convenuto", "convenuta", "resistente", "parte resistente", "esecutato")
_ORDINE_RINNOVAZIONE = re.compile(
    r"\b(?:dispone|ordina)\s+(?:procedersi\s+alla\s+|la\s+)?rinnovazione\s+della\s+notificazion[ei]\b",
)


@dataclass
class Ordine:
    """Un ordine del giudice che non porta una data: per esempio «sia notificato nei termini di legge»."""

    codice: str
    testo: str
    onerato: str
    fonte: Fonte


@dataclass
class LetturaProvvedimento:
    udienze: list[Udienza] = field(default_factory=list)
    termini: list[TermineAssegnato] = field(default_factory=list)
    ordini: list[Ordine] = field(default_factory=list)
    errori_materiali: list[tuple[str, Fonte]] = field(default_factory=list)
    collettivo: bool = False
    rischio: str = ""  # l'avviso di estinzione per diserzione delle parti, se il provvedimento lo dispone


def periodi_della_causa(testo: str, rg: str) -> tuple[list[str], bool]:
    """I periodi che riguardano il nostro ruolo; vero se il provvedimento è collettivo.

    Regola unica del software: `pct/provvedimenti/collettivi.testo_per_il_ruolo` oscura le clausole
    disposte per gli altri gruppi di cause (G-2); qui il testo rimasto si divide in periodi.
    """
    numero, _, anno = rg.partition("/")
    per_il_ruolo = testo_per_il_ruolo(testo, numero, anno) if numero and anno else testo
    # Nei PDF il cambio di capoverso può diventare uno spazio senza punteggiatura.
    per_il_ruolo = re.sub(
        r"(?<=[\w)]) +(?=(?:DISPONE|ASSEGNA|ORDINA)\b|(?:Dispone|Assegna|Ordina)\s+(?:che|alle|alla|al|il|la|un|termine)\b)",
        "\n ", per_il_ruolo,
    )
    periodi = [f for _p, f in frasi(per_il_ruolo) if f.strip()]
    return periodi, per_il_ruolo != testo


def _modalita(frase: str) -> str:
    # «Visto l'art. 127-ter c.p.c. …» in premessa non sostituisce l'udienza: conta la parte che dispone
    # (regola unica di pct/provvedimenti/termine_scritto.parte_dispositiva).
    s = semplice(parte_dispositiva(frase))
    if re.search(r"127[\s-]*ter|note scritte|trattazione scritta|scambio di note", s):
        return "note_scritte"
    if re.search(r"127[\s-]*bis|collegamento audiovisivo|da remoto", s):
        return "remota"
    return "presenza"


def _onerato(frase: str) -> str:
    s = semplice(frase)
    m = re.search(r"a cura (?:della|delle|dell'|dei|del)\s*([a-z ]{3,30})", s)
    soggetto = m.group(1) if m else ""
    if not soggetto:
        m = re.search(r"\b(il|la|i)\s+(convenut[oa]|resistente|terz[oi]|ricorrente|creditrice|creditore)\b[^.]{0,40}(onere|deve|devono|invita)", s)
        soggetto = m.group(2) if m else ""
    if not soggetto:
        m = re.search(r"(?:assegna|concede|onera|invita|avverte)\s+(?:a|alla|al|il|la)?\s*(?:parte\s+)?(ricorrente|resistente|convenut[oa]|attore|attrice|creditrice|creditore|debitrice|debitore|terz[oi])", s)
        soggetto = m.group(1) if m else ""
    if not soggetto and re.search(r"invita i terzi|il terzo", s):
        return "terzo"
    if any(soggetto.startswith(p) for p in _PARTE_ATTIVA):
        return "parte_attiva"
    if any(soggetto.startswith(p) for p in _PARTE_PASSIVA):
        return "parte_passiva"
    if soggetto.startswith("terz"):
        return "terzo"
    if _ORDINE_RINNOVAZIONE.search(s) and re.search(r"\bnei confronti della parte convenuta\b", s):
        return "parte_attiva"
    return ""


def _adempimento(frase: str) -> tuple[str, str]:
    """Il codice e il testo dell'adempimento scritto nella frase; ("", "") se la frase non lo dice."""
    s = semplice(frase)
    dispositiva = semplice(parte_dispositiva(frase))
    if re.search(r"127[\s-]*ter|note scritte|scambio di note", dispositiva) and re.search(r"deposit|sostitu|scambio", dispositiva):
        return "note_127ter", "Depositare le note scritte ex art. 127-ter c.p.c. (sole istanze e conclusioni)"
    if re.search(r"costituir|costituzione", s) and re.search(r"convenut|resistente", s):
        return "costituzione_convenuto", "Costituirsi in giudizio depositando la memoria difensiva"
    if _ORDINE_RINNOVAZIONE.search(s):
        return "notifica_ordinata", "Notificare nuovamente gli atti indicati nell'ordinanza"
    if re.search(r"sia(?:no)? notificat|venga(?:no)? notificat|si notifichi|notificarsi|\bnotificare\b|\bnotifichi\b", s):
        oggetto = re.search(r"(il presente provvedimento|il ricorso[^,;.]{0,40}decreto|il ricorso|il decreto|il provvedimento)", s)
        a_chi = re.search(r"\b(?:alla|al|ai|alle)\s+((?:debitrice|debitore|controparte|terz[oi]|convenut[oa]|resistente)[^,;.]{0,40})", s)
        cosa = oggetto.group(1) if oggetto else "il presente provvedimento"
        return "notifica_ordinata", f"Notificare {cosa}" + (f" {a_chi.group(0).strip()}" if a_chi else "")
    if re.search(r"per la notifica", s):
        dopo = s[s.index("per la notifica"):]
        cosa = re.search(r"(del ricorso[^,;.]{0,60}|del provvedimento|del decreto[^,;.]{0,40})", dopo)
        a_chi = re.search(r"\b(?:alla|al|ai|alle)\s+(parte\s+\w+|controparte|convenut[oa]|resistente)", dopo)
        oggetto = re.sub(r"^del ", "il ", cosa.group(1)).replace(" e del ", " e il ") if cosa else "l'atto indicato dal giudice"
        return "notifica_ordinata", f"Notificare {oggetto}" + (f" {a_chi.group(0)}" if a_chi else "")
    m = re.search(r"per depositare\s+([^;]{3,140}?)(?:;|$)", s) or re.search(r"deposit(?:are|o di|o del|o della|o dei|o delle)\s+([^,;.]{3,80}?)\s+(?:entro|nel termine)", s)
    if m:
        return "deposito_ordinato", f"Depositare {m.group(1).strip()}"
    if re.search(r"comunicare la dichiarazione", s):
        return "dichiarazione_terzo", "Dichiarazione del terzo (art. 547 c.p.c.)"
    return "", ""


def _ora(frase: str) -> str:
    m = re.search(r"ore\s+(\d{1,2})[.:,](\d{2})", frase, re.I)
    return f"{int(m.group(1)):02d}:{m.group(2)}" if m else ""


def _udienze(frase: str, data_atto: date | None) -> list[tuple[date, str]]:
    esito = []
    for inizio, fine, valore in date_nel_testo(frase):
        prima = semplice(frase[max(0, inizio - 45):inizio])
        dopo = semplice(frase[fine:fine + 40])
        if not re.search(r"udienz[ae]\b[^.]{0,35}(?:del|il|al|fissata per il)?\s*$|(?:rinvia|differisce)[a-z]*\b[^.]{0,55}\bal(?: giorno)?\s*$", prima):
            continue
        if re.search(r"non sar[aà] tenuta|tenuta dal|si e' svolta|celebrata", dopo) or re.search(r"(?:nel corso|in esito)\s+dell'udienza", prima):
            continue
        if data_atto and valore <= data_atto:
            continue
        esito.append((valore, _ora(frase[fine:fine + 30])))
    return esito


_RITROSO = re.compile(r"(?:almeno|fino a|sino a|entro e non oltre il termine di)\s+(\w+)\s+giorni prima dell?(?:a|')?\s*"
                      r"(?:prossima\s+)?(?:udienza|termine)")
# La parola che lega il «N giorni prima» al suo adempimento quando un periodo ne contiene più d'uno
# (caso reale RG 2691/2026: «costituirsi almeno 10 giorni prima» e «depositare, sino a cinque giorni prima, note»).
_PAROLE_DELL_ADEMPIMENTO = {"note_127ter": r"\bnote\b", "costituzione_convenuto": r"costitu"}


_DEPOSITO_NOTE = re.compile(r"deposit\w*[^.;]{0,80}\bnote\b|\bnote\b[^.;]{0,60}deposit")


def _ritroso(s: str, codice: str = "") -> re.Match | None:
    """Il «N giorni prima dell'udienza» dell'adempimento del periodo: la clausola (fra «;» o «.») che lo nomina."""
    trovati = list(_RITROSO.finditer(s))
    parola = _PAROLE_DELL_ADEMPIMENTO.get(codice)
    if not parola:
        return trovati[0] if trovati else None
    for m in trovati:
        # La clausola: dal «;», dal «.» di fine periodo o dal «*» precedenti al «;» o «.» seguenti («c.p.c.» non chiude).
        prima = re.sub(r"c\.p\.c\.|c\.c\.|artt?\.", lambda x: "_" * len(x.group(0)), s[:m.start()])
        dopo = re.sub(r"c\.p\.c\.|c\.c\.|artt?\.", lambda x: "_" * len(x.group(0)), s[m.end():])
        inizio = max(prima.rfind(";"), prima.rfind("."), prima.rfind("*")) + 1
        fine = min([i for i in (dopo.find(";"), dopo.find("."), dopo.find("*")) if i >= 0] or [len(dopo)])
        if re.search(parola, s[inizio:m.end() + fine]):
            return m
    # Il «N giorni prima» del periodo riguarda un altro adempimento (per esempio la costituzione del convenuto).
    return None


def _scadenze(frase: str, udienze: list[tuple[date, str]], codice: str = "") -> list[tuple[date, str, str]]:
    """(data, ora, come è scritta) dei termini con data nella frase.

    Il termine «almeno N giorni prima dell'udienza» porta qui la data grezza (udienza meno N giorni) e la
    formula «a ritroso:N:udienza»: il computo secondo l'art. 155 c.p.c. lo fanno le regole dei termini.
    """
    esito = []
    s = semplice(frase)
    for inizio, _fine, valore in date_nel_testo(frase):
        prima = semplice(frase[max(0, inizio - 50):inizio])
        if re.search(r"(entro(?: e non oltre)?(?: il)?|termine(?: perentorio)?(?: del| di| fino al| al)?|fino al|nel giorno)\s*$", prima):
            esito.append((valore, _ora(frase[inizio:inizio + 40]), "data scritta nel provvedimento"))
    if re.search(r"termine perentorio del giorno dell'udienza", s) and udienze:
        esito.append((udienze[0][0], _ora(frase) or udienze[0][1], "giorno dell'udienza fissata"))
    m = _ritroso(s, codice)
    if m and udienze and _numero(m.group(1)):
        giorni = _numero(m.group(1))
        esito.append((udienze[0][0] - timedelta(days=giorni), "", f"a_ritroso:{giorni}:{udienze[0][0].isoformat()}"))
    return esito


def _numero(parola: str) -> int:
    return int(parola) if parola.isdigit() else _NUMERI.get(parola, 0)


def _relativo(frase: str) -> str:
    """«termine di (ulteriori) dieci giorni, dalla comunicazione, per …»: la formula «da_comunicazione:N»."""
    m = re.search(r"termine di\s+(?:ulteriori\s+)?(\w+)\s+giorni(?:[^.;]{0,40}?dall?a?\s+(?:data di\s+)?(comunicazione|notific\w*))?", semplice(frase))
    if not m or not _numero(m.group(1)):
        return ""
    return f"da_{'notifica' if (m.group(2) or '').startswith('notific') else 'comunicazione'}:{_numero(m.group(1))}"


def _brano(contesto: str, valore: date) -> str:
    """Il brano che porta la data: fino a 250 caratteri prima e 120 dopo, non l'inizio del periodo."""
    for inizio, fine, letta in date_nel_testo(contesto):
        if letta == valore:
            return pulito(contesto[max(0, inizio - 250):fine + 120])
    return pulito(contesto)[:400]


def leggi_provvedimento(atto: Atto, rg: str) -> LetturaProvvedimento:
    lettura = LetturaProvvedimento()
    periodi, lettura.collettivo = periodi_della_causa(atto.testo, rg)
    data_atto = giorno(atto.data)
    udienze_atto: list[tuple[date, str]] = []
    for periodo in periodi:
        trovate = _udienze(periodo, data_atto)
        udienze_atto.extend(trovate)
        seguente = periodi[periodi.index(periodo) + 1] if periodi.index(periodo) + 1 < len(periodi) else ""
        # «Fissa l'udienza del 26.2.2026. Sostituisce l'udienza con il deposito di note scritte»: la modalità
        # può stare nel periodo che segue, se parla della sostituzione dell'udienza.
        modalita_fissata = re.search(r"sostitui|sostituit|l'udienza di cui sopra si terra", semplice(seguente))
        dove = periodo + (" " + seguente if modalita_fissata else "")
        for valore, ora in trovate:
            lettura.udienze.append(Udienza(valore.isoformat(), ora, _modalita(dove), Fonte(atto.id, atto.nome, pulito(dove)[:400], atto.data)))
    # Rinvio per diserzione delle parti: la prossima diserzione estingue il processo (artt. 631 e 181 c.p.c.),
    # regola unica di pct/provvedimenti/termine_scritto.rischio_estinzione.
    rischio = rischio_estinzione(atto.testo)
    norma_rischio = {"art. 631 c.p.c.": "cpc_631", "art. 181 c.p.c.": "cpc_181"}.get(rischio.norma, "") if rischio else ""
    lettura.rischio = rischio.avviso if rischio else ""
    if not udienze_atto:
        # Il giorno assegnato per le note vale come data d'udienza (art. 127-ter, comma 5).
        date_note = {
            valore for periodo in periodi if _adempimento(periodo)[0] == "note_127ter"
            for valore, _, _ in _scadenze(periodo, [])
        }
        if len(date_note) == 1:
            udienze_atto = [(next(iter(date_note)), "")]
    trattazione_scritta = any(_adempimento(p)[0] == "note_127ter" for p in periodi)
    for indice, periodo in enumerate(periodi):
        contesto = periodo + (" " + periodi[indice + 1] if norma_rischio and indice + 1 < len(periodi)
                              and re.search(r"631|181", periodi[indice + 1]) else "")
        fonte = Fonte(atto.id, atto.nome, pulito(contesto)[:400], atto.data)
        codice, testo = _adempimento(periodo)
        if not codice and trattazione_scritta and _DEPOSITO_NOTE.search(semplice(periodo)):
            # «INVITA le parti a depositare, sino a cinque giorni prima dell'udienza, coincise note»: nel provvedimento
            # che dispone la trattazione scritta è il termine per le note (art. 127-ter c.p.c.).
            codice, testo = "note_127ter", "Depositare le note scritte ex art. 127-ter c.p.c. (sole istanze e conclusioni)"
        scadenze = _scadenze(periodo, _udienze(periodo, data_atto) or udienze_atto, codice)
        onerato = "tutte_le_parti" if codice == "note_127ter" else _onerato(periodo)
        perentorio = codice == "note_127ter" or bool(re.search(r"perentori|a pena di decadenza", semplice(periodo)))
        if not codice and not re.search(r"\b(assegna|fissa|concede|dispone|ordina|onera)\b|termine perentorio", semplice(periodo)):
            scadenze = []  # una data «entro il …» senza un ordine del giudice non è un termine assegnato
        for valore, ora, come in scadenze:
            fonte_data = Fonte(atto.id, atto.nome, _brano(contesto, valore), atto.data)
            if data_atto and valore < data_atto:
                lettura.errori_materiali.append((valore.isoformat(), fonte_data))
                continue
            lettura.termini.append(TermineAssegnato(
                scadenza=valore.isoformat(), adempimento=testo or codice, onerato=onerato or "ignoto", perentorio=perentorio,
                fonte=fonte_data, norme=(["cpc_127ter_testo"] + ([norma_rischio] if norma_rischio else [])
                   if codice == "note_127ter" else ["cpc_291"] if _ORDINE_RINNOVAZIONE.search(semplice(periodo)) else []),
                conseguenza=come if not come.startswith("a_ritroso") else "termine a ritroso dall'udienza", ora=ora,
                formula=come if come.startswith("a_ritroso") else "data",
            ))
        relativo = "" if scadenze or not codice else _relativo(periodo)
        if relativo:
            lettura.termini.append(TermineAssegnato(
                scadenza="", adempimento=testo or codice, onerato=onerato or "ignoto", perentorio=perentorio, fonte=fonte,
                conseguenza="termine a giorni dalla comunicazione del provvedimento", formula=relativo,
            ))
        elif codice == "notifica_ordinata" and not scadenze:
            lettura.ordini.append(Ordine(codice, testo, onerato or "ignoto", fonte))
    # La data del differimento e il termine per le note possono stare in periodi distinti.
    contesto = " ".join(periodi)
    sostituzione = re.search(r"\budienza\s+(?:sia\s+)?sostituita\s+dal\s+deposito\s+di\s+note\s+scritte", semplice(contesto))
    assegnazione = re.search(
        r"termine perentorio sino alla data della predetta udienza"
        r"|entro le ore\s+\d{1,2}[.:,]\d{2}\s+della data in cui si terra la suddetta udienza",
        semplice(contesto),
    )
    if sostituzione and assegnazione and not any(t.adempimento.startswith("Depositare le note") for t in lettura.termini):
        date_udienza = {d for d, _ in udienze_atto}
        if len(date_udienza) == 1:
            data = next(iter(date_udienza))
            ore = {ora for periodo in periodi if re.search(
                r"deposito delle note entro le ore.{0,16}del giorno di scadenza", semplice(periodo))
                and (ora := _ora(periodo))}
            ora = _ora(assegnazione.group(0)) or (next(iter(ore)) if len(ore) == 1 else "")
            brano = next((periodo for periodo in periodi if _udienze(periodo, data_atto)), "")
            fonte = Fonte(atto.id, atto.nome, pulito(brano + " " + assegnazione.group(0))[:400], atto.data)
            _, adempimento = _adempimento("deposito di note scritte")
            lettura.termini.append(TermineAssegnato(
                scadenza=data.isoformat(), adempimento=adempimento, onerato="tutte_le_parti",
                perentorio=True, fonte=fonte, norme=["cpc_127ter_testo"], ora=ora, formula="data",
            ))
            for udienza in lettura.udienze:
                if udienza.data == data.isoformat():
                    udienza.modalita = "note_scritte"
    return lettura


__all__ = ["LetturaProvvedimento", "Ordine", "leggi_provvedimento", "periodi_della_causa"]
