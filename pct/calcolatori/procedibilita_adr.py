"""Condizione di procedibilità: mediazione o negoziazione assistita.

Prima di iscrivere a ruolo bisogna sapere se la domanda è procedibile: la
mediazione e la negoziazione assistita sono condizioni di procedibilità in
materie diverse, con esclusioni diverse e termini diversi. L'improcedibilità è
rilevabile d'ufficio non oltre la prima udienza, quindi l'errore non si recupera
a piacimento.

Base normativa (testi verificati su Normattiva):

- **Art. 5, comma 1, D.Lgs. 28/2010**: elenca le materie in cui chi intende
  agire «è tenuto preliminarmente a esperire il procedimento di mediazione».
- **Art. 5, comma 2**: l'esperimento è condizione di procedibilità; l'eccezione
  è a pena di decadenza del convenuto o è rilevata d'ufficio non oltre la prima
  udienza.
- **Art. 5, comma 4**: la condizione si considera avverata se il primo incontro
  dinanzi al mediatore si conclude senza l'accordo di conciliazione.
- **Art. 5, comma 6**: elenca i procedimenti ai quali il comma 1 e l'art.
  5-quater non si applicano.
- **Art. 6 D.Lgs. 28/2010**: il procedimento di mediazione dura sei mesi,
  prorogabile per periodi non superiori a tre mesi; il termine non è soggetto a
  sospensione feriale e decorre dal deposito della domanda.
- **Art. 8, comma 1, D.Lgs. 28/2010**: il primo incontro si tiene non prima di
  venti e non oltre quaranta giorni dal deposito della domanda, salvo diversa
  concorde indicazione delle parti.
- **Art. 3, comma 1, D.L. 132/2014**: negoziazione assistita obbligatoria per le
  controversie in materia di risarcimento del danno da circolazione di veicoli e
  natanti e, fuori dalle materie a mediazione obbligatoria, per le domande di
  pagamento a qualsiasi titolo di somme non eccedenti cinquantamila euro; non si
  applica alle controversie su obbligazioni contrattuali derivanti da contratti
  conclusi tra professionisti e consumatori.
- **Art. 3, comma 2**: la condizione si considera avverata se l'invito non è
  seguito da adesione o è seguito da rifiuto entro trenta giorni dalla
  ricezione, ovvero quando è decorso il termine della convenzione.
- **Art. 3, comma 3**: procedimenti ai quali l'obbligo non si applica.
- **Art. 2, comma 2, lett. a), D.L. 132/2014**: il termine della convenzione non
  può essere inferiore a un mese né superiore a tre, prorogabile di trenta
  giorni su accordo delle parti.

Perimetro dichiarato: il modulo qualifica la controversia secondo la materia e
il procedimento indicati e ne ricava la condizione di procedibilità e i termini
di legge. Non sostituisce la qualificazione giuridica della domanda, che resta
dell'avvocato, e non copre le condizioni di procedibilità previste da discipline
speciali fuori dalle due qui trattate.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Mapping, Optional

from pct.calcolatori._base import clean_text, fmt_date_it, fmt_eur, parse_date, safe_float

# Art. 3, comma 1, secondo periodo, D.L. 132/2014.
SOGLIA_NEGOZIAZIONE = 50_000.0

# Art. 8, comma 1, D.Lgs. 28/2010: finestra del primo incontro.
PRIMO_INCONTRO_MIN_GIORNI = 20
PRIMO_INCONTRO_MAX_GIORNI = 40

# Art. 6, commi 1 e 3, D.Lgs. 28/2010: durata del procedimento di mediazione.
DURATA_MEDIAZIONE_MESI = 6
PROROGA_MEDIAZIONE_MESI = 3

# Art. 4, comma 1, e art. 3, comma 2, D.L. 132/2014: risposta all'invito.
GIORNI_RISPOSTA_INVITO = 30

# Materie dell'art. 5, comma 1, D.Lgs. 28/2010, nell'ordine del testo di legge.
MATERIE_MEDIAZIONE: Dict[str, str] = {
    "condominio": "Condominio",
    "diritti_reali": "Diritti reali",
    "divisione": "Divisione",
    "successioni": "Successioni ereditarie",
    "patti_famiglia": "Patti di famiglia",
    "locazione": "Locazione",
    "comodato": "Comodato",
    "affitto_aziende": "Affitto di aziende",
    "responsabilita_medica": "Risarcimento del danno da responsabilità medica e sanitaria",
    "diffamazione": "Risarcimento del danno da diffamazione con la stampa o altro mezzo di pubblicità",
    "contratti_assicurativi": "Contratti assicurativi",
    "contratti_bancari": "Contratti bancari",
    "contratti_finanziari": "Contratti finanziari",
    "associazione_partecipazione": "Associazione in partecipazione",
    "consorzio": "Consorzio",
    "franchising": "Franchising",
    "opera": "Contratto d'opera",
    "rete": "Contratto di rete",
    "somministrazione": "Somministrazione",
    "societa_persone": "Società di persone",
    "subfornitura": "Subfornitura",
}

# Materie che non rientrano nell'art. 5, comma 1, e vanno valutate sulla
# negoziazione assistita.
MATERIE_ALTRE: Dict[str, str] = {
    "circolazione": "Risarcimento del danno da circolazione di veicoli e natanti",
    "pagamento_somme": "Domanda di pagamento di somme a qualsiasi titolo",
    "altra": "Altra materia non soggetta a mediazione obbligatoria",
}

# Art. 5, comma 6, D.Lgs. 28/2010 ed art. 3, comma 3, D.L. 132/2014: le due
# norme escludono insiemi in parte diversi, e la differenza conta.
PROCEDIMENTI: Dict[str, Dict[str, Any]] = {
    "ordinario": {
        "label": "Giudizio ordinario di cognizione",
        "esclude_mediazione": False,
        "esclude_negoziazione": False,
        "limite": "",
    },
    "ingiunzione": {
        "label": "Procedimento per ingiunzione, inclusa l'opposizione",
        "esclude_mediazione": True,
        "esclude_negoziazione": True,
        "limite": "fino alla pronuncia sulle istanze di concessione e sospensione della provvisoria esecuzione (art. 5-bis D.Lgs. 28/2010)",
    },
    "sfratto": {
        "label": "Convalida di licenza o sfratto",
        "esclude_mediazione": True,
        "esclude_negoziazione": False,
        "limite": "fino al mutamento del rito ai sensi dell'art. 667 c.p.c.",
    },
    "ctp_696bis": {
        "label": "Consulenza tecnica preventiva ai fini della composizione della lite (art. 696-bis c.p.c.)",
        "esclude_mediazione": True,
        "esclude_negoziazione": True,
        "limite": "",
    },
    "possessorio": {
        "label": "Procedimento possessorio",
        "esclude_mediazione": True,
        "esclude_negoziazione": False,
        "limite": "fino alla pronuncia dei provvedimenti di cui all'art. 703, terzo comma, c.p.c.",
    },
    "opposizione_esecutiva": {
        "label": "Opposizione o procedimento incidentale di cognizione relativo all'esecuzione forzata",
        "esclude_mediazione": True,
        "esclude_negoziazione": True,
        "limite": "",
    },
    "camera_consiglio": {
        "label": "Procedimento in camera di consiglio",
        "esclude_mediazione": True,
        "esclude_negoziazione": True,
        "limite": "",
    },
    "azione_civile_penale": {
        "label": "Azione civile esercitata nel processo penale",
        "esclude_mediazione": True,
        "esclude_negoziazione": True,
        "limite": "",
    },
    "inibitoria_consumo": {
        "label": "Azione inibitoria ex artt. 37 e 140-octies codice del consumo",
        "esclude_mediazione": True,
        "esclude_negoziazione": False,
        "limite": "",
    },
}

FONTI: tuple[Dict[str, str], ...] = (
    {
        "title": "Art. 5 D.Lgs. 28/2010 — Condizione di procedibilità e rapporti con il processo",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2010-03-04;28~art5",
    },
    {
        "title": "Artt. 6 e 8 D.Lgs. 28/2010 — Durata e procedimento di mediazione",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2010-03-04;28~art6",
    },
    {
        "title": "Artt. 2, 3 e 4 D.L. 132/2014 — Negoziazione assistita e improcedibilità",
        "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legge:2014-09-12;132~art3",
    },
)


def _passaggi_mediazione(deposito: Optional[date]) -> List[Dict[str, str]]:
    """Finestra del primo incontro e durata, quando la domanda è già depositata."""
    if deposito is None:
        return []
    return [
        {"passaggio": "Deposito della domanda di mediazione", "data": fmt_date_it(deposito)},
        {
            "passaggio": f"Primo incontro: non prima di {PRIMO_INCONTRO_MIN_GIORNI} giorni (art. 8, comma 1)",
            "data": fmt_date_it(deposito + timedelta(days=PRIMO_INCONTRO_MIN_GIORNI)),
        },
        {
            "passaggio": f"Primo incontro: non oltre {PRIMO_INCONTRO_MAX_GIORNI} giorni (art. 8, comma 1)",
            "data": fmt_date_it(deposito + timedelta(days=PRIMO_INCONTRO_MAX_GIORNI)),
        },
        {
            "passaggio": f"Scadenza della durata di {DURATA_MEDIAZIONE_MESI} mesi (art. 6, commi 1 e 3)",
            "data": fmt_date_it(_aggiungi_mesi(deposito, DURATA_MEDIAZIONE_MESI)),
        },
    ]


def _aggiungi_mesi(partenza: date, mesi: int) -> date:
    """Stessa data del mese di arrivo, arretrata all'ultimo giorno se non esiste."""
    indice = partenza.month - 1 + mesi
    anno = partenza.year + indice // 12
    mese = indice % 12 + 1
    giorno = partenza.day
    while giorno > 0:
        try:
            return date(anno, mese, giorno)
        except ValueError:
            giorno -= 1
    return partenza


def _passaggi_negoziazione(invito: Optional[date]) -> List[Dict[str, str]]:
    if invito is None:
        return []
    return [
        {"passaggio": "Ricezione dell'invito a stipulare la convenzione", "data": fmt_date_it(invito)},
        {
            "passaggio": f"Termine per l'adesione: {GIORNI_RISPOSTA_INVITO} giorni dalla ricezione (art. 4, comma 1)",
            "data": fmt_date_it(invito + timedelta(days=GIORNI_RISPOSTA_INVITO)),
        },
        {
            "passaggio": "Durata minima della convenzione: un mese (art. 2, comma 2, lett. a)",
            "data": fmt_date_it(_aggiungi_mesi(invito, 1)),
        },
        {
            "passaggio": "Durata massima della convenzione: tre mesi, prorogabili di trenta giorni",
            "data": fmt_date_it(_aggiungi_mesi(invito, 3)),
        },
    ]


def _esito_mediazione(materia: str, procedimento: str) -> Dict[str, Any]:
    regola = PROCEDIMENTI[procedimento]
    if regola["esclude_mediazione"]:
        limite = f" {regola['limite']}" if regola["limite"] else ""
        return {
            "obbligatoria": False,
            "motivo": f"Il procedimento «{regola['label']}» è escluso dall'art. 5, comma 6, D.Lgs. 28/2010{limite}.",
        }
    return {
        "obbligatoria": True,
        "motivo": (
            f"La materia «{MATERIE_MEDIAZIONE[materia]}» è compresa nell'elenco dell'art. 5, "
            "comma 1, D.Lgs. 28/2010: l'esperimento della mediazione è condizione di procedibilità."
        ),
    }


def _esito_negoziazione(materia: str, procedimento: str, valore: float, consumatore: bool) -> Dict[str, Any]:
    regola = PROCEDIMENTI[procedimento]
    if regola["esclude_negoziazione"]:
        return {
            "obbligatoria": False,
            "motivo": f"Il procedimento «{regola['label']}» è escluso dall'art. 3, comma 3, D.L. 132/2014.",
        }
    if materia == "circolazione":
        return {
            "obbligatoria": True,
            "motivo": (
                "Risarcimento del danno da circolazione di veicoli e natanti: l'invito a stipulare "
                "la convenzione è condizione di procedibilità (art. 3, comma 1, primo periodo, "
                "D.L. 132/2014)."
            ),
        }
    if materia == "pagamento_somme":
        if consumatore:
            return {
                "obbligatoria": False,
                "motivo": (
                    "L'art. 3, comma 1, D.L. 132/2014 non si applica alle controversie su "
                    "obbligazioni contrattuali derivanti da contratti conclusi tra professionisti "
                    "e consumatori."
                ),
            }
        if valore <= 0:
            raise ValueError(
                "Indica l'importo domandato: la negoziazione assistita è obbligatoria per le "
                "domande di pagamento di somme non eccedenti cinquantamila euro."
            )
        if valore <= SOGLIA_NEGOZIAZIONE:
            return {
                "obbligatoria": True,
                "motivo": (
                    f"Domanda di pagamento di {fmt_eur(valore)} € non eccedente la soglia di "
                    f"{fmt_eur(SOGLIA_NEGOZIAZIONE, 0)} € (art. 3, comma 1, secondo periodo, D.L. 132/2014)."
                ),
            }
        return {
            "obbligatoria": False,
            "motivo": (
                f"La domanda eccede la soglia di {fmt_eur(SOGLIA_NEGOZIAZIONE, 0)} € dell'art. 3, "
                "comma 1, D.L. 132/2014: nessuna condizione di procedibilità per questa via."
            ),
        }
    return {
        "obbligatoria": False,
        "motivo": "La materia indicata non rientra fra quelle a negoziazione assistita obbligatoria.",
    }


def calcola(payload: Mapping[str, Any]) -> Dict[str, Any]:
    materia = clean_text(payload.get("adr_materia")).lower() or "condominio"
    if materia not in MATERIE_MEDIAZIONE and materia not in MATERIE_ALTRE:
        raise ValueError("Materia non riconosciuta.")
    procedimento = clean_text(payload.get("adr_procedimento")).lower() or "ordinario"
    if procedimento not in PROCEDIMENTI:
        raise ValueError("Tipo di procedimento non riconosciuto.")
    consumatore = clean_text(payload.get("adr_consumatore")).lower() in {"1", "si", "sì", "true"}
    valore = safe_float(payload.get("adr_valore"))

    if materia in MATERIE_MEDIAZIONE:
        esito = _esito_mediazione(materia, procedimento)
        strumento = "mediazione" if esito["obbligatoria"] else "nessuno"
        materia_label = MATERIE_MEDIAZIONE[materia]
    else:
        esito = _esito_negoziazione(materia, procedimento, valore, consumatore)
        strumento = "negoziazione" if esito["obbligatoria"] else "nessuno"
        materia_label = MATERIE_ALTRE[materia]

    deposito = parse_date(payload.get("adr_data_avvio"))
    passaggi = _passaggi_mediazione(deposito) if strumento == "mediazione" else (
        _passaggi_negoziazione(deposito) if strumento == "negoziazione" else []
    )

    note: List[str] = [esito["motivo"]]
    if strumento == "mediazione":
        note.extend(
            [
                "La condizione si considera avverata se il primo incontro dinanzi al mediatore si "
                "conclude senza l'accordo di conciliazione (art. 5, comma 4, D.Lgs. 28/2010).",
                f"Il procedimento dura {DURATA_MEDIAZIONE_MESI} mesi dal deposito della domanda, "
                f"prorogabile per periodi non superiori a {PROROGA_MEDIAZIONE_MESI} mesi; il termine "
                "non è soggetto a sospensione feriale (art. 6 D.Lgs. 28/2010).",
                "Dal momento in cui la comunicazione dell'organismo perviene alle parti la domanda "
                "produce sulla prescrizione gli effetti della domanda giudiziale e impedisce la "
                "decadenza per una sola volta (art. 8, comma 2, D.Lgs. 28/2010).",
            ]
        )
    elif strumento == "negoziazione":
        note.extend(
            [
                "La condizione si considera avverata se l'invito non è seguito da adesione o è "
                f"seguito da rifiuto entro {GIORNI_RISPOSTA_INVITO} giorni dalla ricezione, ovvero "
                "quando è decorso il termine della convenzione (art. 3, comma 2, D.L. 132/2014).",
                "Il termine della convenzione non può essere inferiore a un mese né superiore a "
                "tre, prorogabile di trenta giorni su accordo delle parti (art. 2, comma 2, lett. "
                "a, D.L. 132/2014).",
                "La mancata risposta all'invito entro trenta giorni o il suo rifiuto possono essere "
                "valutati dal giudice ai fini delle spese e degli artt. 96 e 642, primo comma, "
                "c.p.c. (art. 4, comma 1, D.L. 132/2014).",
            ]
        )
    else:
        note.append(
            "Nessuna condizione di procedibilità fra mediazione e negoziazione assistita per la "
            "combinazione indicata: resta possibile l'accesso volontario e la mediazione demandata "
            "dal giudice (art. 5-quater D.Lgs. 28/2010)."
        )

    if PROCEDIMENTI[procedimento]["limite"]:
        note.append(
            f"Esclusione limitata nel tempo: {PROCEDIMENTI[procedimento]['limite']}. Superato quel "
            "momento la condizione torna ad operare."
        )

    avvisi = [
        "L'improcedibilità è eccepita dal convenuto a pena di decadenza o rilevata d'ufficio dal "
        "giudice non oltre la prima udienza (art. 5, comma 2, D.Lgs. 28/2010; art. 3, comma 1, "
        "D.L. 132/2014).",
        "Lo svolgimento della mediazione non preclude i provvedimenti urgenti e cautelari né la "
        "trascrizione della domanda giudiziale (art. 5, comma 5, D.Lgs. 28/2010).",
        "La qualificazione della materia resta dell'avvocato: il modulo applica la regola alla "
        "materia dichiarata, non la ricava dai fatti di causa.",
    ]
    if materia in {"contratti_assicurativi", "contratti_bancari", "contratti_finanziari"}:
        avvisi.append(
            "Per queste materie la condizione può essere assolta anche con le procedure dell'art. "
            "5, comma 3, D.Lgs. 28/2010 (ABF, Arbitro per le controversie finanziarie, IVASS e "
            "organismi dei settori regolati)."
        )

    return {
        "materia": materia,
        "materia_label": materia_label,
        "procedimento": procedimento,
        "procedimento_label": PROCEDIMENTI[procedimento]["label"],
        "strumento": strumento,
        "strumento_label": {
            "mediazione": "Mediazione obbligatoria (D.Lgs. 28/2010)",
            "negoziazione": "Negoziazione assistita obbligatoria (D.L. 132/2014)",
            "nessuno": "Nessuna condizione di procedibilità",
        }[strumento],
        "condizione_procedibilita": strumento != "nessuno",
        "motivo": esito["motivo"],
        "valore": round(valore, 2) if valore > 0 else 0.0,
        "passaggi": passaggi,
        "notes": note,
        "warnings": avvisi,
        "sources": list(FONTI),
    }
