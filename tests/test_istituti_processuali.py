"""Gli istituti processuali letti dai motori: non solo la data, ma che cosa è.

«Termine del 10/09/2026» non dice all'avvocato che cosa deve fare. «Deposito
di note scritte ex art. 127-ter c.p.c.» sì — e da quella qualificazione
discendono i termini che il decreto impone senza scriverne la data.
"""

from __future__ import annotations

from datetime import date

from pct.archivio_letture.collaudo import Contesto
from pct.archivio_letture.istituti_processuali import ISTITUTI, cita_127_bis, cita_127_ter, derivati_da_note
from pct.archivio_letture.motore_documenti import leggi_testo
from pct.archivio_letture.presidi import udienze_e_termini

OGGI = date(2026, 7, 12)
DECRETO_127_TER = (
    "TRIBUNALE DI PALMI N. R.G. 1733/2026 Punturiero Rosa c. MIM. "
    "Ai sensi dell'art. 127 ter c.p.c. in sostituzione dell'udienza "
    "FISSA termine del 10/09/2026 per il deposito di note scritte. "
    "ONERA parte ricorrente della notificazione entro e non oltre 30 giorni prima dell'udienza fissata. "
    "ASSEGNA al resistente termine sino a 10 giorni prima della scadenza per la costituzione."
)


def _letti(testo: str, *, oggi: date = OGGI):
    fatti = leggi_testo(testo, origine="indice",
                        contesto=Contesto(oggi=oggi, numero_rg="1733", anno_rg="2026"))
    for fatto in fatti:
        fatto.oggetto_id, fatto.tipo = "DOC", "documento"
    return fatti


def _per_tipo(testo: str, *, oggi: date = OGGI) -> dict[str, dict]:
    return {voce["type"]: voce for voce in udienze_e_termini(_letti(testo, oggi=oggi), oggi=oggi)}


def test_la_data_del_decreto_prende_il_nome_del_suo_istituto():
    voci = _per_tipo(DECRETO_127_TER)
    assert "note_127_ter" in voci, f"istituto non riconosciuto: {sorted(voci)}"
    assert voci["note_127_ter"]["dateIso"] == "2026-09-10"
    assert "127-ter" in voci["note_127_ter"]["title"]


def test_dal_decreto_nascono_i_termini_che_impone_senza_scriverne_la_data():
    """Trenta giorni prima per la notifica, dieci per la costituzione."""
    voci = _per_tipo(DECRETO_127_TER)
    assert voci["notifica_ricorso_decreto"]["dateIso"] == "2026-08-11"
    assert voci["costituzione_resistente"]["dateIso"] == "2026-08-31"


def test_ogni_termine_porta_con_se_la_norma_che_lo_governa():
    for voce in _per_tipo(DECRETO_127_TER).values():
        assert "127-ter" in voce["norma"], f"{voce['type']} senza norma: {voce.get('norma')!r}"
        assert "149/2022" in voce["norma"], "manca il riferimento alla riforma Cartabia"


def test_un_decreto_che_non_impone_la_notifica_non_fa_nascere_un_termine_di_notifica():
    """Inventarlo metterebbe in scadenziario una data che nessun giudice ha imposto."""
    scarno = (
        "TRIBUNALE DI PALMI N. R.G. 1733/2026. Ai sensi dell'art. 127 ter c.p.c. "
        "FISSA termine del 10/09/2026 per il deposito di note scritte."
    )
    voci = _per_tipo(scarno)
    assert "note_127_ter" in voci
    assert "notifica_ricorso_decreto" not in voci
    assert "costituzione_resistente" not in voci


def test_i_termini_derivati_si_contano_dalla_data_principale():
    assert [(i.codice, g) for i, g in derivati_da_note(DECRETO_127_TER, date(2026, 9, 10))] == [
        ("notifica_ricorso_decreto", date(2026, 8, 11)),
        ("costituzione_resistente", date(2026, 8, 31)),
    ]


def test_un_documento_che_non_cita_l_istituto_resta_come_prima():
    """La qualificazione non si inventa: senza la citazione, la data resta una data."""
    semplice = "TRIBUNALE DI PALMI N. R.G. 1733/2026. Udienza del 10/09/2026 alle ore 9.30."
    voci = _per_tipo(semplice)
    assert set(voci) <= {"udienza_documento", "termine_documento"}, f"istituto inventato: {sorted(voci)}"


def test_il_127_bis_si_riconosce_ma_non_si_confonde_col_127_ter():
    assert cita_127_ter("ai sensi dell'art. 127-ter c.p.c.")
    assert cita_127_ter("art. 127 ter c.p.c.")
    assert not cita_127_ter("ai sensi dell'art. 127-bis c.p.c.")
    assert cita_127_bis("udienza ex art. 127 bis c.p.c. con collegamento audiovisivo")
    assert not cita_127_bis("art. 127-ter c.p.c.")


def test_ogni_istituto_dichiara_titolo_descrizione_e_norma():
    """Un istituto senza norma non si può mostrare all'avvocato: è un dato senza fonte."""
    for istituto in ISTITUTI:
        assert istituto.titolo.strip(), f"{istituto.codice} senza titolo"
        assert istituto.descrizione.strip(), f"{istituto.codice} senza descrizione"
        assert "c.p.c." in istituto.norma, f"{istituto.codice} senza norma"
        assert istituto.campo in {"udienza", "termine", "costituzione"}, f"{istituto.codice}: campo fuori catalogo"
