"""Collaudo del 10/11/2026 (G-6, G-7, G-11): parte onerata, art. 416 solo alla prima udienza, oggetto del deposito,
decorrenze anteriori all'atto. Esempi fittizi costruiti sulle formule reali dei provvedimenti."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from pct.archivio_letture.ancoraggio import esclusione_data_salvata
from pct.archivio_letture.date_incoerenti import motivo_incoerenza
from pct.archivio_letture.estrazione_date import estrai_date
from pct.provvedimenti import esamina_provvedimento, proposte_scadenziario
from pct.provvedimenti.coerenza_termini import (
    COMUNE, CONTROPARTE, INCERTA, STUDIO, motivo_416_su_rinvio, oggetto_del_deposito, parte_onerata, titolo_deposito,
)
from pct.provvedimenti.parte_assistita import ruolo_da_relata
from pct.scadenze_titolo_avvocato import CHIAVE_TITOLO_AVVOCATO
from pct.riconvalida_proposte_giudice import ANNULLA, MARCATORE_RICONVALIDA, TITOLO, esito_proposta, riconvalida_proposte_giudice

DECRETO_415_NOTE = (
    "Causa n. 77/2026 RG Lav. TRIBUNALE DI ROCCAVERDE SEZIONE LAVORO "
    "Il giudice dott. Mario Neri, letto il ricorso che precede; visto l'art. 415 c.p.c.; visto l'art. 127 ter c.p.c. che consente "
    "la sostituzione, con il deposito di note scritte contenenti le sole istanze e conclusioni, delle udienze civili, "
    "FISSA il termine per il deposito delle note in sostituzione dell'udienza nel giorno 06/10/2026, alle ore 14.00. "
    "Assegna alla parte ricorrente termine di dieci giorni, dalla data di comunicazione del presente provvedimento, per la notifica "
    "alla parte convenuta del ricorso e del decreto di fissazione dell'udienza. Avverte il convenuto che ha facoltà di costituirsi in "
    "giudizio fino a 10 giorni prima del termine sopra indicato e che entro lo stesso termine, a pena di decadenza, può proporre le "
    "proprie eccezioni ed indicare i propri mezzi di prova. Roccaverde, 22/06/2026. Il giudice dott. Mario Neri"
)

ORDINANZA_421 = (
    "TRIBUNALE DI ROCCAVERDE Sezione Lavoro R.G. n. 77/2026 Il Giudice del lavoro, letti gli atti, visto l'art. 421 c.p.c., "
    "ASSEGNA a parte ricorrente termine di ulteriori 10 giorni per depositare le graduatorie aggiornate nelle quali risulti il "
    "proprio nominativo o ulteriore prova della permanenza nel sistema scolastico; "
    "RINVIA la causa all'udienza del 23/11/2026 ore 14:00, sostituita dal deposito di note scritte ex art. 127-ter c.p.c. "
    "Roccaverde, 04/11/2026 Il Giudice dott. Mario Neri"
)


def _codici(esito, oggi):
    return [(b.code, b.due_date) for b in proposte_scadenziario(esito, oggi=oggi, fascicolo_id="F1")]


# ── G-6: l'art. 416 si conta dalla prima udienza, mai dal rinvio ─────────────────────────


def test_decreto_415_riletto_dopo_la_prima_udienza_non_conta_la_costituzione_dal_rinvio():
    oggi = date(2026, 11, 8)
    esito = esamina_provvedimento(DECRETO_415_NOTE, oggi=oggi, fascicolo_id="F1", rg="77/2026", materia="LAVORO",
                                  prossima_udienza="2026-11-23")
    costituzione = [v for v in esito.voci if v.codice == "LAV_416_COSTITUZIONE"]
    # contata dal 06/10/2026 del decreto (già decorsa), non dal rinvio del 23/11/2026 del fascicolo
    assert [v.giorno for v in costituzione] == [date(2026, 9, 25)]
    assert _codici(esito, oggi) == []


def test_decreto_415_letto_in_tempo_conta_dalla_sua_udienza():
    oggi = date(2026, 6, 24)
    esito = esamina_provvedimento(DECRETO_415_NOTE, oggi=oggi, fascicolo_id="F1", rg="77/2026", materia="LAVORO")
    assert ("LAV_416_COSTITUZIONE", "2026-09-25") in _codici(esito, oggi)


def test_motivo_416_su_rinvio():
    assert motivo_416_su_rinvio("LAV_416_COSTITUZIONE", udienza_di_calcolo=date(2026, 11, 23), udienza_del_decreto=date(2026, 10, 6))
    assert not motivo_416_su_rinvio("LAV_416_COSTITUZIONE", udienza_di_calcolo=date(2026, 10, 6), udienza_del_decreto=date(2026, 10, 6))
    assert not motivo_416_su_rinvio("CIV_MEMORIA_171_TER_1", udienza_di_calcolo=date(2026, 11, 23), udienza_del_decreto=date(2026, 10, 6))


# ── G-6: la parte onerata ────────────────────────────────────────────────────────────


def test_parte_onerata_per_tutte_le_posizioni():
    assert parte_onerata("convenuto", "ricorrente") == CONTROPARTE
    assert parte_onerata("resistente", "ricorrente") == CONTROPARTE
    assert parte_onerata("ricorrente", "ricorrente") == STUDIO
    assert parte_onerata("appellante", "resistente") == CONTROPARTE
    assert parte_onerata("opposto", "resistente") == STUDIO
    assert parte_onerata("parti", "ricorrente") == COMUNE
    assert parte_onerata("convenuto", "") == INCERTA


RELATA = (
    "RELATA DI NOTIFICA EX ART. 3-BIS L. 53/1994 Io sottoscritto Avv. PAOLO VERDI, difensore per mandato come in atti di: "
    "Anna ROSSI C.F. RSSNNA80A41H501Z; HO NOTIFICATO A 1) AVVOCATURA DISTRETTUALE DELLO STATO (difensore di MINISTERO) "
    "il ricorso ex art. 414 c.p.c. e il decreto di fissazione dell'udienza."
)


def test_ruolo_dalla_relata_dello_studio():
    assert ruolo_da_relata(RELATA, "Rossi Anna") == "ricorrente"
    # il «difensore di» accanto al destinatario è la controparte: nessuna deduzione per il Ministero
    assert ruolo_da_relata(RELATA, "Ministero") == ""
    assert ruolo_da_relata("Io sottoscritto Avv. Paolo Verdi difensore di Anna Rossi HO NOTIFICATO la comparsa", "Anna Rossi") == ""


# ── G-7: che cosa depositare ─────────────────────────────────────────────────────────


def test_ordinanza_421_titolo_con_oggetto_del_deposito_e_norma_del_lavoro():
    oggi = date(2026, 11, 5)
    esito = esamina_provvedimento(ORDINANZA_421, oggi=oggi, comunicata_il=oggi, fascicolo_id="F1", rg="77/2026",
                                  materia="LAVORO", ruolo_cliente="ricorrente")
    [deposito] = [v for v in esito.voci if v.codice == "PROVV_DEPOSITO"]
    assert deposito.titolo == ("Depositare le graduatorie aggiornate o ulteriore prova della permanenza nel sistema scolastico "
                               "(ricorrente) — termine del giudice")
    assert deposito.norme == ("cpc_421",) and deposito.giorno == date(2026, 11, 16)


def test_oggetto_del_deposito_in_altri_riti():
    assert oggetto_del_deposito("onera parte attrice di produrre copia conforme del contratto entro il 20/12/2026") == "copia conforme del contratto"
    assert titolo_deposito("assegna termine fino al 10/12/2026 per il deposito di note autorizzate", "parti") == \
        "Depositare note autorizzate (parti) — termine del giudice"
    assert titolo_deposito("assegna termine per il deposito", "") == ""


# ── Riconvalida delle bozze già create ─────────────────────────────────────────────


@dataclass
class _Bozza:
    id: str
    titolo: str
    descrizione: str
    deadline_profile_code: str
    note: str = "PEC_TERMINE_PROPOSTO:pec_x:CODICE\nTermine proposto: ..."
    stato: str = "BOZZA"
    id_fascicolo: str = "F1"
    provenienza: dict = field(default_factory=dict)


class _Scadenziario:
    def __init__(self, righe):
        self.righe = {r.id: r for r in righe}

    def bozze(self):
        return [r for r in self.righe.values() if r.stato == "BOZZA"]

    def aggiorna(self, id_sc, **campi):
        riga = self.righe[id_sc]
        for chiave, valore in campi.items():
            setattr(riga, chiave, getattr(valore, "value", valore))
        return riga


COSTITUZIONE_SU_RINVIO = _Bozza(
    "a", "Costituzione del convenuto con memoria difensiva - almeno 10 giorni prima dell'udienza — termine assegnato dal giudice - RG 77/2026",
    "Assegnazione del termine al 06/10/2026 ore 14:00 comunicata via PEC il 23/06/2026. Calcolo: Il termine si computa a ritroso "
    "dall'evento del 23/11/2026, escludendo il giorno dell'evento. Regola giudice.costituzione; a carico di: resistente.",
    "LAV_416_COSTITUZIONE",
)
DEPOSITO_GENERICO = _Bozza(
    "b", "Termine assegnato dal giudice: deposito (ricorrente) - RG 77/2026",
    "Riassegnazione del termine comunicata via PEC il 05/11/2026. Dal provvedimento: «Assegna a parte ricorrente termine di "
    "ulteriori 10 giorni per depositare le graduatorie aggiornate nelle quali risulti il proprio nominativo o ulteriore prova della "
    "permanenza nel sistema scolastico» Regola giudice.deposito; a carico di: ricorrente.",
    "PROVV_DEPOSITO",
)


def test_esito_delle_bozze_storiche():
    assert esito_proposta(COSTITUZIONE_SU_RINVIO)[0] == ANNULLA
    azione, titolo = esito_proposta(DEPOSITO_GENERICO)
    assert azione == TITOLO and titolo.startswith("Depositare le graduatorie aggiornate") and titolo.endswith(" - RG 77/2026")
    # termine della controparte con ruolo certo
    controparte = _Bozza("c", "Costituzione del convenuto", "Decreto comunicato via PEC il 01/03/2026. a carico di: convenuto.", "LAV_416_COSTITUZIONE")
    assert esito_proposta(controparte, ruolo_cliente="ricorrente")[0] == ANNULLA
    assert esito_proposta(controparte)[0] == ""


def test_riconvalida_non_tocca_decisioni_dell_avvocato_ed_e_idempotente():
    confermata = _Bozza("d", COSTITUZIONE_SU_RINVIO.titolo, COSTITUZIONE_SU_RINVIO.descrizione, "LAV_416_COSTITUZIONE", stato="APERTO")
    titolo_avvocato = _Bozza("e", DEPOSITO_GENERICO.titolo, DEPOSITO_GENERICO.descrizione, "PROVV_DEPOSITO",
                             provenienza={CHIAVE_TITOLO_AVVOCATO: {"il": "2026-11-06"}})
    righe = [_Bozza(**vars(COSTITUZIONE_SU_RINVIO)), _Bozza(**vars(DEPOSITO_GENERICO)), confermata, titolo_avvocato]
    scadenziario = _Scadenziario(righe)
    esito = riconvalida_proposte_giudice(scadenziario)
    assert (esito["annullate"], esito["titoli"]) == (1, 1)
    assert scadenziario.righe["a"].stato == "ANNULLATO" and MARCATORE_RICONVALIDA in scadenziario.righe["a"].note
    assert scadenziario.righe["b"].titolo.startswith("Depositare le graduatorie")
    assert scadenziario.righe["d"].stato == "APERTO"
    assert scadenziario.righe["e"].titolo == DEPOSITO_GENERICO.titolo
    assert riconvalida_proposte_giudice(scadenziario)["titoli"] == 0


# ── G-11: decorrenze e pagamenti ──────────────────────────────────────────────────────


ISTANZA = ("PREMESSO che il decreto è stato notificato all'ingiunto in data 23/12/2024 a mezzo PEC; considerato che è scaduto "
           "il termine di quaranta giorni ex art. 641 comma 1 c.p.c. decorrente dal 10/02/2024 e che non è stata proposta opposizione")


def test_la_decorrenza_non_e_un_termine_ne_un_udienza():
    fatti = estrai_date(ISTANZA, origine="nativo")
    assert ("notifica", "2024-12-23") in [(f.campo, f.valore) for f in fatti]
    assert "2024-02-10" not in [f.valore for f in fatti]
    # riconvalida dei fatti già registrati sul brano salvato
    assert "decorre" in esclusione_data_salvata(ISTANZA, "2024-02-10")
    for testo in ("termine perentorio di venti giorni a decorrere dal 01/12/2026", "termine che decorre dal 03/03/2027"):
        assert [f for f in estrai_date(testo, origine="nativo") if f.campo in {"termine", "udienza"}] == []
    # una scadenza vera resta
    assert [(f.campo, f.valore) for f in estrai_date("deposito entro il 15/12/2026 a pena di decadenza", origine="nativo")] == [("termine", "2026-12-15")]


def test_avviso_pagopa_non_e_termine_processuale():
    avviso = "|Codice avviso|330007606087363218| |Data scadenza|09/01/2025| |Importo|49,00|"
    assert estrai_date(avviso, origine="nativo") == []
    assert "pagamento" in esclusione_data_salvata(avviso, "2025-01-09")


@dataclass
class _Fatto:
    campo: str
    valore: str
    valore_letto: str = ""
    contesto: str = ""
    categoria: str = "data"
    oggetto_id: str = "D1"
    verifica: str = "verificata"


def test_decorrenza_anteriore_all_atto_che_la_fa_decorrere():
    termine = _Fatto("termine", "2024-02-10", "10/02/2024", ISTANZA)
    notifica = _Fatto("notifica", "2024-12-23", "23/12/2024", ISTANZA)
    motivo = motivo_incoerenza(termine, [termine, notifica])
    assert "anteriore" in motivo and "23/12/2024" in motivo
    # decorrenza successiva alla notifica: coerente
    assert motivo_incoerenza(_Fatto("termine", "2025-01-10", "10/01/2025", ISTANZA.replace("10/02/2024", "10/01/2025")), [notifica]) == ""
    # nessuna formula di decorrenza: nessun giudizio
    assert motivo_incoerenza(_Fatto("termine", "2024-02-10", "10/02/2024", "entro il 10/02/2024"), [notifica]) == ""
    # notifica di un altro documento: nessun giudizio
    assert motivo_incoerenza(termine, [_Fatto("notifica", "2024-12-23", oggetto_id="ALTRO")]) == ""


# ── Lettura: il termine del giudice in bozza fra i prossimi passi ───────────────────────


def test_bozza_del_giudice_nei_prossimi_passi():
    from pct.fascicolo_lettura.prossimi_passi import _passi_scadenze

    scadenze = [
        {"stato": "BOZZA", "data": "2026-11-16", "titolo": "Depositare le graduatorie aggiornate (ricorrente) — termine del giudice",
         "note": "PEC_TERMINE_PROPOSTO:pec_x:PROVV_DEPOSITO\nTermine proposto"},
        {"stato": "BOZZA", "data": "2026-11-20", "titolo": "Proposta generica", "note": "PEC_TERMINE_PROPOSTO:pec_y:CIV_ALTRO"},
    ]
    passi = _passi_scadenze(scadenze, date(2026, 11, 10))
    assert [p.azione for p in passi] == ["Confermare e pianificare «Depositare le graduatorie aggiornate (ricorrente) — termine del giudice»"]
    assert passi[0].entro == "16/11/2026" and passi[0].urgenza == 1


# ── Controllo di sicurezza: testo non fidato e ruolo solo da notifica uscente dello studio ─────────


def test_relata_patologica_termina_in_tempo_breve():
    import time

    patologico = "RELATA DI NOTIFICA " + "Io sottoscritto avv. difensore di: Anna Rossi " * 20000 + "HO NOTIFICATO il ricorso"
    inizio = time.monotonic()
    ruolo_da_relata(patologico, "Anna Rossi")
    assert time.monotonic() - inizio < 1.0


def test_ruolo_dalla_relata_solo_se_la_notifica_esce_dallo_studio():
    from pct.provvedimenti.parte_assistita import notifica_uscente_dello_studio as uscente

    casella = "avv.verdi@pec.it"
    gestore = [{"email": "posta-certificata@legalmail.it"}]
    daticert_falso = '<postacert tipo="accettazione"><intestazione><mittente>avv.verdi@pec.it</mittente></intestazione></postacert>'
    # From falsificato su un messaggio in arrivo, From multiplo, corpo che imita una ricevuta: mai
    assert not uscente(casella=casella, cartella="INBOX", mittenti_busta=[{"email": "avv.verdi@pec.it"}])
    assert not uscente(casella=casella, cartella="INBOX", mittenti_busta=[{"email": "avv.verdi@pec.it"}, gestore[0]])
    # daticert annidato falso e smime.p7s falso (stato di firma di un controllo generico): mai
    assert not uscente(casella=casella, cartella="INBOX", mittenti_busta=gestore, daticert=[daticert_falso], firma_busta="valida")
    # messaggio vero nella cartella degli inviati della casella dello studio
    assert uscente(casella=casella, cartella="Posta inviata")
    assert uscente(casella=casella, cartella="INBOX.Sent")
    # casella sconosciuta o cartella mancante: non verificabile
    assert not uscente(casella="", cartella="Sent")
    assert not uscente(casella=casella, cartella="")


def test_ruolo_incerto_propone_il_termine_con_il_dubbio_dichiarato():
    oggi = date(2026, 6, 24)
    esito = esamina_provvedimento(DECRETO_415_NOTE, oggi=oggi, fascicolo_id="F1", rg="77/2026", materia="LAVORO")
    [costituzione] = [v for v in esito.voci if v.codice == "LAV_416_COSTITUZIONE"]
    assert costituzione.nota.startswith("Non è certo quale parte sia onerata") or "Non è certo quale parte sia onerata" in costituzione.nota
    assert ("LAV_416_COSTITUZIONE", "2026-09-25") in _codici(esito, oggi)
    certo = esamina_provvedimento(DECRETO_415_NOTE, oggi=oggi, fascicolo_id="F1", rg="77/2026", materia="LAVORO", ruolo_cliente="ricorrente")
    assert "LAV_416_COSTITUZIONE" not in [v.codice for v in certo.voci]
