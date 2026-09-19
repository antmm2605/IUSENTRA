"""L'anagrafica del portale parte da cio' che lo studio gia' sa.

Il cliente non deve riscrivere dati che il fascicolo ha gia': li conferma. Ma
quello che scrive di suo resta la sua parola e prevale sempre, e le due origini
non si confondono.

Base normativa: GDPR 2016/679 art. 5 § 1 lett. d) (esattezza) e art. 16
(rettifica).
"""

from __future__ import annotations

from pct.anagrafica_cliente_portale import (
    CAMPI_PORTALE,
    aggiornamenti_per_la_scheda,
    anagrafica_dallo_studio,
    origine_dei_campi,
    separa_via_e_civico,
    unisci_anagrafica,
)
from pct.clienti import Cliente, DocumentoIdentita, Indirizzo, Recapiti, TipoCliente


def _cliente_completo() -> Cliente:
    return Cliente(
        id="CL-1",
        tipo=TipoCliente.PERSONA_FISICA,
        nome="Antonio",
        cognome="Affinito",
        codice_fiscale="FFNNTN86S10A512G",
        data_nascita="1986-11-10",
        luogo_nascita="Avellino",
        indirizzo_residenza=Indirizzo(via="Via Roma", civico="12", cap="83100", comune="Avellino", provincia="av"),
        recapiti=Recapiti(telefono="082512345", cellulare="3331234567", email="antonio@example.it", pec="antonio@pec.it"),
        documento=DocumentoIdentita(numero="CA123", data_scadenza="2030-04-21"),
    )


def test_la_scheda_dello_studio_riempie_i_campi_del_portale():
    dati = anagrafica_dallo_studio(_cliente_completo())

    assert dati["displayName"] == "Affinito Antonio"
    assert dati["fiscalCode"] == "FFNNTN86S10A512G"
    assert dati["birthDate"] == "1986-11-10"
    assert dati["birthPlace"] == "Avellino"
    assert dati["address"] == "Via Roma 12"
    assert dati["cap"] == "83100"
    assert dati["city"] == "Avellino"
    assert dati["province"] == "AV"
    assert dati["pec"] == "antonio@pec.it"
    assert dati["identityExpiresAt"] == "2030-04-21"
    # Il cellulare precede il telefono fisso: e' il recapito con cui si scrive.
    assert dati["phone"] == "3331234567"


def test_una_scheda_vuota_non_inventa_nulla():
    dati = anagrafica_dallo_studio(Cliente(id="CL-2", tipo=TipoCliente.PERSONA_FISICA))

    assert set(dati) == set(CAMPI_PORTALE)
    assert all(valore == "" for campo, valore in dati.items() if campo != "displayName")


def test_senza_cliente_i_campi_restano_vuoti_e_completi():
    dati = anagrafica_dallo_studio(None)

    assert set(dati) == set(CAMPI_PORTALE)
    assert set(dati.values()) == {""}


def test_la_sede_legale_vale_quando_manca_la_residenza():
    societa = Cliente(
        id="CL-3",
        tipo=TipoCliente.PERSONA_GIURIDICA,
        ragione_sociale="Gamma S.p.A.",
        partita_iva="01234567890",
        indirizzo_sede_legale=Indirizzo(via="Corso Italia", civico="9", cap="20121", comune="Milano", provincia="MI"),
    )

    dati = anagrafica_dallo_studio(societa)

    assert dati["address"] == "Corso Italia 9"
    assert dati["city"] == "Milano"
    assert dati["vatNumber"] == "01234567890"


def test_quello_che_scrive_il_cliente_prevale_sulla_scheda():
    dallo_studio = anagrafica_dallo_studio(_cliente_completo())
    dal_cliente = {"phone": "3399999999", "address": "Via Nuova 3"}

    unita = unisci_anagrafica(dallo_studio=dallo_studio, dal_cliente=dal_cliente)

    assert unita["phone"] == "3399999999"
    assert unita["address"] == "Via Nuova 3"
    # Cio' che il cliente non ha toccato resta la proposta dello studio.
    assert unita["city"] == "Avellino"


def test_un_campo_vuoto_del_cliente_non_cancella_il_dato_dello_studio():
    dallo_studio = anagrafica_dallo_studio(_cliente_completo())

    unita = unisci_anagrafica(dallo_studio=dallo_studio, dal_cliente={"city": "   "})

    assert unita["city"] == "Avellino"


def test_l_origine_distingue_confermato_da_proposto():
    dallo_studio = anagrafica_dallo_studio(_cliente_completo())
    origini = origine_dei_campi(dallo_studio=dallo_studio, dal_cliente={"phone": "3399999999"})

    assert origini["phone"] == "cliente"
    assert origini["city"] == "studio"
    # La professione non e' un campo della scheda dello studio: resta da scrivere.
    assert origini["profession"] == ""


def test_quello_che_il_cliente_compila_torna_sui_campi_veri_della_scheda():
    """I recapiti stanno in `recapiti`, l'indirizzo in `indirizzo_residenza`.

    Regressione: la sincronizzazione scriveva su attributi piatti (`email`,
    `telefono`, `citta`) che la dataclass Cliente non ha, e li scartava in
    silenzio: la scheda dello studio non si aggiornava mai.
    """
    cliente = Cliente(id="CL-2", tipo=TipoCliente.PERSONA_FISICA, nome="Antonio", cognome="Affinito")

    aggiornamenti, divergenze = aggiornamenti_per_la_scheda(
        cliente,
        {
            "email": "antonio@example.it",
            "phone": "3331234567",
            "pec": "antonio@pec.it",
            "fiscalCode": "FFNNTN86S10A512G",
            "birthDate": "1986-11-10",
            "birthPlace": "Aversa",
            "address": "Via Emanuele Campolongo 87",
            "cap": "81024",
            "city": "Maddaloni",
            "province": "CE",
            "identityExpiresAt": "2030-11-10",
            "profession": "Impiegato",
        },
    )

    assert divergenze == {}
    assert aggiornamenti["recapiti"] == {"email": "antonio@example.it", "cellulare": "3331234567", "pec": "antonio@pec.it"}
    assert aggiornamenti["cliente"] == {
        "codice_fiscale": "FFNNTN86S10A512G",
        "data_nascita": "1986-11-10",
        "luogo_nascita": "Aversa",
    }
    assert aggiornamenti["indirizzo"] == {
        "via": "Via Emanuele Campolongo",
        "civico": "87",
        "cap": "81024",
        "comune": "Maddaloni",
        "provincia": "CE",
    }
    assert aggiornamenti["documento"] == {"data_scadenza": "2030-11-10"}
    # La professione non e' un campo della scheda: non si inventa dove metterla.
    assert "profession" not in str(aggiornamenti)


def test_un_dato_gia_in_scheda_non_si_sovrascrive_ma_si_segnala():
    cliente = _cliente_completo()

    aggiornamenti, divergenze = aggiornamenti_per_la_scheda(
        cliente,
        {"email": "nuova@example.it", "phone": "3331234567", "city": "Avellino"},
    )

    assert aggiornamenti == {}
    assert divergenze == {"email": ("antonio@example.it", "nuova@example.it")}


def test_lo_stesso_dato_scritto_diversamente_non_e_una_divergenza():
    cliente = _cliente_completo()

    _aggiornamenti, divergenze = aggiornamenti_per_la_scheda(cliente, {"email": "Antonio@Example.it", "province": "AV"})

    assert divergenze == {}


def test_il_civico_si_stacca_solo_quando_e_un_civico():
    assert separa_via_e_civico("Via Emanuele Campolongo 87") == ("Via Emanuele Campolongo", "87")
    assert separa_via_e_civico("Piazza Garibaldi 12/A") == ("Piazza Garibaldi", "12/A")
    assert separa_via_e_civico("Contrada Serroni") == ("Contrada Serroni", "")
    assert separa_via_e_civico("Largo 8 Marzo") == ("Largo 8 Marzo", "")


def test_l_indirizzo_riletto_torna_come_il_cliente_lo_ha_scritto():
    cliente = Cliente(id="CL-3", tipo=TipoCliente.PERSONA_FISICA, nome="Antonio", cognome="Affinito")

    aggiornamenti, _divergenze = aggiornamenti_per_la_scheda(cliente, {"address": "Via Emanuele Campolongo 87"})
    for attributo, valore in aggiornamenti["indirizzo"].items():
        setattr(cliente.indirizzo_residenza, attributo, valore)

    assert anagrafica_dallo_studio(cliente)["address"] == "Via Emanuele Campolongo 87"


def test_senza_cliente_non_si_aggiorna_nulla():
    assert aggiornamenti_per_la_scheda(None, {"email": "a@b.it"}) == ({}, {})
