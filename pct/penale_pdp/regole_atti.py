"""Regole del PDP che le tabelle codificate del portale non contengono.

Fonte: manuale utente del Portale Deposito atti Penali (area riservata PST,
consultato il 25/09/2026) — pagine «Depositi», «Deposito atti successivi» e
schede dei singoli atti — e il menu «Depositi» del portale (versione
6.11.10). Le chiavi sono i codici tipo atto del PDP (``codificati/tipi-atto``);
ogni regola cita la pagina del manuale da cui viene.
"""

from __future__ import annotations

from dataclasses import dataclass

FONTE_MANUALE = "Manuale utente PDP (servizipst.giustizia.it/PST/PAVVP), consultato il 25/09/2026"


@dataclass(frozen=True)
class Campo:
    """Un dato che la maschera del PDP chiede per quell'atto."""

    chiave: str
    etichetta: str
    tipo: str = "testo"  # testo | scelta | numero | importo | si_no | anagrafica
    obbligatorio: bool = True
    opzioni: tuple[str, ...] = ()
    nota: str = ""


@dataclass(frozen=True)
class RegolaAtto:
    campi: tuple[Campo, ...] = ()
    procura_speciale: str = ""  # "" | "spunta" | "nomina_o_procura"
    un_solo_soggetto: bool = False
    fonte: str = FONTE_MANUALE


# Menu «Depositi» del PDP: atti che non richiedono il procedimento autorizzato.
PRINCIPALI: tuple[tuple[str, str], ...] = (
    ("P02", "Nomina Difensore/Legale"),
    ("P10", "Costituzione Parte Civile"),
    ("P26", "Costituzione Responsabile Civile"),
    ("P30", "Costituzione Civilmente Obbligato"),
    ("P27", "Intervento Responsabile Civile"),
    ("PBT", "Intervento di ente esponenziale"),
    ("R24", "Denuncia"),
    ("R25", "Querela"),
    ("R23", "Istanza Procedimento"),
    ("R26", "Integrazione denuncia, querela o istanza"),
    ("PB9", "Rescissione del giudicato"),
    ("PB8", "Revisione"),
    ("PAD", "Riparazione per ingiusta detenzione"),
    ("PCS", "Riparazione dell'errore giudiziario"),
    ("PB2", "Riesame: appello misura personale"),
    ("PB4", "Riesame: appello cautelare reale"),
    ("PAO", "Riesame: ricorso Cassazione ordinanza personale"),
    ("PB5", "Riesame: ricorso Cassazione ordinanza reale"),
    ("PB6", "Riesame personale"),
    ("PB7", "Riesame reale"),
    ("PCB", "Riesame reale terzo interessato"),
    ("C335", "Richiesta certificato ex art. 335 cpp"),
)
# Atti del menu che non sono nelle tabelle dei tipi atto: uffici e ruoli dal manuale.
FUORI_TABELLA: dict[str, tuple[str, tuple[str, ...], tuple[str, ...]]] = {
    "R24": ("Denuncia del privato (art. 333 cpp)", ("PM-U", "PM-G"), ("OFF",)),
    "R25": ("Querela (art. 336 cpp)", ("PM-U", "PM-G"), ("OFF",)),
    "R23": ("Istanza di Procedimento (art. 341 cpp)", ("PM-U", "PM-G"), ("OFF",)),
    "R26": ("Integrazione Denuncia/Querela/Istanza Procedimento", ("PM-U", "PM-G"), ("OFF",)),
    "C335": ("Richiesta certificato ex art. 335 cpp", ("PM-U",), ("OFF", "IND")),
}
NOMINE = frozenset({"P02", "P49"})

_IMPUGNAZIONE = (
    Campo("tipo_impugnazione", "Tipo impugnazione", "scelta", opzioni=("Appello", "Ricorso per Cassazione")),
    Campo("numero_sentenza", "Numero sentenza"),
    Campo("anno_sentenza", "Anno sentenza", "numero"),
)
_DOMICILIO = Campo("domicilio", "Domicilio di ogni soggetto (o «presso il legale»)")
_DENUNCIA = (
    Campo("urgente", "Urgente", "si_no", obbligatorio=False),
    Campo("violenza_genere", "Violenza di genere", "si_no", obbligatorio=False,
          nota="Se sì, il PDP chiede luogo, figli, armi e rapporto autore-vittima."),
    Campo("eppo", "Reato di competenza della Procura europea (EPPO)", "si_no", obbligatorio=False),
)

REGOLE: dict[str, RegolaAtto] = {
    "P18": RegolaAtto(campi=(
        Campo("tipo_pena", "Tipo pena", "scelta", opzioni=("Reclusione", "Arresto")),
        Campo("anni", "Anni", "numero", obbligatorio=False),
        Campo("mesi", "Mesi", "numero", obbligatorio=False),
        Campo("giorni", "Giorni", "numero", obbligatorio=False, nota="Almeno uno fra anni, mesi e giorni."),
        Campo("pena_pecuniaria", "Pena pecuniaria", "scelta", obbligatorio=False, opzioni=("Multa", "Ammenda"),
              nota="Con la reclusione solo multa, con l'arresto solo ammenda."),
        Campo("importo", "Importo (euro)", "importo", obbligatorio=False, nota="Obbligatorio se c'è la pena pecuniaria."),
        Campo("sospensione_condizionale", "Sospensione condizionale della pena", "si_no", obbligatorio=False),
    ), fonte="Atti successivi/Istanza patteggiamento.htm"),
    "P19": RegolaAtto(campi=(
        Campo("tipo_oblazione", "Tipo di oblazione", "scelta", opzioni=("art. 162 c.p.", "art. 162-bis c.p.")),
        Campo("importo", "Ammenda proposta (euro)", "importo", obbligatorio=False),
    ), fonte="Atti successivi/Istanza oblazione.htm"),
    "P17": RegolaAtto(campi=(Campo("tipo_abbreviato", "Tipo di giudizio abbreviato", "scelta", opzioni=("Semplice", "Condizionato")),),
                      fonte="Atti successivi/Istanza giudizio abbreviato.htm"),
    "P33": RegolaAtto(campi=(Campo("istanza_interrogatorio", "Contiene istanza di interrogatorio", "si_no"),),
                      fonte="Atti successivi/Memorie e istanze (art. 415 bis cpp).htm"),
    "P36": RegolaAtto(campi=(Campo("consulente", "Consulente tecnico (cognome, nome, codice fiscale)", "anagrafica"),),
                      fonte="Atti successivi/Nomina consulente tecnico di parte.htm"),
    "P37": RegolaAtto(campi=(Campo("perito", "Perito (cognome, nome, codice fiscale)", "anagrafica"),),
                      fonte="Depositi/Costituzione parte civile (atto principale).htm"),
    "P25": RegolaAtto(campi=(Campo("parte_civile", "Parte civile da escludere (cognome, nome, codice fiscale)", "anagrafica"),),
                      fonte="Atti successivi/Istanza esclusione parte civile.htm"),
    "P22": RegolaAtto(campi=(Campo("magistrato", "Magistrato ricusato"),), fonte="Atti successivi/Ricusazione giudice.htm"),
    "P07": RegolaAtto(campi=(Campo("cf_avvocato_revocato", "Codice fiscale dell'avvocato revocato"),),
                      fonte="Atti successivi/Revoca altro difensore.htm"),
    "P13": RegolaAtto(campi=(Campo("reati", "Reati per i quali ci si costituisce"),),
                      fonte="Atti successivi/Costituzione parte civile di persona offesa rappresentata.htm"),
    "P23": RegolaAtto(campi=(_DOMICILIO,), procura_speciale="spunta", fonte="Atti successivi/Dichiarazione domicilio.htm"),
    "P24": RegolaAtto(campi=(_DOMICILIO,), procura_speciale="spunta", fonte="Atti successivi/Elezione domicilio.htm"),
    "PB9": RegolaAtto(procura_speciale="spunta", fonte="Depositi/Rescissione del giudicato.htm"),
    "PB8": RegolaAtto(procura_speciale="spunta", fonte="Depositi/Istanza revisione.htm"),
    "PAD": RegolaAtto(procura_speciale="spunta", fonte="Depositi/Istanza di riparazione per ingiusta detenzione.htm"),
    "R24": RegolaAtto(campi=_DENUNCIA, procura_speciale="nomina_o_procura", fonte="Depositi/Denuncia.htm"),
    "R25": RegolaAtto(campi=_DENUNCIA, procura_speciale="nomina_o_procura", fonte="Depositi/Querela.htm"),
    "R23": RegolaAtto(procura_speciale="nomina_o_procura", fonte="Consultazione/Elenco presentazioni denunce_querele.htm"),
    "C335": RegolaAtto(campi=(
        Campo("comprensivo_mandato", "Comprensivo di mandato a richiedere il certificato", "si_no", obbligatorio=False,
              nota="Se no, il mandato va allegato."),
    ), un_solo_soggetto=True, fonte="Richiesta certificati/Richiesta certificati.htm"),
}
for _codice in ("PBA", "PB1", "PC4", "PC5", "PBB", "PC9", "PCA", "PCL", "PCM"):
    REGOLE[_codice] = RegolaAtto(campi=_IMPUGNAZIONE, fonte="Atti successivi/Impugnazione sentenza.htm")


def regola_per(codice: str) -> RegolaAtto:
    return REGOLE.get(str(codice or "").upper(), RegolaAtto())


def e_principale(codice: str) -> bool:
    return any(c == str(codice or "").upper() for c, _ in PRINCIPALI)


def etichetta_menu(codice: str) -> str:
    return next((e for c, e in PRINCIPALI if c == str(codice or "").upper()), "")


def e_nomina(codice: str) -> bool:
    return str(codice or "").upper() in NOMINE


__all__ = ["Campo", "FONTE_MANUALE", "FUORI_TABELLA", "NOMINE", "PRINCIPALI", "REGOLE", "RegolaAtto",
           "e_nomina", "e_principale", "etichetta_menu", "regola_per"]
