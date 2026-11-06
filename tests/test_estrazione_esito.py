"""L'esito della sentenza dal dispositivo, come fatti «evento» dell'archivio delle letture (forma della sentenza Alessi)."""

from pct.archivio_letture.estrazione_esito import estrai_esito
from pct.registro_letture.fatti_repository import CATEGORIE

SENTENZA = ("REPUBBLICA ITALIANA IL TRIBUNALE DI VELLETRI ha pronunciato la seguente S E N T E N Z A ex art. 429 c.p.c. "
            "nella causa iscritta al n. 2539, del Ruolo Generale ... P.Q.M. Il Giudice del Lavoro, definitivamente pronunciando: "
            "-condanna la parte convenuta a emettere i buoni; -condanna la parte convenuta al pagamento delle spese processuali, "
            "che liquida in euro 250,00, oltre accessori di legge, da distrarsi in favore dei procuratori antistatari. "
            "Velletri, 7 ottobre 2026 Il giudice dott. X")


def test_esito_e_spese_come_fatti_ammessi_dall_archivio():
    fatti = {f.campo: f for f in estrai_esito(SENTENZA, origine="nativo")}
    assert fatti["esito_sentenza"].valore == "accoglimento"
    assert fatti["spese_sentenza"].valore == "condanna;importo=250,00;distrazione"
    assert all(f.categoria in CATEGORIE and f.verifica == "verificata" for f in fatti.values())


def test_un_atto_che_non_e_una_sentenza_non_ha_esito():
    assert estrai_esito("RICORSO EX ART. 414 C.P.C. ... P.Q.M. si chiede che il giudice accolga", origine="nativo") == []
