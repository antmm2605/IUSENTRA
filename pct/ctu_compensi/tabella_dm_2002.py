"""Tabella degli onorari degli ausiliari del magistrato (D.M. 30 maggio 2002).

Riproduce la tabella allegata al D.M. 30/05/2002 (adeguamento dei compensi di periti,
consulenti tecnici, interpreti e traduttori), che resta quella vigente: l'adeguamento
triennale previsto dall'art. 54 D.P.R. 115/2002 non è mai stato adottato (TAR Lazio,
sent. 14327/2026 del 19/08/2026, ha ordinato ai Ministeri di provvedere). Quando uscirà
il nuovo decreto se ne aggiunge qui la tabella con la sua data di efficacia.

Tipi di voce:
- ``scaglioni``: percentuali minime e massime per scaglione di valore, applicate a
  scaglioni progressivi (ogni percentuale sulla quota di valore del suo scaglione);
- ``fisso``: importo minimo e massimo per la prestazione (per reperto, campione o visita);
- ``unico``: importo unico per la prestazione.
"""

from __future__ import annotations

DECRETO = "D.M. 30 maggio 2002"
EFFICACIA = "2002-08-05"
VACAZIONE_EURO = 14.68  # art. 4 L. 319/1980 come adeguato dal D.M. 30/05/2002
VACAZIONE_SUCCESSIVA_DM = 8.15  # superata da Corte cost. 16/2025 (vedi vacazioni.py)

_ART_2 = [(5164.57, 4.6896, 9.3951), (10329.14, 3.7580, 7.5160), (25822.84, 2.8106, 5.6370),
          (51645.69, 2.3527, 4.6896), (103291.38, 1.8790, 3.7580), (258228.45, 0.9316, 1.8790),
          (516456.90, 0.4737, 0.9474)]
_ART_11 = [(5164.57, 6.5686, 13.1531), (10329.14, 4.6896, 9.3951), (25822.84, 3.7580, 7.5160),
           (51645.69, 2.8106, 5.6370), (103291.38, 1.8790, 3.7580), (258228.45, 0.9316, 1.8790),
           (516456.90, 0.2353, 0.4705)]


def _scaglioni(titolo: str, base: str, scaglioni: list, minimo: float, fattore: float = 1.0, nota: str = "") -> dict:
    return {"tipo": "scaglioni", "titolo": titolo, "base": base, "scaglioni": scaglioni, "minimo": minimo,
            "fattore": fattore, "nota": nota}


def _fisso(titolo: str, minimo: float, massimo: float, unita: str = "prestazione", successivi: tuple[float, float] | None = None,
           nota: str = "") -> dict:
    return {"tipo": "fisso", "titolo": titolo, "minimo": minimo, "massimo": massimo, "unita": unita,
            "successivi": successivi, "nota": nota}


def _unico(titolo: str, importo: float, unita: str = "prestazione") -> dict:
    return {"tipo": "unico", "titolo": titolo, "minimo": importo, "massimo": importo, "unita": unita, "successivi": None, "nota": ""}


_DUE_TERZI = (1 / 3, 2 / 3)  # reperti successivi ridotti da un terzo a due terzi
_META = (0.5, 0.5)

VOCI: dict[str, dict] = {
    "2": _scaglioni("Art. 2 — Materia amministrativa, contabile e fiscale", "valore della controversia o dell'accertamento", _ART_2, 145.12),
    "3": _scaglioni("Art. 3 — Valutazione di aziende, patrimoni, diritti", "valore stimato", _ART_2, 145.12, 0.5,
                    "Onorari dell'art. 2 ridotti alla metà."),
    "4A": _scaglioni("Art. 4 (A) — Bilancio: sul totale delle attività", "totale delle attività",
                     [(51645.69, 0.3790, 0.7579), (103291.38, 0.1405, 0.2811), (258228.45, 0.0932, 0.1879),
                      (516456.90, 0.0474, 0.0947), (1032913.80, 0.0235, 0.0471), (2582284.50, 0.0093, 0.0188)], 145.12,
                     nota="Si somma alla voce 4 (B) sui ricavi lordi."),
    "4B": _scaglioni("Art. 4 (B) — Bilancio: sul totale dei ricavi lordi", "totale dei ricavi lordi",
                     [(258228.45, 0.0932, 0.1879), (516456.90, 0.0474, 0.0947), (1032913.80, 0.0188, 0.0376),
                      (5164568.99, 0.0093, 0.0188)], 145.12),
    "5": _fisso("Art. 5 — Inventari, rendiconti, situazioni contabili", 145.12, 970.42),
    "6": _scaglioni("Art. 6 — Avarie comuni", "somma ammessa in avaria",
                    [(3098.74, 4.6896, 9.3951), (5164.57, 3.7580, 7.5160), (10329.14, 3.2843, 6.5686),
                     (25822.84, 2.8106, 5.6370), (51645.69, 1.8790, 3.7580), (103291.38, 1.4053, 2.8106),
                     (258228.45, 0.7042, 1.4085), (516456.90, 0.2353, 0.4705)], 145.12),
    "6bis": _scaglioni("Art. 6-bis — Avarie particolari", "somma liquidata",
                       [(3098.74, 3.2843, 6.5686), (5164.57, 2.8106, 5.6370), (15493.71, 1.4053, 2.8106),
                        (30987.41, 0.7042, 1.4085), (51645.69, 0.4737, 0.9474), (103291.38, 0.2353, 0.4705)], 145.12),
    "7": _fisso("Art. 7 — Metodo attuariale", 145.12, 484.95),
    "7bis": _fisso("Art. 7-bis — Verifica delle basi tecniche previdenziali", 193.67, 582.05),
    "8": _scaglioni("Art. 8 — Equilibrio tecnico-finanziario delle gestioni previdenziali", "entrate annue",
                    [(103291.38, 0.6632, 1.3106), (258228.45, 0.3790, 0.7579), (516456.90, 0.2842, 0.5684),
                     (5164568.99, 0.0379, 0.0758), (25822844.95, 0.0093, 0.0188)], 145.12),
    "8bis": _scaglioni("Art. 8-bis — Analisi tecniche di bilanci previdenziali e assicurativi", "valore di riferimento",
                       [(103291.38, 0.3284, 0.6569), (258228.45, 0.1405, 0.2811), (516456.90, 0.0474, 0.0947),
                        (5164568.99, 0.0141, 0.0281), (51645689.91, 0.00235, 0.0047)], 145.12),
    "9": _fisso("Art. 9 — Pittura, scultura e simili", 96.58, 484.95, "reperto", _DUE_TERZI),
    "10": _fisso("Art. 10 — Retribuzioni, contributi previdenziali, rapporto di lavoro", 145.12, 582.05),
    "11": _scaglioni("Art. 11 — Costruzioni edilizie, impianti, infrastrutture", "valore dell'opera", _ART_11, 145.12),
    "12": _fisso("Art. 12 — Conformità tecnica, collaudo, contabilità dei lavori", 145.12, 970.42),
    "12bis": _fisso("Art. 12-bis — Rilievi topografici e planimetrici", 145.12, 970.42),
    "13": _scaglioni("Art. 13 — Estimo", "importo stimato",
                     [(5164.57, 1.0264, 2.0685), (10329.14, 0.9316, 1.8790), (25822.84, 0.8369, 1.6895),
                      (51645.69, 0.5684, 1.1211), (103291.38, 0.3790, 0.7579), (258228.45, 0.2842, 0.5684),
                      (516456.90, 0.0474, 0.0947)], 145.12),
    "14": _scaglioni("Art. 14 — Cave, miniere, minerali e sostanze", "importo stimato",
                     [(5164.57, 1.4053, 2.8106), (10329.14, 0.9316, 1.8790), (25822.84, 0.4737, 0.9474),
                      (51645.69, 0.2842, 0.5684), (103291.38, 0.1879, 0.3758), (258228.45, 0.0932, 0.1879),
                      (516456.90, 0.0474, 0.0947)], 145.12),
    "15": _scaglioni("Art. 15 — Aerei, navi, imbarcazioni, salvataggio", "valore", _ART_11, 96.58, 0.5,
                     "Onorari dell'art. 11 ridotti alla metà."),
    "15danni": _scaglioni("Art. 15 — Aerei, navi, imbarcazioni: accertamento dei danni", "valore del danno", _ART_11, 96.58, 0.25,
                          "Onorari dell'art. 11 dimezzati e ulteriormente dimezzati per i danni."),
    "16": _fisso("Art. 16 — Amministrazione di immobili, curatele, equo canone, tabelle millesimali", 145.12, 970.42),
    "17": _scaglioni("Art. 17 — Infortunistica del traffico", "valore del danno",
                     [(258.23, 7.5160, 15.0321), (516.46, 5.6370, 11.2741), (2582.28, 3.7580, 7.5160),
                      (25822.84, 1.4053, 2.8106), (51645.69, 0.9316, 1.8790)], 38.73),
    "18": _fisso("Art. 18 — Esplosivi, armi, proiettili", 48.03, 145.12, "reperto", _DUE_TERZI),
    "18bis": _fisso("Art. 18-bis — Balistica", 96.58, 387.86, "reperto", _DUE_TERZI),
    "19": _fisso("Art. 19 — Geomorfologia, idrogeologia, stabilità dei pendii", 241.70, 4852.11),
    "20visita": _unico("Art. 20 — Medico-legale a giudizio immediato: visita", 19.11, "visita"),
    "20ispezione": _unico("Art. 20 — Medico-legale a giudizio immediato: ispezione di cadavere", 19.11, "ispezione"),
    "20autopsia": _unico("Art. 20 — Medico-legale a giudizio immediato: autopsia", 67.66, "autopsia"),
    "20esumato": _unico("Art. 20 — Medico-legale a giudizio immediato: autopsia su cadavere esumato", 96.58, "autopsia"),
    "20bisvisita": _fisso("Art. 20-bis — Medico-legale con relazione scritta: visite", 48.03, 145.12),
    "20biscadavere": _fisso("Art. 20-bis — Medico-legale con relazione scritta: accertamenti su cadavere", 116.20, 387.86),
    "21": _fisso("Art. 21 — Accertamenti medici diagnostici", 48.03, 290.77),
    "22": _unico("Art. 22 — Esame alcoolimetrico", 14.46, "campione"),
    "23": _unico("Art. 23 — Ricerca della carbossiemoglobina", 28.92, "campione"),
    "24": _fisso("Art. 24 — Perizia psichiatrica o criminologica", 96.58, 387.86),
    "25": _fisso("Art. 25 — Materiale biologico e tracce biologiche", 28.92, 290.77, "reperto", _META),
    "26visita": _unico("Art. 26 — Animali a giudizio immediato: visita clinica", 19.11, "visita"),
    "26necroscopico": _unico("Art. 26 — Animali a giudizio immediato: esame necroscopico", 67.66, "esame"),
    "26bisvisita": _fisso("Art. 26-bis — Animali con relazione scritta: visita", 48.03, 145.12, "visita",
                          nota="Onorari raddoppiati per le malattie infettive (indicalo con l'aumento)."),
    "26bisnecroscopico": _fisso("Art. 26-bis — Animali con relazione scritta: esame necroscopico", 96.58, 290.77, "esame"),
    "27qualitativa": _fisso("Art. 27 — Tossicologia su reperti non biologici: ricerca qualitativa", 48.03, 145.12, "campione"),
    "27quantitativa": _fisso("Art. 27 — Tossicologia su reperti non biologici: ricerca quantitativa", 67.66, 193.67, "campione"),
    "27bisqualitativa": _fisso("Art. 27-bis — Tossicologia su reperti biologici: analisi qualitativa", 67.66, 193.67, "sostanza", _META),
    "27bisquantitativa": _fisso("Art. 27-bis — Tossicologia su reperti biologici: analisi quantitativa", 48.03, 145.12, "sostanza", _META),
    "28": _fisso("Art. 28 — Chimico-tossicologica, ricerca completa", 48.03, 145.12),
    "28bis": _fisso("Art. 28-bis — Ecotossicologia", 48.03, 407.48),
    "28ter": _fisso("Art. 28-ter — Inquinamento acustico", 48.03, 484.95),
}

NOTA_ART_29 = ("Art. 29: gli onorari comprendono la relazione, la partecipazione alle udienze e ogni altra attività "
               "connessa all'incarico.")


def elenco() -> list[dict]:
    """Voci per la scelta in interfaccia, nell'ordine della tabella."""

    return [{"value": codice, "label": voce["titolo"], "tipo": voce["tipo"], "base": voce.get("base", ""),
             "unita": voce.get("unita", ""), "nota": voce.get("nota", "")} for codice, voce in VOCI.items()]


__all__ = ["DECRETO", "EFFICACIA", "NOTA_ART_29", "VACAZIONE_EURO", "VACAZIONE_SUCCESSIVA_DM", "VOCI", "elenco"]
