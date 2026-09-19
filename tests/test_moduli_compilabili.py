"""Il modulo del cliente: quello che lo studio sa gia' e le righe in piu'.

Due cose che un PDF mandato al cliente non fa da solo: evitargli di riscrivere
dati che il fascicolo ha gia' (GDPR art. 5 § 1 lett. d e art. 16) e aggiungere
una riga al nucleo familiare, perche' il pulsante «+» del modulo e' JavaScript
interno al PDF e nel portale non gira.
"""

from __future__ import annotations

from pct.moduli_compilabili import (
    caselle_per_impaginazione,
    impaginazioni_dichiarate,
    proposte_dalla_scheda,
    righe_da_attivare,
    righe_gia_mostrate,
)

ANAGRAFICA = {
    "displayName": "Affinito Antonio",
    "fiscalCode": "FFNNTN86S10A512G",
    "birthDate": "10/11/1986",
    "birthPlace": "Aversa",
    "address": "Via Emanuele Campolongo 87, 81024 Maddaloni (CE)",
    "phone": "",
}


def _campo(nome, *, visibile=True, y=0.0, h=0.02, x=0.1, xref=0, sola_lettura=False, pagina=1):
    return {
        "nome": nome, "etichetta": nome, "pagina": pagina, "visibile": visibile, "xref": xref,
        "tipo": "Text", "valore": "", "opzioni": [], "sola_lettura": sola_lettura,
        "richiesto": False, "max_caratteri": 100, "selezionato": False,
        "rettangolo": [x, y, 0.3, h],
    }


def test_propone_solo_i_dati_che_la_scheda_ha_davvero():
    campi = [_campo("nome_cognome"), _campo("luogo_nascita"), _campo("telefono"), _campo("professione")]

    proposte = proposte_dalla_scheda(campi, ANAGRAFICA)

    assert proposte == {"nome_cognome": "Affinito Antonio", "luogo_nascita": "Aversa"}
    # il telefono manca in scheda e resta vuoto; la professione la scheda non la conosce


def test_la_prima_riga_della_tabella_e_il_richiedente():
    campi = [_campo("nucleo_1_nome"), _campo("nucleo_1_codice_fiscale"), _campo("nucleo_2_nome")]

    proposte = proposte_dalla_scheda(campi, ANAGRAFICA)

    assert proposte["nucleo_1_nome"] == "Affinito Antonio"
    assert proposte["nucleo_1_codice_fiscale"] == "FFNNTN86S10A512G"
    # la riga 2 e' un altro componente: non si riempie con i dati del richiedente
    assert "nucleo_2_nome" not in proposte


def test_un_campo_non_dichiarato_non_si_interpreta():
    """Un nome fuori dall'elenco non diventa un dato personale per somiglianza."""
    assert proposte_dalla_scheda([_campo("referente_pratica")], ANAGRAFICA) == {}


def test_un_campo_di_sola_lettura_non_si_propone():
    assert proposte_dalla_scheda([_campo("nome_cognome", sola_lettura=True)], ANAGRAFICA) == {}


def _modulo_a_righe():
    """Due righe mostrate, due pronte, e un'impaginazione per ogni misura."""
    campi = [
        _campo("impaginazione_2", visibile=True, sola_lettura=True, y=0.4, h=0.3, xref=1),
        _campo("impaginazione_3", visibile=False, sola_lettura=True, y=0.4, h=0.3, xref=2),
        _campo("impaginazione_4", visibile=False, sola_lettura=True, y=0.4, h=0.3, xref=3),
    ]
    for riga in (1, 2):
        campi.append(_campo(f"nucleo_{riga}_nome", visibile=True, y=0.40 + riga * 0.05, h=0.02, xref=10 + riga))
    # le righe 3 e 4 esistono in una variante per ogni impaginazione che le contiene
    campi.append(_campo("nucleo_3_nome", visibile=False, y=0.55, h=0.02, xref=30))   # con 3 righe
    campi.append(_campo("nucleo_3_nome", visibile=False, y=0.53, h=0.018, xref=31))  # con 4 righe
    campi.append(_campo("nucleo_4_nome", visibile=False, y=0.58, h=0.018, xref=40))  # con 4 righe
    return campi


def test_legge_le_impaginazioni_che_il_modulo_si_porta_dietro():
    assert sorted(impaginazioni_dichiarate(_modulo_a_righe())) == [2, 3, 4]
    assert righe_gia_mostrate(_modulo_a_righe()) == 2


def test_le_righe_pronte_si_possono_attivare_una_alla_volta():
    righe = righe_da_attivare(_modulo_a_righe())

    assert [r["numero"] for r in righe] == [3, 4]


def test_di_ogni_campo_si_sceglie_la_casella_dell_impaginazione_giusta():
    """Con tre righe vale la variante piu' alta, con quattro quella compressa."""
    campi = _modulo_a_righe()

    assert caselle_per_impaginazione(campi, 3)["nucleo_3_nome"] == 30
    assert caselle_per_impaginazione(campi, 4)["nucleo_3_nome"] == 31
    assert caselle_per_impaginazione(campi, 4)["nucleo_4_nome"] == 40


def test_un_modulo_senza_impaginazioni_non_aggiunge_righe():
    """Senza una griglia pronta la riga cadrebbe fuori dalla tabella: non si aggiunge."""
    campi = [_campo("nucleo_1_nome", visibile=True), _campo("nucleo_2_nome", visibile=False)]

    assert righe_da_attivare(campi) == []
