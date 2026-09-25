"""Da quando, per ciascun ufficio, il PDP è l'unico canale di deposito.

Base normativa: art. 111-bis c.p.p.; D.M. 29/12/2023 n. 217, art. 3, come
modificato dal D.M. 27/12/2024 n. 206, dal D.M. 30/12/2025 n. 206 e dal
D.M. 26/06/2026 n. 114 (G.U. n. 149 del 30/06/2026). Prima della data
d'obbligo restano ammessi PEC e deposito cartaceo; la costituzione di parte
civile in udienza resta cartacea (art. 78 c.p.p.).
"""

from __future__ import annotations

from datetime import date

FONTE = ("art. 111-bis c.p.p.; D.M. 217/2023 art. 3 come modificato dai D.M. 206/2024, "
         "206/2025 e 114/2026 (G.U. n. 149 del 30/06/2026)")

# Codice tipo ufficio del PDP (codificati/tipi-ufficio) -> (data d'obbligo, descrizione)
OBBLIGO: dict[str, tuple[date, str]] = {
    "PM-U": (date(2025, 1, 1), "Procura della Repubblica"),
    "PM-G": (date(2025, 1, 1), "Procura della Repubblica (reati di competenza del Giudice di Pace)"),
    "GIP-U": (date(2025, 1, 1), "Giudice per le indagini e l'udienza preliminare"),
    "DIB-U": (date(2025, 1, 1), "Tribunale"),
    "RIE": (date(2025, 1, 1), "Tribunale del Riesame"),
    "CAS-U": (date(2025, 1, 1), "Corte d'Assise (presso il Tribunale)"),
    "CAP-U": (date(2027, 7, 1), "Corte d'Appello"),
    "CASAP-U": (date(2027, 7, 1), "Corte d'Assise d'Appello"),
    "PGCAP-U": (date(2027, 7, 1), "Procura Generale presso la Corte d'Appello"),
    "GP-C": (date(2028, 1, 1), "Giudice di Pace"),
    "GP-G": (date(2028, 1, 1), "Giudice di Pace"),
    "DIB-G": (date(2028, 1, 1), "Tribunale in appello avverso le sentenze del Giudice di Pace"),
    "PMM-U": (date(2029, 1, 1), "Procura presso il Tribunale per i minorenni"),
    "GIPM-U": (date(2029, 1, 1), "GIP presso il Tribunale per i minorenni"),
    "GUPM-U": (date(2029, 1, 1), "GUP presso il Tribunale per i minorenni"),
    "DIBM-U": (date(2029, 1, 1), "Tribunale per i minorenni"),
    "CAPSM-U": (date(2029, 1, 1), "Corte d'Appello, sezione minorenni"),
}

# Uffici fuori dal PDP degli avvocati ma con obbligo a calendario (per informazione).
ALTRI: tuple[tuple[str, date], ...] = (
    ("Corte di Cassazione e Procura Generale presso la Cassazione", date(2028, 1, 1)),
    ("Uffici della giustizia minorile", date(2029, 1, 1)),
    ("Procedimenti di esecuzione (Libro X c.p.p.)", date(2029, 7, 1)),
    ("Tribunale di Sorveglianza", date(2030, 1, 1)),
    ("Ulteriori categorie di procedimenti (riparazione, revisione, rapporti con autorità straniere, MAE)", date(2030, 7, 1)),
)


# Procedimenti con calendario proprio, anche se depositati alla Corte d'Appello.
SPECIALI: dict[str, tuple[date, str]] = {
    "PB8": (date(2030, 7, 1), "Revisione"),
    "PAD": (date(2030, 7, 1), "Riparazione per ingiusta detenzione"),
    "PCS": (date(2030, 7, 1), "Riparazione dell'errore giudiziario"),
}


def canale(ufficio: str, oggi: date | None = None, *, atto: str = "") -> dict[str, str | bool]:
    """Il canale di deposito per quell'ufficio (e, se serve, quell'atto) alla data indicata."""
    codice = str(ufficio or "").strip().upper()
    giorno = oggi or date.today()
    voce = OBBLIGO.get(codice)
    speciale = SPECIALI.get(str(atto or "").upper())
    if voce is not None and speciale is not None:
        voce = speciale
    if voce is None:
        return {"obbligatorio": False, "etichetta": "Canale da verificare", "dal": "",
                "nota": "Ufficio non presente nel calendario del processo penale telematico.", "fonte": FONTE}
    dal, descrizione = voce
    if giorno >= dal:
        return {"obbligatorio": True, "etichetta": "PDP obbligatorio", "dal": dal.isoformat(),
                "nota": f"{descrizione}: deposito solo telematico dal {dal.strftime('%d/%m/%Y')}.", "fonte": FONTE}
    return {"obbligatorio": False, "etichetta": "PDP facoltativo", "dal": dal.isoformat(),
            "nota": (f"{descrizione}: obbligo dal {dal.strftime('%d/%m/%Y')}. "
                     "Fino ad allora sono ammessi anche PEC e deposito cartaceo."), "fonte": FONTE}


__all__ = ["ALTRI", "FONTE", "OBBLIGO", "SPECIALI", "canale"]
