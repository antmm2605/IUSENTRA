"""Le parti lette nell'epigrafe degli atti: lato dello studio, controparti, difensori, anagrafica.

Testi sintetici: nomi e codici fiscali inventati (i codici sono calcolati per
persone fittizie, così il carattere di controllo è valido).
"""

from __future__ import annotations

from pct.archivio_letture.collaudo import Contesto
from pct.archivio_letture.estrazione_parti import cf_valido, estrai_parti, fatti_parti
from pct.archivio_letture.estrazione_ruolo import estrai_ruoli
from pct.archivio_letture.parti_fascicolo import cognome_e_nome, confronta_con_fascicolo, parti_lette, tipo_soggetto
from pct.codice_fiscale import calcola


def _cf(cognome: str, nome: str, sesso: str = "F") -> str:
    return calcola(cognome=cognome, nome=nome, sesso=sesso, data_nascita="1970-04-07", luogo_nascita="Milano")["codice_fiscale"]


CF_VERDI = _cf("Verdi", "Giulia")
CF_NERI = _cf("Neri", "Paolo", "M")
CF_BLU = _cf("Blu", "Franco", "M")

CITAZIONE = f"""TRIBUNALE DI MILANO
ATTO DI CITAZIONE
Verdi Giulia, c.f. {CF_VERDI}, nata a Milano il 07.04.1970 e Neri Paolo, c.f. {CF_NERI}, nato a
Milano il 07.04.1970, entrambi rappresentati e difesi dall'Avv. Carlo
Bianchi (c.f. BNCCRL60A01F205X) con procura allegata al presente atto
premesso che
le parti hanno stipulato un contratto preliminare.
Tanto premesso, Verdi Giulia e Neri Paolo, come sopra rappresentati, con il presente atto
CITANO
Blu Franco, c.f. {CF_BLU}, residente in Via Roma 1, Milano, a comparire dinanzi al Tribunale di Milano
"""

RICORSO_TAR = f"""TRIBUNALE AMMINISTRATIVO REGIONALE PER LA LOMBARDIA
RICORSO PER L'OTTEMPERANZA
PER
Verdi Giulia, c.f. {CF_VERDI}, rappresentata e difesa dall'Avv. Carlo Bianchi
CONTRO
MINISTERO DELL'ISTRUZIONE E DEL MERITO, c.f. 80185250588, in persona del Ministro pro tempore,
rappresentato e difeso ex lege dall'Avvocatura Distrettuale dello Stato di Milano
per l'esecuzione della sentenza n. 123/2024
IN FATTO
"""

SENTENZA_TAR = """N. 01729/2025 REG.RIC.
REPUBBLICA ITALIANA
Il Tribunale Amministrativo Regionale per la Lombardia
ha pronunciato la presente SENTENZA sul ricorso numero di registro generale 1729 del 2025, proposto da Anna Rosa, rappresentata e difesa dall'avvocato Carlo Bianchi, con domicilio digitale come da PEC da Registri di Giustizia;
contro
Ministero dell'Istruzione e del Merito, rappresentato e difeso dall'Avvocatura Distrettuale dello Stato di Milano;
per l'annullamento del decreto
Visti gli atti
N. 00321/2025 REG.PROV.COLL.
"""

NOTE_SCRITTE = """TRIBUNALE CIVILE DI PALMI
Note per la trattazione scritta
Procedimento R.G. n. 1025/2024
Rosa Anna e Viola Marco, rappresentati e difesi
dall'Avv. Carlo Bianchi,
- attori -
contro
Gialli Sara nata a Milano il 22.08.1989 ed ivi domiciliata.
- convenuta contumace -
**************
"""


def test_cf_valido_riconosce_il_carattere_di_controllo():
    assert cf_valido(CF_VERDI)
    assert not cf_valido(CF_VERDI[:-1] + ("A" if CF_VERDI[-1] != "A" else "B"))


def test_citazione_con_cita_ha_due_assistiti_e_il_convenuto():
    parti = estrai_parti(CITAZIONE, avvocati_studio=["Carlo Bianchi"])
    assistiti = [p for p in parti if p.ruolo == "assistito"]
    assert {p.nome for p in assistiti} == {"Verdi Giulia", "Neri Paolo"}
    assert all(p.difensore == "Carlo Bianchi" for p in assistiti)
    assert [(p.nome, p.codice_fiscale) for p in parti if p.ruolo == "controparte"] == [("Blu Franco", CF_BLU)]


def test_ricorso_tar_contro_ministero_difeso_dall_avvocatura():
    parti = estrai_parti(RICORSO_TAR, avvocati_studio=["Avv. Carlo Bianchi"])
    assert [(p.ruolo, p.nome) for p in parti if p.ruolo == "assistito"] == [("assistito", "Verdi Giulia")]
    ministero = next(p for p in parti if p.ruolo == "controparte")
    assert ministero.nome.upper().startswith("MINISTERO DELL'ISTRUZIONE")
    assert ministero.codice_fiscale == "80185250588"
    assert "Avvocatura Distrettuale dello Stato" in ministero.difensore
    assert any(p.ruolo == "difensore_controparte" and "Avvocatura" in p.nome for p in parti)


def test_sentenza_tar_proposto_da_a_meta_riga_e_ruolo_reg_ric():
    parti = estrai_parti(SENTENZA_TAR, avvocati_studio=["Carlo Bianchi"])
    assert [p.nome for p in parti if p.ruolo == "assistito"] == ["Anna Rosa"]
    assert any(p.ruolo == "controparte" and p.nome.startswith("Ministero") for p in parti)
    ruoli = estrai_ruoli(SENTENZA_TAR, origine="nativo")
    assert [f.valore for f in ruoli] == ["1729/2025"], "REG.PROV.COLL. non è un ruolo"


def test_nomi_congiunti_prima_di_rappresentati_e_intestazione_ignorata():
    parti = estrai_parti("STUDIO LEGALE BIANCHI\nAvvocato Carlo Bianchi\n\n" + NOTE_SCRITTE, avvocati_studio=["Carlo Bianchi"])
    assert [p.nome for p in parti if p.ruolo == "assistito"] == ["Rosa Anna", "Viola Marco"]
    assert all(p.difensore == "Carlo Bianchi" for p in parti if p.ruolo == "assistito")
    assert [p.nome for p in parti if p.ruolo == "controparte"] == ["Gialli Sara"]
    assert not any("Studio" in p.nome or "Avvocato" in p.nome for p in parti)


def test_senza_difensore_dello_studio_il_lato_si_riconosce_dal_cliente_o_resta_da_confermare():
    col_cliente = estrai_parti(CITAZIONE, avvocati_studio=[], cliente="Giulia Verdi")
    assert {p.nome for p in col_cliente if p.ruolo == "assistito"} == {"Verdi Giulia", "Neri Paolo"}
    senza = estrai_parti(CITAZIONE, avvocati_studio=[], cliente="")
    assert {p.ruolo for p in senza} == {"parte"}


def test_fatti_parti_verificate_solo_con_codice_fiscale_valido():
    fatti = fatti_parti(CITAZIONE, origine="nativo", avvocati_studio=["Carlo Bianchi"])
    assert all(f.categoria == "parte" for f in fatti)
    verdi = next(f for f in fatti if f.valore == "Verdi Giulia")
    assert verdi.verifica == "verificata" and verdi.valore_letto == CF_VERDI
    senza_cf = fatti_parti(NOTE_SCRITTE, origine="nativo", avvocati_studio=["Carlo Bianchi"])
    assert all(f.verifica == "plausibile" for f in senza_cf if f.campo == "assistito")


def test_cognome_e_nome_dal_codice_fiscale():
    assert cognome_e_nome("Verdi Giulia", CF_VERDI) == ("Verdi", "Giulia")
    assert cognome_e_nome("Giulia Verdi", CF_VERDI) == ("Verdi", "Giulia")
    assert cognome_e_nome("Giulia Verdi", "") == ("Giulia Verdi", "")


def test_tipo_soggetto():
    assert tipo_soggetto("MINISTERO DELL'ISTRUZIONE") == "PUBBLICA_AMMINISTRAZIONE"
    assert tipo_soggetto("Alfa S.r.l.") == "PERSONA_GIURIDICA"
    assert tipo_soggetto("Carlo Bianchi", ruolo="difensore_controparte") == "PROFESSIONISTA"
    assert tipo_soggetto("Verdi Giulia", CF_VERDI) == "PERSONA_FISICA"


def test_motore_documenti_legge_le_parti_ma_non_quelle_di_un_precedente():
    from pct.archivio_letture.motore_documenti import leggi_testo

    contesto = Contesto(avvocati_studio=("Carlo Bianchi",), cliente="Verdi Giulia")
    fatti = leggi_testo(CITAZIONE, origine="nativo", contesto=contesto, nome="citazione.pdf")
    assert {f.valore for f in fatti if f.categoria == "parte" and f.campo == "assistito"} == {"Verdi Giulia", "Neri Paolo"}


def test_parti_lette_e_confronto_con_il_fascicolo():
    fatti = fatti_parti(CITAZIONE, origine="nativo", avvocati_studio=["Carlo Bianchi"])
    for indice, fatto in enumerate(fatti):
        fatto.id = f"f{indice}"
        fatto.oggetto_id = "doc1"
    voci = confronta_con_fascicolo(parti_lette(fatti), nome_cliente="Giulia Verdi", parti_esistenti=[])
    per_nome = {v.nome: v for v in voci}
    assert per_nome["Verdi Giulia"].e_il_cliente
    assert per_nome["Neri Paolo"].certa and not per_nome["Neri Paolo"].e_il_cliente
    assert per_nome["Blu Franco"].ruolo == "controparte" and per_nome["Blu Franco"].certa


def test_consegna_parti_crea_soggetti_senza_doppioni(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from pct.soggetti import GestioneSoggetti
    from web.services import parti_lette_runtime

    gestione = GestioneSoggetti(str(tmp_path / "soggetti.json"), str(tmp_path / "parti.json"))
    aggiornati: dict = {}
    monkeypatch.setattr(parti_lette_runtime, "_completa_intestazione", lambda fascicolo, voci: aggiornati.update({v.nome: v.ruolo for v in voci}) or {})
    fascicolo = SimpleNamespace(id="F1", nome_cliente="Giulia Verdi", controparte="", avvocato_controparte="")
    fatti = fatti_parti(CITAZIONE, origine="nativo", avvocati_studio=["Carlo Bianchi"])
    for indice, fatto in enumerate(fatti):
        fatto.id = f"f{indice}"
        fatto.oggetto_id = "doc1"
    certi = [f for f in fatti if f.verifica == "verificata"]
    esiti = {e["fatto_id"]: e for e in parti_lette_runtime.consegna_parti(fascicolo, certi, gestione=gestione)}
    verdi = next(f for f in certi if f.valore == "Verdi Giulia")
    assert esiti[verdi.id]["stato"] == "non_pertinente"  # è il cliente
    parti = {(p.ruolo.value, s.nome_completo) for p, s in gestione.parti_fascicolo("F1")}
    assert parti == {("ASSISTITO", "Neri Paolo"), ("CONTROPARTE", "Blu Franco")}
    blu = next(s for _, s in gestione.parti_fascicolo("F1") if s.codice_fiscale == CF_BLU)
    assert (blu.cognome, blu.nome) == ("Blu", "Franco")
    # Seconda consegna: nessun doppione, i fatti risultano già consegnati.
    di_nuovo = parti_lette_runtime.consegna_parti(fascicolo, certi, gestione=gestione)
    assert len(gestione.tutti()) == 2
    assert all(e["stato"] in {"consegnato", "non_pertinente"} for e in di_nuovo)
