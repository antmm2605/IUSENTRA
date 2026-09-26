"""Le parti del procedimento lette nell'epigrafe degli atti: chi agisce, contro chi, con quali difensori.

Ogni atto introduttivo, memoria o provvedimento apre con l'epigrafe: le parti
con i loro dati (art. 163 c.p.c. per la citazione, art. 125 c.p.c. per gli atti
di parte, art. 40 c.p.a. per il ricorso amministrativo, art. 132 c.p.c. per la
sentenza) e il difensore con la procura. Da lì si legge:

- **chi è assistito dallo studio**: la parte «rappresentata e difesa» da un
  avvocato dello studio (il criterio certo) o, in mancanza, quella che porta
  il nome del cliente del fascicolo;
- **le controparti** e i loro difensori (compresa l'Avvocatura dello Stato,
  art. 1 R.D. 1611/1933, e i funzionari ex art. 417-bis c.p.c.);
- **testimoni** indicati nei capitoli di prova (art. 244 c.p.c.) e **CTU**
  nominati (art. 191 c.p.c.).

Il codice fiscale, quando c'è, si verifica con il carattere di controllo
(D.M. 23/12/1976): un nome con codice valido è un dato certo, gli altri sono
proposte da confermare. Nessuna parte si inventa: ogni voce porta la frase
del documento da cui viene.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from pct.registro_letture.fatti_repository import Fatto

VERSIONE_ESTRAZIONE_PARTI = "2026.09.26.parti-v2-lato"
_CF = re.compile(r"\b([A-Z]{3}\s?[A-Z]{3}\s?\d{2}[A-Z]\d{2}\s?[A-Z]\d{3}[A-Z])\b")
_PIVA_ENTE = re.compile(r"\b(?:c\.?\s*f\.?|p\.?\s*iva|codice\s+fiscale)\s*:?\s*(\d{11})\b", re.IGNORECASE)
# Un nome sta su una riga: le intestazioni sopra l'epigrafe non vi si attaccano.
_NOME = r"[A-ZÀ-Ü][\w'’À-ÿ.]+(?:[ \t]+(?:de|di|del|della|dello|dei|degli|la|lo|d['’])?[ \t]*[A-ZÀ-Ü][\w'’À-ÿ.]+){1,4}"
# Parole che non stanno mai nel nome di una parte: intestazioni, titoli dell'atto, uffici.
_NON_NOME = re.compile(
    r"\b(?:studio|legale|avvocat\w*|avv|tribunale|corte|giudice|sezione|atto|citazione|ricorso|memoria|comparsa|"
    r"sentenza|ordinanza|decreto|repubblica|italiana|popolo|nome|reg|ric|oggetto|procura|udienza)\b",
    re.IGNORECASE,
)
# Il nome del difensore può andare a capo dopo «Avv.»: qui il nome attraversa la riga.
_NOME_DIFENSORE = r"[A-ZÀ-Ü][\w'’À-ÿ.]+(?:\s+(?:de|di|del|della|d['’])?\s*[A-ZÀ-Ü][\w'’À-ÿ.]+){1,3}"
_DIFENSORE = re.compile(
    rf"rappresentat[oaie]\s*,?\s+(?:e\s+)?difes[oaie].{{0,160}}?\bdall?[’']?\s*(?:avv(?:ocat[oa])?\.?|avv\.ti|avvocati)\s+({_NOME_DIFENSORE})",
    re.IGNORECASE | re.DOTALL,
)
_AVVOCATURA = re.compile(r"\b(avvocatura\s+(?:distrettuale\s+)?(?:generale\s+)?d(?:ello|i)\s+stato(?:\s+di\s+[A-ZÀ-Ü][\w'’]+(?:\s+[A-ZÀ-Ü][\w'’]+)?)?)", re.IGNORECASE)
_FINE_EPIGRAFE = re.compile(
    r"\n\s*(?:premesso|in\s+fatto|fatto\s+e\s+diritto|svolgimento\s+del\s+processo|motivi|considerato|con\s+(?:il\s+)?ricorso|"
    r"\*{3,}|visti\s+gli\s+atti|oggetto\s*:)", re.IGNORECASE,
)
_PER = re.compile(r"(?:(?:^|\n)\s*(?:per|nell['’]interesse\s+d[ie]l?l?[ao]?)\s*:?\s*(?=\S)|\b(?:proposto|promosso|proposta|promossa)\s+da\s+)", re.IGNORECASE)
_CONTRO = re.compile(r"(?:\bcontro\b|\bnei\s+confronti\s+d[ie]l?l?[ao]?\b|\bavverso\b)\s*:?", re.IGNORECASE)
_ENTE = re.compile(
    r"\b((?:MINISTERO|Ministero|AGENZIA|Agenzia|COMUNE|Comune|REGIONE|Regione|PROVINCIA|Provincia|INPS|Inps|INAIL|Inail|"
    r"ISTITUTO|Istituto|UFFICIO\s+SCOLASTICO|Ufficio\s+Scolastico|AZIENDA|Azienda|UNIVERSIT[AÀ]|Universit[aà])"
    r"[^,;\n(]{0,110})"
)
_TESTI = re.compile(
    r"(?:si\s+indica(?:no)?|indica(?:no)?|chied\w+\s+(?:di\s+essere\s+)?ammess\w+\s+a\s+provare.{0,300}?)\s+(?:a|quali|come)\s+testi(?:moni)?\s*:?\s*(.{5,600}?)(?:\n\s*\n|$)",
    re.IGNORECASE | re.DOTALL,
)
_PERSONA_TESTE = re.compile(rf"(?:\b(?:il\s+)?sig\.?(?:ra)?|\bla\s+sig\.?ra|\bdott\.?(?:ssa)?|\bing\.?|\bgeom\.?|\barch\.?|\bprof\.?(?:ssa)?)\s+({_NOME})")
_CTU = re.compile(
    rf"(?:nomin\w+|nominat\w+)\s+(?:quale\s+|come\s+)?(?:c\.?\s*t\.?\s*u\.?|consulente\s+tecnico\s+d['’]ufficio)\s*,?\s*(?:il|la)?\s*"
    rf"(?:dott\.?(?:ssa)?|ing\.?|arch\.?|geom\.?|prof\.?(?:ssa)?|rag\.?)?\s*({_NOME})",
    re.IGNORECASE,
)
_RUOLI_PROCESSUALI = re.compile(
    r"\b(ricorrent[ei]|resistent[ei]|attor[ei]|attrice|convenut[oaie]|appellant[ei]|appellat[oaie]|opponent[ei]|oppost[oaie]|"
    r"reclamant[ei]|reclamat[oaie]|intervenut[oaie]|terz[oaie]\s+chiamat[oaie]|controinteressat[oaie]|creditor[ei]|debitor[ei])\b",
    re.IGNORECASE,
)


@dataclass
class ParteLetta:
    nome: str
    ruolo: str  # assistito | controparte | difensore_controparte | difensore_assistito | testimone | ctu
    codice_fiscale: str = ""
    posizione: str = ""
    difensore: str = ""
    citazione: str = ""
    prove: list[dict[str, str]] = field(default_factory=list)
    # «agisce» (dopo PER, chi propone l'atto o la domanda) o «resiste» (dopo CONTRO / CITA)
    lato_atto: str = ""


def _semplice(testo: str) -> str:
    base = unicodedata.normalize("NFKD", str(testo or "")).encode("ascii", "ignore").decode().casefold()
    return re.sub(r"[^a-z0-9]+", " ", base).strip()


def cf_valido(cf: str) -> bool:
    codice = re.sub(r"\s+", "", str(cf or "")).upper()
    if not re.fullmatch(r"[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]", codice):
        return False
    try:
        from pct.codice_fiscale import _checksum

        return _checksum(codice[:15]) == codice[15]
    except Exception:
        return False


_TITOLI = re.compile(r"^(?:il|la|lo|i|le|gli|sig\.?(?:ra)?|prof\.?(?:ssa)?|dott\.?(?:ssa)?|ing\.?|avv\.?|geom\.?|arch\.?)\s+", re.IGNORECASE)
_CODA_RUOLO = re.compile(r"\s+(?:ricorrent\w*|resistent\w*|attor\w*|attrice|convenut\w*|appell\w*|oppon\w*|oppost\w*|intervenut\w*|terz\w*)$", re.IGNORECASE)


def _pulisci_nome(nome: str) -> str:
    nome = re.split(r",|\bc\.?\s*f\.?\b|\bnat[oa]\b|\bin\s+persona\b|\bcon\s+sede\b|\bresident\w*\b|\(", nome, maxsplit=1, flags=re.IGNORECASE)[0]
    nome = " ".join(nome.split())
    precedente = None
    while precedente != nome:
        precedente, nome = nome, _TITOLI.sub("", nome).strip()
    nome = _CODA_RUOLO.sub("", nome)
    return nome.strip(" .;:-")


def _epigrafe(testo: str) -> str:
    zona = str(testo or "")[:7000]
    fine = _FINE_EPIGRAFE.search(zona, 200)
    return zona[: fine.start()] if fine else zona[:4500]


def _blocchi(epigrafe: str, epigrafe_completa: dict[str, str] | None = None) -> list[tuple[str, str]]:
    """[(lato, testo)] con lato «a» (chi agisce, dopo PER) e «b» (dopo CONTRO o CITA)."""
    epigrafe_completa = epigrafe_completa or {}
    blocchi: list[tuple[str, str]] = []
    contro = _CONTRO.search(epigrafe)
    per = _PER.search(epigrafe)
    if not contro:
        # Atto di citazione: «… CITA(NO) X … a comparire» (art. 163 c.p.c.).
        cita = re.search(r"\bcita(?:no)?\b\s*:?\s*(.{5,500}?)\ba\s+comparire\b", epigrafe_completa.get("testo", ""), re.IGNORECASE | re.DOTALL)
        if cita:
            return [("a", epigrafe[per.end():] if per else epigrafe), ("b", cita.group(1))]
    if contro:
        prima, dopo = epigrafe[: contro.start()], epigrafe[contro.end():]
        if per and per.start() < contro.start():
            prima = prima[per.end():]
        blocchi.append(("a", prima))
        seconda_fine = re.search(r"\b(?:per\s+l['’]?\s*(?:annullamento|esecuzione|ottemperanza|accertamento|condanna)|per\s+(?:la|il)\s+riforma|in\s+punto\b)", dopo, re.IGNORECASE)
        blocchi.append(("b", dopo[: seconda_fine.start()] if seconda_fine else dopo[:1800]))
    return blocchi


_ANCORA_PERSONA = re.compile(
    rf"({_NOME})\s*,\s*(?:c\.?\s*f\.?|nat[oa]\b|codice\s+fiscale)"
    rf"|({_NOME}(?:[ \t]+e[ \t]+{_NOME})*)\s*,\s*(?:entramb\w+\s+)?rappresentat"
)


def _parte_del_blocco(lato: str, blocco: str) -> list[ParteLetta]:
    """Una o più parti dello stesso lato: ognuna parte dal suo nome, con i suoi dati e il suo difensore."""
    ancore: list[tuple[int, str]] = []
    for m in _ANCORA_PERSONA.finditer(blocco[:2500]):
        if m.group(1):
            ancore.append((m.start(1), m.group(1)))
            continue
        # «Tizio e Caio, rappresentati…»: una voce per ciascuno, con il difensore comune.
        for nome in re.finditer(_NOME, m.group(2)):
            ancore.append((m.start(2) + nome.start(), nome.group(0)))
    for m in _ENTE.finditer(blocco[:1500]):
        prima = blocco[max(0, m.start() - 60):m.start()].casefold()
        if "difes" in prima or "domicil" in prima:
            continue
        # «MINISTERO DELL'ISTRUZIONE E DEL MERITO, c.f.»: il nome dell'ente prevale
        # sul pezzo che sembra un nome di persona dentro la sua denominazione.
        ancore = [(a, n) for a, n in ancore if not (m.start() <= a < m.end())]
        if not any(abs(m.start() - a) < 40 for a, _ in ancore):
            ancore.append((m.start(), m.group(1)))
    ancore.sort()
    if not ancore:
        # «Tizio e Caio, rappresentati e difesi…»: più persone nominate insieme in testa al blocco.
        iniziale = re.search(rf"{_NOME}(?:[ \t]+e[ \t]+{_NOME})*", blocco[:300])
        if iniziale:
            ancore = []
            for pezzo in re.finditer(_NOME, iniziale.group(0)):
                if pezzo.group(0).strip():
                    ancore.append((iniziale.start() + pezzo.start(), pezzo.group(0)))
    difensore_comune = ""
    parti: list[ParteLetta] = []
    for indice, (inizio, nome_grezzo) in enumerate(ancore[:6]):
        fine = ancore[indice + 1][0] if indice + 1 < len(ancore) else len(blocco)
        pezzo = blocco[inizio:fine]
        nome = _pulisci_nome(nome_grezzo)
        ente = bool(_ENTE.match(nome))
        if len(nome) < 4 or (not ente and _NON_NOME.search(nome)) or any(_semplice(p.nome) == _semplice(nome) for p in parti):
            continue
        difensore = _DIFENSORE.search(pezzo)
        avvocatura = _AVVOCATURA.search(pezzo)
        nome_difensore = _pulisci_nome(difensore.group(1)) if difensore else (" ".join(avvocatura.group(1).split()) if avvocatura else "")
        if nome_difensore and re.search(r"\b(?:entramb\w|tutt\w|congiuntamente)\b", pezzo[:difensore.start() if difensore else len(pezzo)], re.IGNORECASE):
            difensore_comune = nome_difensore
        dati = pezzo[: difensore.start()] if difensore else pezzo
        cf = _CF.search(dati.upper())
        partita = _PIVA_ENTE.search(dati)
        posizione = _RUOLI_PROCESSUALI.search(pezzo)
        parti.append(ParteLetta(
            nome=nome, ruolo=lato,
            codice_fiscale=re.sub(r"\s+", "", cf.group(1)) if cf else (partita.group(1) if partita else ""),
            posizione=posizione.group(1).lower() if posizione else "", difensore=nome_difensore,
            citazione=" ".join(pezzo.strip()[:220].split()),
        ))
    for parte in parti:
        parte.difensore = parte.difensore or difensore_comune
    if len(parti) > 1 and not any(p.difensore for p in parti[:-1]) and parti[-1].difensore:
        for parte in parti[:-1]:
            parte.difensore = parti[-1].difensore
    return parti


def _e_dello_studio(difensore: str, avvocati_studio: list[str]) -> bool:
    nome = _semplice(difensore)
    return bool(nome) and any(
        set(_semplice(avvocato).split()) <= set(nome.split()) or set(nome.split()) <= set(_semplice(avvocato).split())
        for avvocato in avvocati_studio if _semplice(avvocato)
    )


def _dal_cliente(nome: str, cliente: str) -> bool:
    parole = set(_semplice(cliente).split())
    return len(parole) >= 2 and parole <= set(_semplice(nome).split())


def estrai_parti(testo: str, *, avvocati_studio: list[str] | None = None, cliente: str = "") -> list[ParteLetta]:
    """Le parti dell'epigrafe, con il lato dello studio riconosciuto dal difensore o dal nome del cliente."""
    avvocati = [a for a in (avvocati_studio or []) if str(a or "").strip()]
    epigrafe = _epigrafe(testo)
    lette: list[ParteLetta] = []
    for lato, blocco in _blocchi(epigrafe, {"testo": str(testo or "")[:12000]}):
        lette.extend(_parte_del_blocco(lato, blocco))
    # Memorie di costituzione: «X … Resistente contro Y … Ricorrente» — il lato
    # si decide comunque dal difensore, non dall'ordine.
    lato_studio = next((p.ruolo for p in lette if _e_dello_studio(p.difensore, avvocati)), "")
    if not lato_studio:
        lato_studio = next((p.ruolo for p in lette if _dal_cliente(p.nome, cliente)), "")
    esito: list[ParteLetta] = []
    visti: set[tuple[str, str]] = set()

    def _aggiungi(parte: ParteLetta) -> None:
        chiave = (_semplice(parte.nome), parte.ruolo)
        if chiave not in visti:
            visti.add(chiave)
            esito.append(parte)

    for parte in lette:
        parte.lato_atto = "agisce" if parte.ruolo == "a" else "resiste" if parte.ruolo == "b" else ""
        if not lato_studio:
            parte.ruolo = "parte"
        else:
            parte.ruolo = "assistito" if parte.ruolo == lato_studio else "controparte"
        _aggiungi(parte)
        if parte.ruolo == "controparte" and parte.difensore:
            _aggiungi(ParteLetta(nome=parte.difensore, ruolo="difensore_controparte", citazione=parte.citazione,
                                 posizione=f"difensore di {parte.nome}"))
    for trovato in _TESTI.finditer(str(testo or "")[:40000]):
        for teste in _PERSONA_TESTE.finditer(trovato.group(1)):
            nome = _pulisci_nome(teste.group(1))
            if nome and not any(p.nome == nome for p in esito):
                esito.append(ParteLetta(nome=nome, ruolo="testimone", citazione=" ".join(trovato.group(0)[:200].split())))
    for trovato in _CTU.finditer(str(testo or "")[:40000]):
        nome = _pulisci_nome(trovato.group(1))
        if nome and not any(p.nome == nome and p.ruolo == "ctu" for p in esito):
            esito.append(ParteLetta(nome=nome, ruolo="ctu", citazione=" ".join(trovato.group(0)[:200].split())))
    return esito


def fatti_parti(testo: str, *, origine: str, avvocati_studio: list[str] | None = None, cliente: str = "") -> list[Fatto]:
    """Le parti come fatti dell'archivio (categoria «parte»): verificate se il codice fiscale è valido."""
    fatti: list[Fatto] = []
    for posizione, parte in enumerate(estrai_parti(testo, avvocati_studio=avvocati_studio, cliente=cliente)):
        prove = [{"codice": "epigrafe", "esito": "ok", "dettaglio": parte.citazione[:200]}]
        if parte.codice_fiscale:
            valido = cf_valido(parte.codice_fiscale)
            prove.append({"codice": "codice_fiscale", "esito": "ok" if valido else "attenzione",
                          "dettaglio": f"{parte.codice_fiscale} ({'carattere di controllo valido' if valido else 'carattere di controllo non valido'})"})
        if parte.difensore:
            prove.append({"codice": "difensore", "esito": "ok", "dettaglio": parte.difensore})
        if parte.posizione:
            prove.append({"codice": "posizione", "esito": "ok", "dettaglio": parte.posizione})
        if parte.lato_atto:
            prove.append({"codice": "lato", "esito": "ok", "dettaglio": parte.lato_atto})
        verificata = parte.ruolo in {"assistito", "controparte", "difensore_controparte"} and (
            (bool(parte.codice_fiscale) and cf_valido(parte.codice_fiscale)) or parte.ruolo == "difensore_controparte"
        )
        fatti.append(Fatto(
            categoria="parte", campo=parte.ruolo, valore=parte.nome, valore_letto=parte.codice_fiscale or parte.nome,
            etichetta=f"{parte.ruolo.replace('_', ' ').capitalize()}: {parte.nome}", contesto=parte.citazione,
            posizione=posizione, origine=origine, confidenza=0.95 if verificata else 0.7,
            verifica="verificata" if verificata else "plausibile", prove=prove,
        ))
    return fatti


__all__ = ["ParteLetta", "VERSIONE_ESTRAZIONE_PARTI", "cf_valido", "estrai_parti", "fatti_parti"]
