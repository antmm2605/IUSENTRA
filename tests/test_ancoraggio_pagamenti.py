"""FAS-25: le date di avvisi pagoPA/CBILL, quietanze, bonifici e fatture non sono termini processuali."""
from pct.archivio_letture.ancoraggio import brano, esclusione_data_salvata
from pct.archivio_letture.estrazione_date import estrai_date

CBILL = ("Pagamento bolletta PagoPA\nDati ordinante\nConto addebito\nDati bolletta\nCodice azienda\n"
         "80184430587 MINISTERO DELLA GIUSTIZIA\nCodice avviso\n330007606087363218\nData scadenza\n09/01/2025\n"
         "Importo\n49,00\nCommissioni azienda")
PAGOPA = "QUANTO E QUANDO PAGARE?\n27,00 Euro entro il 12/02/2025 PAGA SUL SITO O CON LE APP\nBANCHE E ALTRI CANALI RATA entro il 12/02/2025"
FATTURA = "si prega di trovare in allegato fattura del 28/05/2024, si prega di procedere al saldo entro e non oltre il 30/05/2024."


def test_le_date_di_pagamento_non_diventano_termini():
    for testo in (CBILL, PAGOPA, FATTURA):
        assert not [f for f in estrai_date(testo, origine="nativo") if f.campo in {"termine", "udienza"}], testo


def test_i_termini_del_processo_restano():
    assert [f.campo for f in estrai_date("Il giudice assegna termine fino al 10/03/2026 per il deposito di note.", origine="nativo")] == ["termine"]
    ingiunzione = "ingiunge di pagare la somma di Euro 1.000,00 entro il 10/03/2026, avvertendo che può essere proposta opposizione."
    assert [f.campo for f in estrai_date(ingiunzione, origine="nativo")] == ["termine"]
    assert [f.campo for f in estrai_date("Il giudice fissa l'udienza del 12/05/2026 ore 9.30.", origine="nativo")] == ["udienza"]


def test_riconvalida_dei_termini_gia_registrati_dal_brano_salvato():
    """I fatti già in archivio si respingono con la riconvalida: il brano salvato basta a decidere."""
    for testo, valore in ((CBILL, "2025-01-09"), (FATTURA, "2024-05-30")):
        giorno = valore[8:10] + "/" + valore[5:7] + "/" + valore[:4]
        inizio = testo.index(giorno)
        motivo = esclusione_data_salvata(brano(testo, inizio, inizio + 10), valore)
        assert "pagamento" in motivo and "non termine processuale" in motivo
