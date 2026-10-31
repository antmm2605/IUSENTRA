"""Bozze «termine lungo» calcolate dalla comunicazione (verifica sulle PEC reali del 31/10/2026).

Fonte certa dai documenti del fascicolo, altrimenti decide l'avvocato; nulla si cancella o si conferma.
"""

from __future__ import annotations

from types import SimpleNamespace

from pct.riconvalida_termine_lungo import AVVISO, DAI_DOCUMENTI, NON_CERTA, riconvalida_bozze
from pct.scadenziario import GestioneScadenziario, StatoTermine, TipoTermine


def _bozza(scadenziario, *, numero: str, fascicolo: str, comunicazione: str, lavoro: bool = True):
    feriale = "Sospensione feriale non applicata: controversia di lavoro" if lavoro else "Sospensione feriale 1-31 agosto applicata"
    scadenza = scadenziario.nuova(
        titolo="Impugnazione sentenza - termine lungo - RG 1/2026", tipo=TipoTermine.IMPUGNAZIONE,
        data_scadenza="2027-04-16", id_fascicolo=fascicolo,
        descrizione=f"Sentenza n. {numero} comunicata via PEC il {comunicazione}. Sei mesi dalla pubblicazione. {feriale}.",
        data_decorrenza="2026-10-16", source_event_at="2026-10-16T11:55:18Z", deadline_profile_code="CIV_APPELLO_LUNGO",
    )
    return scadenziario.aggiorna(scadenza.id, stato=StatoTermine.BOZZA.value, note=f"PEC_TERMINE_PROPOSTO:pec_x:{numero}")


def _fatto(contesto: str, valore: str):
    return SimpleNamespace(categoria="data", campo="deposito", verifica="verificata", contesto=contesto, valore=valore)


def test_data_di_deposito_trovata_nei_documenti_del_fascicolo_sostituisce_la_comunicazione(tmp_path):
    scadenziario = GestioneScadenziario(str(tmp_path / "scadenze.json"))
    bozza = _bozza(scadenziario, numero="809/2026", fascicolo="F1", comunicazione="16/10/2026")
    fatti = {"F1": [
        _fatto("con sentenza n. 1842/2022 pubblicata il 16.03.2022", "2022-03-16"),  # precedente citato: ignorato
        _fatto("Sentenza n. 809/2026 pubbl. il 14/10/2026 RG n. 538/2026", "2026-10-14"),
    ]}
    assert riconvalida_bozze(scadenziario, lambda fid: fatti.get(fid, [])) == {"dal_portale": 0, "dai_documenti": 1, "da_giudicare": 0}
    voce = scadenziario.get(bozza.id)
    assert voce.data_decorrenza == "2026-10-14" and voce.data_scadenza == "2027-04-14"
    assert voce.stato == StatoTermine.BOZZA and DAI_DOCUMENTI in voce.note


def test_senza_fonte_certa_decide_l_avvocato_e_la_riconvalida_non_si_ripete(tmp_path):
    scadenziario = GestioneScadenziario(str(tmp_path / "scadenze.json"))
    bozza = _bozza(scadenziario, numero="938/2026", fascicolo="", comunicazione="09/06/2026")
    assert riconvalida_bozze(scadenziario, lambda fid: []) == {"dal_portale": 0, "dai_documenti": 0, "da_giudicare": 1}
    voce = scadenziario.get(bozza.id)
    assert voce.stato == StatoTermine.BOZZA and voce.data_scadenza == "2027-04-16"  # nulla cancellato o confermato
    assert voce.descrizione.startswith(AVVISO) and NON_CERTA in voce.note
    assert riconvalida_bozze(scadenziario, lambda fid: []) == {"dal_portale": 0, "dai_documenti": 0, "da_giudicare": 0}


def test_decorrenza_dal_registro_diversa_dalla_comunicazione_non_si_tocca(tmp_path):
    scadenziario = GestioneScadenziario(str(tmp_path / "scadenze.json"))
    bozza = _bozza(scadenziario, numero="250/2026", fascicolo="F1", comunicazione="29/04/2026")
    scadenziario.aggiorna(bozza.id, data_decorrenza="2026-10-15")  # data dell'evento del registro, non la comunicazione
    assert riconvalida_bozze(scadenziario, lambda fid: []) == {"dal_portale": 0, "dai_documenti": 0, "da_giudicare": 0}


def _documento_portale(classe: str, deposito: str, fonte: str = "PORTALE_TELEMATICO"):
    return SimpleNamespace(fonte_documento=fonte, classificazione_portale=classe, data_deposito_portale=deposito)


def test_la_sentenza_del_portale_corregge_la_scadenza_tardiva_di_un_giorno(tmp_path):
    """Caso reale (RG 806/2026): deposito il 06/10 sul portale, comunicazione il 07/10."""
    scadenziario = GestioneScadenziario(str(tmp_path / "scadenze.json"))
    bozza = _bozza(scadenziario, numero="762/2026", fascicolo="F2", comunicazione="07/10/2026")
    scadenziario.aggiorna(bozza.id, data_decorrenza="2026-10-07", source_event_at="2026-10-07T09:00:00Z", data_scadenza="2027-04-07")
    documenti = {"F2": [
        _documento_portale("SentenzaDefinitiva", "06/10/2026"),
        _documento_portale("Provvedimento - sentenza", "31/05/2026", fonte="IMPORT_ESTERNO"),  # data d'importazione
        _documento_portale("Verbale", "06/10/2026"),
    ]}
    esito = riconvalida_bozze(scadenziario, lambda fid: [], lambda fid: documenti.get(fid, []))
    assert esito == {"dal_portale": 1, "dai_documenti": 0, "da_giudicare": 0}
    voce = scadenziario.get(bozza.id)
    assert voce.data_decorrenza == "2026-10-06" and voce.data_scadenza == "2027-04-06"
    assert "fascicolo telematico" in voce.descrizione and voce.stato == StatoTermine.BOZZA


def test_la_bozza_non_certa_si_corregge_quando_arriva_la_sentenza_dal_portale(tmp_path):
    scadenziario = GestioneScadenziario(str(tmp_path / "scadenze.json"))
    bozza = _bozza(scadenziario, numero="839/2026", fascicolo="F3", comunicazione="16/10/2026")
    documenti: dict[str, list] = {"F3": []}
    assert riconvalida_bozze(scadenziario, lambda fid: [], lambda fid: documenti[fid])["da_giudicare"] == 1
    documenti["F3"] = [_documento_portale("SentenzaDefinitiva", "15/10/2026")]
    assert riconvalida_bozze(scadenziario, lambda fid: [], lambda fid: documenti[fid])["dal_portale"] == 1
    voce = scadenziario.get(bozza.id)
    assert voce.data_decorrenza == "2026-10-15" and AVVISO not in voce.descrizione and NON_CERTA not in voce.note


def test_sentenze_del_portale_con_date_diverse_non_si_sceglie():
    from datetime import date

    from pct.termine_lungo_sentenza import data_deposito_dal_portale

    documenti = [_documento_portale("SentenzaDefinitiva", "2026-10-06"), _documento_portale("Sentenza non definitiva", "2026-09-01")]
    assert data_deposito_dal_portale(documenti, comunicazione=date(2026, 10, 7)) is None
    assert data_deposito_dal_portale(documenti[:1], comunicazione=date(2026, 10, 7)) == date(2026, 10, 6)
    assert data_deposito_dal_portale(documenti[:1], comunicazione=date(2026, 10, 5)) is None  # dopo la comunicazione: no
