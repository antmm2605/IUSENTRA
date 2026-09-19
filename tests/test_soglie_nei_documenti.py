"""Un modulo che cita una soglia di legge superata deve dirlo.

Il modello dell'autocertificazione per l'esenzione dal contributo unificato
riportava 38.514,03 euro — il triplo del limite del D.M. 10 maggio 2023 —
quando il D.M. 22 aprile 2025 aveva gia' portato quel triplo a 40.978,92: chi
lo compilava dichiarava su una soglia che non esisteva piu'.

Base normativa: artt. 76, 77 e 9 comma 1-bis D.P.R. 115/2002.
"""

from __future__ import annotations

from datetime import date

from pct.soglie_nei_documenti import (
    importi_nel_testo,
    soglie_conosciute,
    soglie_superate_nel_testo,
)


class _Norme:
    """La tabella versionata, con i due decreti di adeguamento noti."""

    def rows(self, tabella: str, on_date=None):
        return [
            {
                "effective_from": "2023-06-06",
                "amount": 12838.01,
                "decreto": "D.M. 10 maggio 2023",
                "gazzetta": "GU Serie Generale n. 130 del 6 giugno 2023",
            },
            {
                "effective_from": "2025-07-11",
                "amount": 13659.64,
                "decreto": "D.M. 22 aprile 2025",
                "gazzetta": "GU Serie Generale n. 159 dell'11 luglio 2025",
            },
        ]


OGGI = date(2026, 9, 19)


def test_riconosce_il_triplo_superato_e_indica_quello_vigente():
    testo = "non supera l'importo di Euro 38.514,03 relativamente all'anno 2025"

    segnalazioni = soglie_superate_nel_testo(testo, _Norme(), OGGI)

    assert len(segnalazioni) == 1
    segnalazione = segnalazioni[0]
    assert segnalazione["importo_citato"] == "38514.03"
    assert segnalazione["importo_vigente"] == "40978.92"
    assert "D.M. 22 aprile 2025" in segnalazione["messaggio"]
    assert "40.978,92" in segnalazione["messaggio"]


def test_riconosce_anche_il_limite_base_superato():
    segnalazioni = soglie_superate_nel_testo("reddito non superiore a 12.838,01 euro", _Norme(), OGGI)

    assert [s["importo_vigente"] for s in segnalazioni] == ["13659.64"]


def test_l_importo_vigente_non_si_segnala():
    assert soglie_superate_nel_testo("non superiore a 40.978,92 euro", _Norme(), OGGI) == []
    assert soglie_superate_nel_testo("non superiore a 13.659,64 euro", _Norme(), OGGI) == []


def test_un_numero_qualunque_non_diventa_una_soglia():
    """Il confronto e' al centesimo: un importo somigliante non basta."""
    testo = "canone di 38.514,04 euro, spese per 1.234,56 e un acconto di 12.838,00"

    assert soglie_superate_nel_testo(testo, _Norme(), OGGI) == []


def test_gli_importi_si_leggono_nella_forma_italiana():
    trovati = {str(v) for v in importi_nel_testo("38.514,03 euro e 1.234,56 oltre a 12 mele")}

    assert trovati == {"38514.03", "1234.56"}


def test_la_tabella_dichiara_quale_riga_e_vigente():
    conosciute = soglie_conosciute(_Norme(), OGGI)

    vigenti = {str(v) for v, dati in conosciute.items() if dati["vigente"]}
    superate = {str(v) for v, dati in conosciute.items() if not dati["vigente"]}
    assert vigenti == {"13659.64", "40978.92"}
    assert superate == {"12838.01", "38514.03"}


def test_prima_del_decreto_del_2025_vigeva_l_altro():
    """La verifica guarda la data: nel 2024 la soglia superata era un'altra."""
    conosciute = soglie_conosciute(_Norme(), date(2024, 5, 1))

    assert {str(v) for v, dati in conosciute.items() if dati["vigente"]} == {"12838.01", "38514.03"}
    assert soglie_superate_nel_testo("38.514,03", _Norme(), date(2024, 5, 1)) == []
