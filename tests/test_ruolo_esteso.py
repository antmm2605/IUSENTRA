"""Ruolo scritto per esteso nell'epigrafe delle sentenze di tribunale (sentenza Alessi, RG 2539/2025)."""

from pct.archivio_letture.estrazione_ruolo import estrai_ruoli


def _valori(testo):
    return [f.valore for f in estrai_ruoli(testo, origine="nativo")]


def test_forma_estesa_della_sentenza():
    assert _valori("SENTENZA ex art. 429 c.p.c. nella causa iscritta al n. 2539, del Ruolo Generale Affari Contenziosi "
                   "dell’anno 2025, pendente TRA") == ["2539/2025"]


def test_varianti_della_forma_estesa():
    assert _valori("causa iscritta al n. 77 del ruolo generale degli affari civili per l'anno 2023") == ["77/2023"]
    assert _valori("la causa n. 1234/2024 del Ruolo Generale") == ["1234/2024"]


def test_numeri_che_non_sono_ruoli_restano_fuori():
    assert _valori("al n. 3 del registro delle imprese dell'anno 2020") == []
    assert _valori("R.G. n. 12/2026") == ["12/2026"]
