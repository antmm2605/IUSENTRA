"""Controlli puri del guardiano della catena e registro dei controlli (dati fittizi, esempi da norme vigenti)."""

from __future__ import annotations

from datetime import date

from pct.catena import guardiano as g
from pct.catena.registro import AVVISO, CHIUSA, RIPARATA, RegistroGuardiano

OGGI = date(2026, 11, 19)
DECRETO_415 = {"documento_id": "DEC", "documento": "Decreto di fissazione udienza.pdf", "brano": "FISSA l'udienza",
               "data": "09/10/2026"}
NORMA_415 = [{"norma": "art. 415, commi 4–6, c.p.c."}]


def conclusione(codice, cosa, scadenza, *, onerato="noi", stato="da_fare", natura="ordinatorio", dubbi=(), **altro):
    return {"codice": codice, "cosa": cosa, "stato": stato, "onerato_codice": onerato, "letto": DECRETO_415,
            "norme": NORMA_415, "termine": {"scadenza_iso": scadenza, "natura": natura, "scaduto": False},
            "dubbi": [{"codice": d, "testo": d, "manca": "x"} for d in dubbi], **altro}


NOTIFICA = conclusione("notifica_ricorso_decreto_415", "Notificare alla controparte il ricorso con il decreto", "2027-01-08")
COSTITUZIONE = conclusione("costituzione_convenuto", "Costituzione del convenuto con memoria difensiva", "2027-01-29",
                           onerato="controparte")
UDIENZA_NOTE = {"data": "09/02/2027", "ora": "", "modalita": "sostituita da note scritte (art. 127-ter c.p.c.)",
                "documento": "Decreto di fissazione udienza.pdf", "documento_id": "DEC"}


def lettura(conclusioni=(), udienze=(), passi=None, fase="udienza_fissata"):
    return {"ragionamento": {"impronta": "abc123", "conclusioni": list(conclusioni), "udienze": list(udienze),
                             "fase": {"codice": fase, "descrizione": fase}},
            "prossimi_passi": passi if passi is not None else [{"azione": c["cosa"]} for c in conclusioni
                                                               if c["stato"] == "da_fare" and c["onerato_codice"] == "noi"]}


def stato(**campi):
    return g.StatoFascicolo(fascicolo_id="F1", oggi=OGGI, **campi)


def codici(incoerenze):
    return [(i.codice, i.riparazione) for i in incoerenze]


PROPOSTA = "PEC_TERMINE_PROPOSTO:abc:LAV_415_NOTIFICA_TRENTA_GIORNI"


def test_termine_certo_dello_studio_senza_scadenza_si_crea_con_data_e_norma():
    esito = g.controlla(stato(lettura=lettura([NOTIFICA])))
    assert codici(esito) == [("termine_certo_senza_scadenza", g.CREA_SCADENZA)]
    assert esito[0].dati["data"] == "2027-01-08" and esito[0].dati["norma"] == "art. 415, commi 4–6, c.p.c."
    nota = g.nota_scadenza(esito[0].dati, "abc123")
    assert nota.startswith("RAGIONAMENTO:notifica_ricorso_decreto_415:abc123") and "art. 415" in nota


def test_termine_certo_presente_con_stessa_data_non_e_incoerente():
    scadenza = {"id": "S1", "titolo": "Notifica di ricorso e decreto", "data": "2027-01-08", "stato": "APERTO", "note": PROPOSTA}
    assert g.controlla(stato(lettura=lettura([NOTIFICA]), scadenze=[scadenza])) == []


def test_proposta_in_bozza_automatica_si_conferma_quella_dell_avvocato_e_un_avviso():
    bozza = {"id": "S1", "titolo": "Notifica di ricorso e decreto", "data": "2027-01-08", "stato": "BOZZA", "note": PROPOSTA}
    assert codici(g.controlla(stato(lettura=lettura([NOTIFICA]), scadenze=[bozza]))) == [("termine_certo_in_bozza", g.CONFERMA_BOZZA)]
    presa = {**bozza, "id_utente_responsabile": "avv1"}
    assert codici(g.controlla(stato(lettura=lettura([NOTIFICA]), scadenze=[presa]))) == [("termine_certo_in_bozza", "")]


def test_termine_con_dubbio_del_computo_o_scaduto_non_si_scrive():
    dubbio = conclusione("notifica_ricorso_decreto_415", "Notificare", "2027-01-08", dubbi=("destinazione_notifica_ignota",))
    passato = conclusione("note_127ter", "Depositare le note", "2026-11-10")
    assert g.controlla(stato(lettura=lettura([dubbio, passato], passi=[]))) == []


def test_termine_della_controparte_proposto_si_scarta_ma_quello_dell_avvocato_resta():
    """Art. 416 c.p.c.: la costituzione del convenuto grava sulla controparte se il cliente è il ricorrente."""
    bozza = {"id": "S2", "titolo": "Costituzione del convenuto con memoria difensiva", "data": "2027-01-29",
             "stato": "BOZZA", "note": "PEC_TERMINE_PROPOSTO:abc:LAV_416_COSTITUZIONE"}
    esito = g.controlla(stato(lettura=lettura([COSTITUZIONE]), scadenze=[bozza]))
    assert codici(esito) == [("termine_della_controparte", g.SCARTA_BOZZA)]
    dell_avvocato = {**bozza, "stato": "APERTO", "note": "scritta a mano"}
    esito = g.controlla(stato(lettura=lettura([COSTITUZIONE]), scadenze=[dell_avvocato]))
    assert codici(esito) == [("termine_della_controparte", "")] and "resta com'è" in esito[0].perche


def test_scadenza_scritta_dal_guardiano_superata_da_un_nuovo_calcolo_si_annulla():
    vecchia = {"id": "S3", "titolo": "Notificare", "data": "2026-12-20", "stato": "APERTO",
               "note": "RAGIONAMENTO:notifica_ricorso_decreto_415:abc\nFonte: x"}
    esito = codici(g.controlla(stato(lettura=lettura([NOTIFICA]), scadenze=[vecchia])))
    assert ("scadenza_superata", g.ANNULLA_SCADENZA) in esito and ("termine_certo_senza_scadenza", g.CREA_SCADENZA) in esito


def test_opposizione_nel_giorno_dell_udienza_e_l_udienza():
    udienza = {"data": "15/01/2027", "ora": "10:00", "modalita": "in presenza", "documento": "Decreto.pdf", "documento_id": "D"}
    scadenza = {"id": "S4", "titolo": "Opposizione a decreto ingiuntivo", "data": "2027-01-15", "stato": "APERTO",
                "note": "ARCHIVIO_FATTO:f1\nFonte: x"}
    appuntamento = {"id": "A1", "tipo": "UDIENZA", "data": "2027-01-15", "stato": "PROGRAMMATO", "note": ""}
    esito = g.controlla(stato(lettura=lettura(udienze=[udienza], passi=[]), scadenze=[scadenza], appuntamenti=[appuntamento]))
    assert codici(esito) == [("opposizione_e_udienza", g.ANNULLA_SCADENZA)]


def test_udienza_futura_del_modello_in_agenda_con_la_modalita_disposta():
    esito = g.controlla(stato(lettura=lettura(udienze=[UDIENZA_NOTE], passi=[])))
    assert codici(esito) == [("udienza_non_in_agenda", g.CREA_UDIENZA)] and esito[0].dati["modalita"] == "note_scritte"
    in_presenza = {"id": "A2", "tipo": "UDIENZA", "data": "2027-02-09", "stato": "PROGRAMMATO", "modalita": "",
                   "note": "ARCHIVIO_FATTO:f2"}
    esito = g.controlla(stato(lettura=lettura(udienze=[UDIENZA_NOTE], passi=[]), appuntamenti=[in_presenza]))
    assert codici(esito) == [("modalita_udienza_diversa", g.AGGIORNA_MODALITA)]
    note = {**in_presenza, "modalita": "note_scritte"}
    assert g.controlla(stato(lettura=lettura(udienze=[UDIENZA_NOTE], passi=[]), appuntamenti=[note])) == []


def test_passo_gia_fatto_con_prova_e_scadenza_ancora_aperta():
    fatta = conclusione("notifica_ricorso_decreto_415", "Notificare alla controparte il ricorso con il decreto", "2027-01-08",
                        stato="fatto", prova_notifica={"ricevuta": "RdAC"})
    aperta = {"id": "S5", "titolo": "Notifica di ricorso e decreto", "data": "2027-01-08", "stato": "APERTO", "note": PROPOSTA}
    esito = codici(g.controlla(stato(lettura=lettura([fatta], passi=[{"azione": fatta["cosa"]}]), scadenze=[aperta])))
    assert ("passo_gia_fatto", g.RICALCOLO) in esito and ("scadenza_di_adempimento_provato", g.RICONCILIA_ADEMPIMENTI) in esito


def test_stato_del_fascicolo_coerente_con_la_causa_solo_avviso():
    esito = g.controlla(stato(lettura=lettura(udienze=[UDIENZA_NOTE], passi=[]), stato_fascicolo="DEFINITO",
                              appuntamenti=[{"id": "A", "tipo": "UDIENZA", "data": "2027-02-09", "stato": "", "modalita": "note_scritte"}]))
    assert codici(esito) == [("definito_con_udienza_futura", "")]
    esito = g.controlla(stato(lettura=lettura(passi=[{"azione": "Depositare la memoria"}], fase="atto_introduttivo_depositato"),
                              stato_fascicolo="DEFINITO"))
    assert codici(esito) == [("definito_senza_decisione", "")]
    # Un provvedimento (estinzione, conciliazione) senza sentenza riconosciuta non basta a dire che la causa pende.
    assert g.controlla(stato(lettura=lettura(passi=[{"azione": "x"}], fase="provvedimenti_presenti"), stato_fascicolo="DEFINITO")) == []
    assert g.controlla(stato(lettura=lettura(passi=[], fase="decisa"), stato_fascicolo="DEFINITO")) == []
    esito = g.controlla(stato(lettura=lettura(passi=[], fase="giudicato_da_verificare"), stato_fascicolo="IN_CORSO",
                              credito_incassato=True))
    assert codici(esito) == [("in_corso_con_giudicato_e_incasso", "")]


def test_quadro_freschezza_e_bozze():
    corrente = lettura([NOTIFICA])
    scadenza = {"id": "S1", "titolo": "Notifica", "data": "2027-01-08", "stato": "APERTO", "note": PROPOSTA}
    quadro = {"righe": [{"tema": "prossimo_passo", "testo": "Preparare l'udienza del 09/02/2027"}]}
    pannelli = [{"pannello": "conto-economico", "salvata": "v1", "attesa": "v2", "tentata": ""},
                {"pannello": "lettura", "salvata": "v2", "attesa": "v2", "tentata": ""}]
    bozze = [{"chiave": "b1", "stato": "pronta", "titolo": "Note scritte", "passi": [{"azione": "Depositare le note"}]},
             {"chiave": "b2", "stato": "modificata", "titolo": "Altro", "passi": [{"azione": "Altro"}]}]
    esito = codici(g.controlla(stato(lettura=corrente, scadenze=[scadenza], quadro=quadro, pannelli=pannelli, bozze=bozze)))
    assert esito == [("quadro_diverso_dalla_lettura", g.RICALCOLO), ("pannello_superato", g.RICALCOLO),
                     ("bozza_senza_passo", g.PREPARA_BOZZE)]


def test_senza_lettura_pronta_si_controllano_solo_freschezza_e_catalogo():
    pannelli = [{"pannello": "lettura", "salvata": "v1", "attesa": "v2", "tentata": ""}]
    catalogo = [{"documento": "sentenza.pdf", "voce": "Sentenza", "quando": "2026-11-19T10:00:00+00:00"}]
    esito = codici(g.controlla(stato(lettura=None, pannelli=pannelli, catalogo_dopo_letture=catalogo)))
    assert esito == [("pannello_superato", g.RICALCOLO), ("catalogo_dopo_le_letture", g.RICONVALIDA_CICLO)]


def test_chiave_stabile_e_registro_dei_controlli(tmp_path):
    prima = g.controlla(stato(lettura=lettura([NOTIFICA])))
    seconda = g.controlla(stato(lettura=lettura([NOTIFICA])))
    assert prima[0].chiave == seconda[0].chiave
    registro = RegistroGuardiano(tmp_path / "g.sqlite")
    voce = {**prima[0].come_dizionario(), "esito_riparazione": "riparata: scadenza X creata"}
    avviso = {**g.controlla(stato(lettura=lettura(passi=[{"azione": "Depositare il ricorso"}], fase="preparatoria"), stato_fascicolo="DEFINITO"))[0].come_dizionario()}
    conteggi = registro.registra_giro("F1", origine="test", impronta="i1", esito="controllato", voci=[voce, avviso], versione=g.VERSIONE)
    assert conteggi == {"incoerenze": 2, "riparate": 1, "avvisi": 1}
    assert [a["codice"] for a in registro.avvisi("F1")] == ["definito_senza_decisione"]
    assert registro.tentativi("F1", voce["chiave"]) == 1
    # Il giro dopo non vede più nulla: le incoerenze si chiudono, il registro le conserva.
    registro.registra_giro("F1", origine="test", impronta="i2", esito="controllato", voci=[], versione=g.VERSIONE)
    stati = {i["codice"]: i["stato"] for i in registro.incoerenze("F1")}
    assert stati == {"termine_certo_senza_scadenza": CHIUSA, "definito_senza_decisione": CHIUSA}
    assert registro.riepilogo()["termine_certo_senza_scadenza"] == {CHIUSA: 1}
    assert [r["impronta"] for r in registro.giri(fascicolo_id="F1")] == ["i2", "i1"]
    assert RIPARATA and AVVISO


def test_in_aggiornamento_non_chiude_le_incoerenze(tmp_path):
    registro = RegistroGuardiano(tmp_path / "g.sqlite")
    voce = g.controlla(stato(lettura=lettura(passi=[{"azione": "Depositare il ricorso"}], fase="preparatoria"), stato_fascicolo="DEFINITO"))[0].come_dizionario()
    registro.registra_giro("F1", origine="test", impronta="i1", esito="controllato", voci=[voce], versione=g.VERSIONE)
    registro.registra_giro("F1", origine="test", impronta="i2", esito="in_aggiornamento", voci=[], versione=g.VERSIONE)
    assert [a["codice"] for a in registro.avvisi("F1")] == ["definito_senza_decisione"]


def test_senza_avvocati_dello_studio_la_parte_onerata_non_e_certa_e_non_si_scrive_nulla():
    esito = g.controlla(stato(lettura=lettura([NOTIFICA, COSTITUZIONE]), studio_con_avvocati=False))
    assert codici(esito) == [("studio_senza_avvocati", "")]


def test_la_scadenza_scritta_dal_guardiano_porta_la_stessa_norma_del_modello():
    nostra = {"id": "S9", "titolo": "Notificare", "data": "2027-01-08", "stato": "APERTO",
              "note": "RAGIONAMENTO:notifica_ricorso_decreto_415:abc\nFonte: x\nNorma: art. 414 c.p.c."}
    esito = g.controlla(stato(lettura=lettura([NOTIFICA]), scadenze=[nostra]))
    assert codici(esito) == [("norma_diversa", g.AGGIORNA_NORMA)]
    giusta = {**nostra, "note": "RAGIONAMENTO:notifica_ricorso_decreto_415:abc\nFonte: x\nNorma: art. 415, commi 4–6, c.p.c."}
    assert g.controlla(stato(lettura=lettura([NOTIFICA]), scadenze=[giusta])) == []


def test_responsabile_automatico_non_e_una_decisione_dell_avvocato():
    """«ripasso-2484», «scheduler»: lavori del software, non persone (misura sui dati reali del 19/11/2026)."""
    bozza = {"id": "S2", "titolo": "Costituzione del convenuto con memoria difensiva", "data": "2027-01-29", "stato": "BOZZA",
             "note": "PEC_TERMINE_PROPOSTO:abc:LAV_416_COSTITUZIONE", "id_utente_responsabile": "ripasso-2484",
             "responsabile_umano": False}
    assert codici(g.controlla(stato(lettura=lettura([COSTITUZIONE]), scadenze=[bozza]))) == [("termine_della_controparte", g.SCARTA_BOZZA)]
    umano = {**bozza, "responsabile_umano": True}
    assert codici(g.controlla(stato(lettura=lettura([COSTITUZIONE]), scadenze=[umano]))) == [("termine_della_controparte", "")]


def test_proposta_doppia_di_un_termine_gia_aperto_si_scarta():
    aperta = {"id": "S1", "titolo": "Notificare ricorso e decreto", "data": "2027-01-08", "stato": "APERTO",
              "note": "Obbligo di notifica letto dal documento"}
    doppia = {"id": "S2", "titolo": "Notifica di ricorso e decreto", "data": "2027-01-08", "stato": "BOZZA", "note": PROPOSTA}
    esito = g.controlla(stato(lettura=lettura([NOTIFICA]), scadenze=[aperta, doppia]))
    assert codici(esito) == [("proposta_doppia", g.SCARTA_BOZZA)] and esito[0].dati["scadenza_id"] == "S2"


def test_udienza_annullata_in_agenda_non_si_ricrea_e_le_note_valgono_come_udienza():
    annullata = {"id": "A1", "tipo": "UDIENZA", "data": "2027-02-09", "stato": "ANNULLATO", "modalita": "note_scritte", "note": ""}
    esito = g.controlla(stato(lettura=lettura(udienze=[UDIENZA_NOTE], passi=[]), appuntamenti=[annullata]))
    assert codici(esito) == [("udienza_annullata_in_agenda", "")]
    note = {"id": "S3", "titolo": "Deposito note scritte ex art. 127-ter c.p.c. - RG 1571/2026", "data": "2027-02-09",
            "stato": "APERTO", "note": "PEC_AUDIT:x"}
    assert g.controlla(stato(lettura=lettura(udienze=[UDIENZA_NOTE], passi=[]), scadenze=[note])) == []
