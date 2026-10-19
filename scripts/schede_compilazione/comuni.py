"""Mattoni comuni delle schede di compilazione: norme e campi ricorrenti.

Ogni campo segue lo schema di ``pct/schede_compilazione.py``: fonte (database, archivio_letture,
documento, calcolo, avvocato, lex), norma che lo rende necessario e cosa fare se manca. Gli articoli si
scrivono come nell'archivio «Codici e leggi» (per esempio ``171ter``) perché ``costruisci.py`` li verifica lì.
"""
from __future__ import annotations

CPC, CC = "codice_procedura_civile", "codice_civile"
FERIALE = ("legge_742_1969", "1", "sospensione feriale dei termini")
SENZA_FERIALE = [("legge_742_1969", "3", "esclusione della sospensione feriale"), ("12/1941", "92", "affari urgenti esclusi dalla sospensione")]
A_RITROSO = "; se l’ultimo giorno cade di sabato o festivo si anticipa al primo giorno non festivo precedente"
IN_AVANTI = "; se l’ultimo giorno cade di sabato o festivo si proroga al primo giorno non festivo seguente (art. 155 c.p.c.)"


def N(atto: str, articolo: str, perche: str = "") -> dict:
    return {"atto": atto, "articolo": articolo, "perche": perche}


def _norme(norme) -> list[dict]:
    return [n if isinstance(n, dict) else N(*n) for n in (norme or [])]


def campo(nome, etichetta, fonte, *, norma=None, obbligatorio=True, se_manca="", compilatore=None,
          parole=None, fatti=None) -> dict:
    c = {"campo": nome, "etichetta": etichetta, "obbligatorio": obbligatorio, "fonte": fonte}
    if norma:
        c["norma"] = _norme(norma)
    if se_manca:
        c["se_manca"] = se_manca
    if compilatore:
        c["compilatore"] = list(compilatore)
    if parole:
        c["parole_documento"] = list(parole)
    if fatti:
        c["fatti"] = list(fatti)
    return c


def avvocato(nome, etichetta, domanda, **kw) -> dict:
    return campo(nome, etichetta, {"tipo": "avvocato", "domanda": domanda}, **kw)


def lex(nome, etichetta, compito, **kw) -> dict:
    kw.setdefault("obbligatorio", False)
    return campo(nome, etichetta, {"tipo": "lex", "compito": compito}, **kw)


def calcolo(nome, etichetta, regola, termine=None, **kw) -> dict:
    fonte = {"tipo": "calcolo", "regola": regola}
    if termine:
        fonte["termine"] = termine
    return campo(nome, etichetta, fonte, **kw)


def T(base, giorni=0, *, mesi=0, ritroso=False, feriale=True) -> dict:
    """Termine calcolabile dal software (vedi ``pct/schede_termini.py``)."""
    t = {"base": base, "direzione": "ritroso" if ritroso else "avanti", "feriale": feriale}
    t.update({"mesi": mesi} if mesi else {"giorni": giorni})
    return t


def documento(nome, etichetta, descrizione, parole, **kw) -> dict:
    return campo(nome, etichetta, {"tipo": "documento", "documento": descrizione}, parole=parole, **kw)


def letto(nome, etichetta, fatto, descrizione, fatti, **kw) -> dict:
    return campo(nome, etichetta, {"tipo": "archivio_letture", "fatto": fatto, "documento": descrizione}, fatti=fatti, **kw)


def database(nome, etichetta, percorsi, **kw) -> dict:
    return campo(nome, etichetta, {"tipo": "database", "percorsi": list(percorsi)}, **kw)


# Campi presenti in quasi tutti gli atti di parte
def difensore() -> dict:
    return database("difensore", "Difensore, codice fiscale e PEC",
                    ["studio.avvocato_titolare", "studio_timbro.codice_fiscale", "studio_timbro.pec"],
                    norma=[(CPC, "125", "sottoscrizione del difensore"), (CPC, "83", "procura")],
                    compilatore=["lawyer", "_lawyer_pec", "_lawyer_tax_id"])


def procura(se_manca="chiedere il caricamento della procura; senza procura l’atto non si deposita") -> dict:
    return documento("procura", "Procura alle liti", "procura sottoscritta dal cliente", ["procura"],
                     norma=[(CPC, "83", "procura alle liti")], se_manca=se_manca)


def data_luogo() -> dict:
    return database("data_luogo", "Luogo e data", ["studio.citta", "today"], compilatore=["place", "document_date"])


def assistito(etichetta="Parte assistita (anagrafica e codice fiscale)", nome="assistito") -> dict:
    return database(nome, etichetta, ["parti.assistito_principale", "cliente"],
                    norma=[(CPC, "125", "indicazione delle parti")], compilatore=["client_or_sender"])


def controparte(etichetta="Controparte", nome="controparte") -> dict:
    return database(nome, etichetta, ["parti.controparte_principale", "fascicolo.controparte"],
                    norma=[(CPC, "125", "indicazione delle parti")], compilatore=["counterparty_or_recipient"])


def causa_pendente(etichetta="Ufficio, giudice e numero di ruolo della causa") -> dict:
    return letto("dati_causa", etichetta, "ufficio_e_rg", "fascicolo, PEC di cancelleria e verbali",
                 [{"categoria": "ruolo"}], norma=[(CPC, "125", "indicazione dell’ufficio")],
                 compilatore=["recipient_or_court", "case_reference_display"],
                 se_manca="chiedere ufficio e numero di ruolo: senza la causa pendente l’atto non si deposita")


def ufficio_da_adire(norma) -> dict:
    return calcolo("ufficio", "Ufficio giudiziario competente",
                   "competenza per materia, valore e territorio secondo le norme indicate; da confermare",
                   norma=norma, compilatore=["recipient_or_court"])


def udienza(etichetta="Prossima udienza fissata", nome="udienza") -> dict:
    return letto(nome, etichetta, "udienza", "verbali e PEC di cancelleria", [{"categoria": "data", "campo": "udienza"}],
                 se_manca="chiedere la data dell’udienza: i termini si contano da lì")


def fatti_documentati(etichetta="Fatti rilevanti con date e documenti") -> dict:
    return letto("fatti", etichetta, "eventi_e_date", "documenti del fascicolo", [{"categoria": "evento"}, {"categoria": "data"}],
                 compilatore=["facts"])


def allegati() -> dict:
    return database("allegati", "Documenti da allegare", ["documenti.nomi"], obbligatorio=False, compilatore=["attachments_list"])
