"""Regolamenti UE nell'archivio di Lex dal testo della GUUE (2.436.11).

``lex/normativa/ue_regolamenti.py`` divide in articoli l'XHTML dell'Ufficio delle pubblicazioni (formato GUUE ``oj-``,
GUUE vecchio ``ti-art``, consolidato CONVEX, HTML semplice), ``tools/ue_regolamenti_scarica.py`` produce le righe di
``lex/normativa/integrazioni/leggi_essenziali.jsonl``; sigle e alias («Reg. UE 1215/2012», «Bruxelles I bis», «Roma I»)
sono in ``lex/ricerca_giuridica/testo.py``. Nessun accesso alla rete: XHTML finti.
"""

from __future__ import annotations

import json
import os
import sqlite3

import pytest

from lex.normativa.integrazione_leggi import FILE_PREDEFINITO, _numero_e_tipo, integra, leggi_jsonl
from lex.normativa.ue_regolamenti import (
    REGOLAMENTI,
    REGOLAMENTI_PER_CELEX,
    controlla,
    dividi,
    mancanti,
    prepara,
    righe_jsonl,
    sostituisci_nel_jsonl,
)
from lex.retrieval.normativa import etichetta_fonte_normattiva
from lex.ricerca_giuridica.ibrida import cerca_normattiva_indicizzata
from lex.ricerca_giuridica.testo import CODICI_PER_CHIAVE, analizza_domanda, codice_da_atto

os.environ.setdefault("LEX_RICERCA_SEMANTICA", "0")

# --- formato GUUE «oj-» (ELI): considerando, articoli in div#art_N, elenchi in tabelle a due colonne, nota, allegato ---
OJ = """<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE html PUBLIC "-//W3C//DTD XHTML//EN" "xhtml-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml"><head><title>L_2008177IT.01000601.xml</title></head><body>
<table><tr><td><p class="oj-hd-date">4.7.2008</p></td><td><p class="oj-hd-oj">L 177/6</p></td></tr></table>
<div class="eli-container"><div class="eli-main-title" id="tit_1">
<p class="oj-doc-ti" id="d1">REGOLAMENTO (CE) N. 593/2008 DEL PARLAMENTO EUROPEO E DEL CONSIGLIO</p>
<p class="oj-doc-ti">del 17 giugno 2008</p>
<p class="oj-doc-ti">sulla legge applicabile alle obbligazioni contrattuali (Roma I)</p></div>
<div class="eli-subdivision" id="pbl_1"><p class="oj-normal">IL PARLAMENTO EUROPEO E IL CONSIGLIO DELL'UNIONE EUROPEA,</p>
<div class="eli-subdivision" id="rct_1"><table><tr><td><p class="oj-normal">(1)</p></td>
<td><p class="oj-normal">Articolo 99 considerando che non deve diventare un articolo.</p></td></tr></table></div>
<p class="oj-normal">HANNO ADOTTATO IL PRESENTE REGOLAMENTO:</p></div>
<div id="enc_1"><div class="eli-subdivision" id="cpt_I"><p class="oj-ti-section-1">CAPO I</p>
<div class="eli-title"><p class="oj-ti-section-2">AMBITO DI APPLICAZIONE</p></div>
<div class="eli-subdivision" id="art_1"><p class="oj-ti-art">Articolo 1</p>
<div class="eli-title"><p class="oj-sti-art">Campo d’applicazione materiale</p></div>
<div id="001.001"><p class="oj-normal">1.   Il presente regolamento si applica alle obbligazioni contrattuali in materia civile e commerciale
(<span class="oj-super oj-note-tag">1</span>).</p></div>
<div id="001.002"><p class="oj-normal">2.   Sono esclusi dal campo d’applicazione:</p>
<table><col width="4%"/><col width="96%"/><tbody><tr><td valign="top"><p class="oj-normal">a)</p></td>
<td valign="top"><p class="oj-normal">le questioni di stato e di capacità delle persone fisiche;</p></td></tr></tbody></table>
<table><tbody><tr><td valign="top"><p class="oj-normal">b)</p></td>
<td valign="top"><p class="oj-normal">le obbligazioni derivanti dai rapporti di famiglia.</p></td></tr></tbody></table></div></div>
</div><div class="eli-subdivision" id="cpt_II"><p class="oj-ti-section-1">CAPO II</p>
<div class="eli-title"><p class="oj-ti-section-2">NORME UNIFORMI</p></div>
<div class="eli-subdivision" id="art_2"><p class="oj-ti-art">Articolo 2</p>
<div class="eli-title"><p class="oj-sti-art">Libertà di scelta</p></div>
<p class="oj-normal">Il contratto è disciplinato dalla legge scelta dalle parti ai sensi dell’articolo 1.</p></div></div>
<p class="oj-normal">Il presente regolamento è obbligatorio in tutti i suoi elementi e direttamente applicabile negli Stati membri.</p>
<p class="oj-normal">Fatto a Strasburgo, addì 17 giugno 2008.</p>
<div class="oj-signatory"><p class="oj-signatory">Per il Parlamento europeo</p></div></div>
<p class="oj-note">(<a>1</a>)  GU C 318 del 23.12.2006, pag. 56.</p>
<p class="oj-doc-sep"></p><div class="eli-container"><p class="oj-ti-annex">ALLEGATO</p>
<p class="oj-ti-art">Articolo 3</p><p class="oj-normal">Testo dell'allegato da non importare.</p></div>
</body></html>"""

# --- GUUE «vecchio» (ti-art / sti-art, paragrafi fino al ti-art successivo) ---
VECCHIO = """<html><body>
<p class="doc-ti">REGOLAMENTO (CE) N. 864/2007 DEL PARLAMENTO EUROPEO E DEL CONSIGLIO</p>
<p class="doc-ti">dell'11 luglio 2007</p>
<p class="doc-ti">sulla legge applicabile alle obbligazioni extracontrattuali («Roma II»)</p>
<p class="normal">considerando quanto segue:</p><p class="normal">(1) La Comunità si è prefissa l'obiettivo...</p>
<p class="ti-section-1">CAPO I</p>
<p class="ti-art">Articolo 1</p><p class="sti-art">Ambito d'applicazione</p>
<p class="normal">1.   Il presente regolamento si applica alle obbligazioni extracontrattuali in materia civile e commerciale.</p>
<p class="normal">2.   Sono esclusi:</p>
<table><tr><td><p class="normal">a)</p></td><td><p class="normal">le obbligazioni extracontrattuali che derivano da rapporti di famiglia;</p></td></tr></table>
<p class="ti-art">Articolo 2</p><p class="sti-art">Obbligazioni extracontrattuali</p>
<p class="normal">Ai fini del presente regolamento, il danno include qualsiasi conseguenza derivante da fatto illecito.</p>
<p class="final">Il presente regolamento è obbligatorio in tutti i suoi elementi.</p>
</body></html>"""

# --- consolidato CONVEX: marcatori ►M1 ◄ ▼B, articolo «bis», elenchi in div rientrati, rimandi a note, allegato ---
CONSOLIDATO = """<?xml version="1.0" encoding="UTF-8"?><html xmlns="http://www.w3.org/1999/xhtml"><body>
<p class="disclaimer">Trattandosi di un semplice strumento di documentazione</p>
<table><tr><td><p class="arrow"><a title="32012R1215">►B</a></p></td>
<td><p class="title-doc-first">REGOLAMENTO (UE) N. 1215/2012 DEL PARLAMENTO EUROPEO E DEL CONSIGLIO</p>
<p class="title-doc-first">del 12 dicembre 2012</p>
<p class="title-doc-first">concernente la competenza giurisdizionale in materia civile e commerciale</p>
<p class="title-doc-last">(rifusione)</p><p class="title-doc-oj-reference">(GU L 351 del 20.12.2012, pag. 1)</p></td></tr></table>
<p class="hd-modifiers">Modificato da:</p><p class="title-fam-member-star">Regolamento (UE) n. 542/2014 Articolo 9</p>
<p class="arrow"><a class="modref">▼B</a></p>
<p class="title-doc-first">REGOLAMENTO (UE) N. 1215/2012 DEL PARLAMENTO EUROPEO E DEL CONSIGLIO</p>
<p class="title-doc-first">del 12 dicembre 2012</p>
<p class="normal">considerando quanto segue:</p>
<p class="title-division-1">CAPO II</p><p class="title-division-2">COMPETENZA</p>
<p class="title-article-norm">Articolo 7</p>
<p class="norm">Una persona domiciliata in uno Stato membro può essere convenuta in un altro Stato membro:</p>
<div style="margin-left: 24pt">1)<span> </span>
  <div style="margin-left: 24pt"><p class="norm">a)<span> </span>in materia contrattuale, davanti all’autorità del luogo di esecuzione;</p></div>
  <div style="margin-left: 24pt"><p class="norm">b)<span> </span>il luogo di esecuzione è:</p>
     <div><p class="norm">—<span> </span>nel caso della compravendita di beni, il luogo di consegna,</p></div></div></div>
<div style="margin-left: 24pt"><p class="norm">2)<span> </span>in materia di illeciti civili, davanti al giudice del luogo dell’evento <a href="#E0001" id="src.E0001"><span class="superscript">1</span></a>;</p></div>
<p class="arrow"><a class="modref" title="32014R0542">▼M1</a></p>
<p class="title-article-norm">Articolo 7 <span class="norm">bis</span></p>
<p class="norm">1.  Ai fini del presente regolamento, ►M1 un’autorità giurisdizionale comune ◄ è un’autorità di uno Stato membro.</p>
<p class="norm">2.  Quando è fatto riferimento al presente articolo si applica il paragrafo 1.</p>
<p class="arrow"><a class="modref">▼B</a></p>
<p class="title-article-norm">Articolo 8</p>
<p class="norm">Una persona domiciliata in uno Stato membro può inoltre essere convenuta davanti al giudice del convenuto.</p>
<p class="norm">Il presente regolamento è obbligatorio in tutti i suoi elementi e direttamente applicabile.</p>
<p class="separator-annex"></p><p class="title-annex-1">ALLEGATO I</p><p class="norm">Modulo da non importare</p>
<p class="footnote">(1)  GU L 1 del 1.1.2000.</p>
</body></html>"""

# --- consolidato recente: div#art_N, rubrica stitle, grid-container, paragrafo con numero separato ---
GRIGLIA = """<html><body>
<p class="title-doc-first">REGOLAMENTO (UE) 2015/848 DEL PARLAMENTO EUROPEO E DEL CONSIGLIO</p>
<p class="title-doc-first">del 20 maggio 2015</p><p class="title-doc-first">relativo alle procedure di insolvenza</p>
<div class="eli-subdivision" id="art_1"><p class="title-article-norm">Articolo 1</p>
<div class="eli-title"><p class="stitle-article-norm">Ambito di applicazione</p></div>
<div class="norm"><span class="no-parag">1.  </span><div class="norm inline-element"><p class="norm inline-element">Il presente regolamento si applica alle procedure concorsuali pubbliche,</p>
<div class="grid-container grid-list"><div class="list grid-list-column-1"><span>a) </span></div>
<div class="grid-list-column-2"><p class="norm">in cui il debitore è spossessato;</p></div></div></div></div></div>
<div class="eli-subdivision" id="art_2"><p class="title-article-norm">Articolo2</p>
<div class="eli-title"><p class="stitle-article-norm">Definizioni</p></div>
<p class="norm">Ai fini del presente regolamento, s'intende per «debitore» la persona sottoposta alla procedura.</p></div>
<div class="eli-subdivision" id="art_4"><p class="title-article-norm">Articolo 4</p>
<div class="eli-title"><p class="stitle-article-norm">Entrata in vigore</p></div>
<p class="norm">Il presente regolamento entra in vigore il ventesimo giorno successivo alla pubblicazione.</p></div>
</body></html>"""

# --- HTML semplice degli atti anteriori a maggio 2004 (charset dichiarato in modo non standard) ---
HTML_SEMPLICE = """<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"><html lang="IT"><head>
<meta name="DC.type" http-equiv="Content-Type" content="text/html; charset=UNICODE-1-1-UTF-8"></head><body>
<p><strong>Regolamento (CE) n. 261/2004 del Parlamento europeo e del Consiglio, dell'11 febbraio 2004, che istituisce regole comuni
in materia di compensazione ed assistenza ai passeggeri</strong></p><div id="TexteOnly"><p><TXT_TE>
<p>Regolamento (CE) n. 261/2004 del Parlamento europeo e del Consiglio</p><p>dell'11 febbraio 2004</p>
<p>considerando quanto segue:</p><p>(1) L'intervento della Comunità ... cfr. Articolo 7 del trattato.</p>
<p>HANNO ADOTTATO IL PRESENTE REGOLAMENTO:</p>
<p>Articolo 1</p><p>Oggetto</p><p>1. Il presente regolamento riconosce ai passeggeri diritti minimi.</p>
<p>Articolo 2</p><p>Definizioni</p><p>Ai fini del presente regolamento si intende per:</p><p>a) "vettore aereo": un'impresa di trasporto aereo;</p>
<p>Articolo 3</p><p>Compensazione pecuniaria</p><p>1. Quando è fatto riferimento al presente articolo, i passeggeri ricevono 600 EUR.</p>
<p>Il presente regolamento è obbligatorio in tutti i suoi elementi.</p><p>Fatto a Bruxelles, addì 11 febbraio 2004.</p>
<p>ALLEGATO</p><p>Articolo 9</p><p>da non importare</p>
</TXT_TE></p></div></body></html>"""


def _articoli(atto):
    return {a.numero: a for a in atto.articoli}


def test_formato_oj_titolo_data_rubriche_elenchi_senza_considerando_note_e_allegati():
    atto = dividi(OJ.encode("utf-8"))
    assert atto.formato == "oj" and atto.sigla == "Reg. CE 593/2008" and atto.data_atto == "2008-06-17"
    assert atto.titolo == ("Regolamento (CE) n. 593/2008 del Parlamento europeo e del Consiglio, del 17 giugno 2008, "
                           "sulla legge applicabile alle obbligazioni contrattuali (Roma I)")
    art = _articoli(atto)
    assert list(art) == ["1", "2"] and controlla(atto) == []
    assert art["1"].rubrica == "Campo d'applicazione materiale"
    assert art["1"].testo == ("Art. 1. (Campo d'applicazione materiale). 1. Il presente regolamento si applica alle obbligazioni "
                              "contrattuali in materia civile e commerciale. 2. Sono esclusi dal campo d'applicazione: "
                              "a) le questioni di stato e di capacità delle persone fisiche; "
                              "b) le obbligazioni derivanti dai rapporti di famiglia.")
    # il capo II non finisce nel testo dell'articolo 1, la formula finale e l'allegato non entrano nell'articolo 2
    assert "CAPO" not in art["1"].testo and "NORME UNIFORMI" not in art["1"].testo
    assert art["2"].testo.endswith("ai sensi dell'articolo 1.") and "allegato" not in art["2"].testo.lower()
    assert "99" not in art and "3" not in art


def test_formato_vecchio_ti_art():
    atto = dividi(VECCHIO)
    assert atto.formato == "vecchio" and atto.data_atto == "2007-07-11" and atto.sigla == "Reg. CE 864/2007"
    assert "dell'11 luglio 2007" in atto.titolo and "(«Roma II»)" in atto.titolo
    art = _articoli(atto)
    assert [a.rubrica for a in atto.articoli] == ["Ambito d'applicazione", "Obbligazioni extracontrattuali"]
    assert art["1"].corpo.endswith("2. Sono esclusi: a) le obbligazioni extracontrattuali che derivano da rapporti di famiglia;")
    assert art["2"].corpo == "Ai fini del presente regolamento, il danno include qualsiasi conseguenza derivante da fatto illecito."


def test_formato_consolidato_marcatori_bis_elenchi_annidati_e_note():
    atto = dividi(CONSOLIDATO.encode("utf-8"))
    assert atto.formato == "consolidato" and atto.sigla == "Reg. UE 1215/2012" and atto.data_atto == "2012-12-12"
    assert atto.titolo.endswith("concernente la competenza giurisdizionale in materia civile e commerciale (rifusione)")
    art = _articoli(atto)
    assert list(art) == ["7", "7bis", "8"]
    assert art["7"].corpo == ("Una persona domiciliata in uno Stato membro può essere convenuta in un altro Stato membro: "
                              "1) a) in materia contrattuale, davanti all'autorità del luogo di esecuzione; "
                              "b) il luogo di esecuzione è: — nel caso della compravendita di beni, il luogo di consegna, "
                              "2) in materia di illeciti civili, davanti al giudice del luogo dell'evento;")
    assert art["7bis"].testo.startswith("Art. 7-bis. 1. Ai fini del presente regolamento, un'autorità giurisdizionale comune è")
    assert "Quando è fatto riferimento" in art["7bis"].corpo  # la «Q» dopo un marcatore non si perde
    assert not any(c in a.testo for a in atto.articoli for c in "►▼◄")
    assert art["8"].corpo.endswith("davanti al giudice del convenuto.") and "Modulo" not in art["8"].corpo
    # gli articoli 1-6 non ci sono nel documento finto: la numerazione lo segnala
    assert mancanti(atto) == [1, 2, 3, 4, 5, 6]
    assert any("mancanti" in e for e in controlla(atto))
    assert controlla(atto, soppressi_ammessi=range(1, 7)) == []


def test_formato_consolidato_a_griglia_e_articolo_senza_spazio():
    atto = dividi(GRIGLIA)
    assert atto.sigla == "Reg. UE 2015/848" and atto.titolo.startswith("Regolamento (UE) 2015/848 del Parlamento")
    art = _articoli(atto)
    assert art["1"].testo == ("Art. 1. (Ambito di applicazione). 1. Il presente regolamento si applica alle procedure concorsuali "
                              "pubbliche, a) in cui il debitore è spossessato;")
    assert art["2"].rubrica == "Definizioni"
    assert controlla(atto) == ["articoli mancanti: [3] (ultimo: Articolo 4)"]


def test_html_semplice_con_charset_non_standard():
    atto = dividi(HTML_SEMPLICE.encode("utf-8"))
    assert atto.formato == "html" and atto.sigla == "Reg. CE 261/2004" and atto.data_atto == "2004-02-11"
    art = _articoli(atto)
    assert list(art) == ["1", "2", "3"] and controlla(atto) == []
    assert art["3"].testo == ("Art. 3. (Compensazione pecuniaria). 1. Quando è fatto riferimento al presente articolo, "
                              "i passeggeri ricevono 600 EUR.")
    assert art["2"].corpo == "Ai fini del presente regolamento si intende per: a) \"vettore aereo\": un'impresa di trasporto aereo;"


def test_controlli_articolo_vuoto_e_intestazione_dentro_un_altro_articolo():
    atto = dividi(GRIGLIA)
    atto.articoli[1].righe = []
    atto.articoli[2].righe.append("Articolo 5")
    errori = controlla(atto)
    assert "articolo 2 vuoto" in errori
    assert any("contiene l'intestazione «Articolo 5»" in e for e in errori)


def test_righe_jsonl_nel_formato_del_gdpr_e_integrazione_con_riferimento_esatto(tmp_path):
    atto = dividi(CONSOLIDATO.encode("utf-8"))
    righe = righe_jsonl(atto, chiave="reg_ue_2012_1215", url="https://publications.europa.eu/resource/celex/02012R1215-20150226",
                        consolidato_al="2015-02-26", raccolto_il="2026-10-05")
    prima = righe[0]
    assert set(prima) == {"atto", "chiave", "articolo", "rubrica", "testo", "titolo_atto", "data_atto", "urn", "fonte_testo",
                          "url", "raccolto_il"}
    assert prima["atto"] == "Reg. UE 1215/2012" and prima["urn"] == "urn:nir:unione.europea:regolamento:2012-12-12;1215"
    assert prima["fonte_testo"] == "publications.europa.eu (GUUE)"
    assert prima["titolo_atto"].endswith("[Testo consolidato al 26/02/2015, Ufficio delle pubblicazioni UE]")
    originale = righe_jsonl(atto, chiave="reg_ue_2012_1215", url="u")[0]["titolo_atto"]
    assert originale.endswith("[Testo originale pubblicato in GUUE: modifiche successive non incluse]")
    assert _numero_e_tipo(prima["urn"]) == ("1215", "Regolamento (UE)")

    file = tmp_path / "leggi.jsonl"
    file.write_text(json.dumps({"chiave": "legge_1_2000", "atto": "l. 1/2000"}) + "\n", encoding="utf-8")
    assert sostituisci_nel_jsonl(file, righe) == (0, 3)
    assert sostituisci_nel_jsonl(file, righe) == (3, 3)  # rilancio: sostituisce, non duplica
    assert [json.loads(r)["chiave"] for r in file.read_text(encoding="utf-8").splitlines()][:2] == ["legge_1_2000", "reg_ue_2012_1215"]

    solo_ue = tmp_path / "ue.jsonl"
    solo_ue.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in righe), encoding="utf-8")
    db = tmp_path / "normattiva.sqlite"
    esito = integra(db, jsonl=solo_ue)
    assert esito.atti_inseriti == 1 and esito.articoli_inseriti == 3
    conn = sqlite3.connect(str(db))
    info = conn.execute("SELECT codice, articolo FROM normative_fts_info ORDER BY articolo").fetchall()
    conn.close()
    assert info == [("reg_ue_2012_1215", "7"), ("reg_ue_2012_1215", "7bis"), ("reg_ue_2012_1215", "8")]
    trovati = cerca_normattiva_indicizzata("art. 7-bis Reg. UE 1215/2012", db, limite=2)
    assert trovati and trovati[0]["riferimento_esatto"] and trovati[0]["metadata"]["article_number"] == "Art. 7-bis."
    trovati = cerca_normattiva_indicizzata("art. 8 Bruxelles I bis", db, limite=2)
    assert trovati and trovati[0]["metadata"]["article_number"] == "Art. 8." and trovati[0]["riferimento_esatto"]


@pytest.mark.parametrize("domanda,chiave", [
    ("art. 7 Reg. UE 1215/2012", "reg_ue_2012_1215"),
    ("art. 7 del regolamento (UE) n. 1215/2012", "reg_ue_2012_1215"),
    ("art. 25 Bruxelles I-bis proroga di competenza", "reg_ue_2012_1215"),
    ("art. 4 Roma I vendita", "reg_ue_2008_593"),
    ("art. 4 Roma II", "reg_ue_2007_864"),
    ("art. 8 Roma III", "reg_ue_2010_1259"),
    ("Bruxelles II-ter art. 7 responsabilità genitoriale", "reg_ue_2019_1111"),
    ("art. 7 regolamento passeggeri compensazione", "reg_ue_2004_261"),
    ("art. 7 Reg. CE 261/2004", "reg_ue_2004_261"),
    ("art. 3 Reg. UE 2015/848 centro degli interessi principali", "reg_ue_2015_848"),
    ("art. 3 regolamento 848/2015", "reg_ue_2015_848"),
    ("art. 25 eIDAS firma elettronica", "reg_ue_2014_910"),
    ("art. 5 AI Act pratiche vietate", "reg_ue_2024_1689"),
    ("art. 12 del decreto ingiuntivo europeo", "reg_ue_2006_1896"),
    ("art. 6 regolamento UE 2016/679", "gdpr"),
])
def test_riconoscimento_sigle_e_alias(domanda, chiave):
    analisi = analizza_domanda(domanda)
    assert analisi.codice == chiave and analisi.articoli and analisi.riferimento_esatto


def test_alias_ambigui_non_scattano():
    # «Roma i» con la minuscola e «regolamento ai sensi» non sono regolamenti UE
    assert analizza_domanda("il tribunale di Roma i giudici hanno deciso sul danno art. 2043 c.c.").codice == "codice_civile"
    assert analizza_domanda("il regolamento ai sensi dell'art. 3").codice == ""
    # le parole del contenuto restano termini di ricerca anche se fanno parte di un alias del regolamento
    termini = analizza_domanda("art. 4 Roma I legge applicabile al contratto di vendita").termini
    assert "vend" in termini and "contratt" in termini


def test_etichette_delle_fonti_e_codici():
    assert codice_da_atto("1215", "2012-12-12") == "reg_ue_2012_1215"
    assert codice_da_atto("848", "2015-05-20") == "reg_ue_2015_848"
    assert etichetta_fonte_normattiva({"titolo": "Regolamento (UE) n. 1215/2012 ...", "data": "2012-12-12",
                                       "metadata": {"numero": "1215"}}) == "Reg. UE 1215/2012 (Bruxelles I-bis)"
    assert etichetta_fonte_normattiva({"titolo": "Regolamento (UE) 2015/848 ...", "data": "2015-05-20",
                                       "metadata": {"numero": "848"}}) == "Reg. UE 2015/848 (insolvenza)"
    # regolamento non in catalogo: dalla URN, con l'ordine anno/numero dal 2015
    etichetta = etichetta_fonte_normattiva({"titolo": "Regolamento (UE) 2017/1001 sul marchio dell'Unione europea",
                                            "data": "2017-06-14", "url_origine": "urn:nir:unione.europea:regolamento:2017-06-14;1001",
                                            "metadata": {"numero": "1001"}})
    assert etichetta.startswith("Reg. UE 2017/1001, ")
    for reg in REGOLAMENTI:
        assert reg.chiave in CODICI_PER_CHIAVE, reg.chiave


def test_prepara_offline_consolidato_con_articoli_soppressi_e_ripiego_sull_originale(tmp_path):
    reg = REGOLAMENTI_PER_CELEX["32012R1215"]
    # originale con gli articoli 1-8, consolidato senza 1-6 (soppressi): accettato con nota
    originale = CONSOLIDATO.replace('<p class="title-article-norm">Articolo 7</p>',
                                    "".join(f'<p class="title-article-norm">Articolo {n}</p><p class="norm">Testo {n}.</p>'
                                            for n in range(1, 7)) + '<p class="title-article-norm">Articolo 7</p>')
    (tmp_path / "32012R1215.xhtml").write_text(originale, encoding="utf-8")
    (tmp_path / "02012R1215-20150226.xhtml").write_text(CONSOLIDATO, encoding="utf-8")
    esito = prepara(reg, tmp_path, offline=True, oggi="2026-10-05")
    assert esito.valido and esito.celex_usato == "02012R1215-20150226" and esito.consolidato_al == "2015-02-26"
    assert esito.soppressi == [1, 2, 3, 4, 5, 6]
    # consolidato futuro rispetto alla data limite: resta l'originale
    esito = prepara(reg, tmp_path, offline=True, oggi="2014-01-01")
    assert esito.valido and esito.celex_usato == "32012R1215" and esito.consolidato_al == ""
    # solo originale richiesto
    assert prepara(reg, tmp_path, offline=True, consolidato=False).celex_usato == "32012R1215"


def test_strumento_offline_scrive_copie_e_aggiorna_il_jsonl(tmp_path, capsys):
    from tools.ue_regolamenti_scarica import main

    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "32008R0593.xhtml").write_text(OJ, encoding="utf-8")
    jsonl = tmp_path / "leggi.jsonl"
    jsonl.write_text("", encoding="utf-8")
    codice = main(["--cache", str(cache), "--solo", "32008R0593", "--offline", "--aggiorna", "--jsonl", str(jsonl),
                   "--copie", str(tmp_path / "copie")])
    assert codice == 0
    uscita = capsys.readouterr().out
    assert "Reg. CE 593/2008" in uscita and "originale GUUE" in uscita
    righe = [json.loads(r) for r in jsonl.read_text(encoding="utf-8").splitlines()]
    assert [r["articolo"] for r in righe] == ["1", "2"] and righe[0]["url"].endswith("/celex/32008R0593")
    assert (tmp_path / "copie" / "reg_ue_2008_593.jsonl").read_text(encoding="utf-8").count("\n") == 2


ATTESI = {  # chiave -> articoli nel file del repository (consolidato o originale, vedi CHANGELOG 2.436.11)
    "reg_ue_2012_1215": 85, "reg_ue_2007_861": 32, "reg_ue_2006_1896": 33, "reg_ue_2004_805": 33, "reg_ue_2014_655": 54,
    "reg_ue_2008_593": 29, "reg_ue_2007_864": 32, "reg_ue_2019_1111": 105, "reg_ue_2010_1259": 21, "reg_ue_2012_650": 84,
    "reg_ue_2020_1784": 38, "reg_ue_2020_1783": 35, "reg_ue_2004_261": 19, "reg_ue_2015_848": 92, "reg_ue_2014_910": 81,
    "reg_ue_2024_1689": 119,
}


def test_file_del_repository_contiene_i_regolamenti_ue():
    gruppi = leggi_jsonl(FILE_PREDEFINITO)
    for chiave, attesi in ATTESI.items():
        righe = gruppi[chiave]
        assert len(righe) == attesi, chiave
        assert {r["fonte_testo"] for r in righe} == {"publications.europa.eu (GUUE)"}
        assert all(r["url"].startswith("https://publications.europa.eu/resource/celex/") for r in righe)
        assert all(r["urn"].startswith("urn:nir:unione.europea:regolamento:") for r in righe)
        assert all(r["testo"].startswith("Art. ") and len(r["testo"]) > 60 for r in righe), chiave
        assert "[Testo" in righe[0]["titolo_atto"]
    art7 = {r["articolo"]: r["testo"] for r in gruppi["reg_ue_2012_1215"]}["7"]
    assert "in materia contrattuale, davanti all'autorità giurisdizionale del luogo di esecuzione" in art7
    roma2 = gruppi["reg_ue_2007_864"][0]["titolo_atto"]
    assert roma2.endswith("[Testo originale pubblicato in GUUE: modifiche successive non incluse]")


def _intestazione(riga: dict) -> str:
    from lex.providers.prompt_budget import format_evidence_item
    from lex.retrieval.normativa import _archive_row_to_source
    from lex.retrieval.sources import row_to_evidence

    fonte = _archive_row_to_source(riga, source_type="normativa_normattiva", default_title="Normattiva")
    evidenza = row_to_evidence(fonte.to_dict() if hasattr(fonte, "to_dict") else fonte.__dict__, "normativa")
    return format_evidence_item(1, evidenza, max_chars=1600)[0].splitlines()[0]


def _riga(urn: str, titolo: str, data: str, numero: str, articolo: str) -> dict:
    return {"chunk_id": "c1", "document_id": 1, "fonte": "Normattiva", "titolo": titolo, "data": data, "url_origine": urn,
            "articolo_o_chunk": f"Art. {articolo}.", "testo": f"Art. {articolo}. Testo.", "vigenza": "VIGENTE",
            "metadata": {"numero": numero, "data_atto": data, "article_number": f"Art. {articolo}.", "urn": urn}}


def test_provenienza_guue_e_cnf_nell_intestazione_della_fonte():
    from lex.ricerca_giuridica.testo import provenienza_atto

    assert provenienza_atto("urn:nir:unione.europea:regolamento:2012-12-12;1215") == "GUUE"
    assert provenienza_atto("urn:nir:consiglio.nazionale.forense:codice.deontologico:2014-01-31") == "CNF"
    assert provenienza_atto("urn:nir:stato:legge:1994-01-21;53") == "Normattiva"
    assert provenienza_atto("") == "Normattiva"
    assert _intestazione(_riga("urn:nir:unione.europea:regolamento:2012-12-12;1215", "Regolamento (UE) n. 1215/2012",
                               "2012-12-12", "1215", "7")) == "[1] Reg. UE 1215/2012 (Bruxelles I-bis) (GUUE) · art. 7 · vigente · 12/12/2012"
    assert _intestazione(_riga("urn:nir:unione.europea:regolamento:2016-04-27;679", "Regolamento (UE) 2016/679",
                               "2016-04-27", "679", "6")).startswith("[1] Regolamento (UE) 2016/679 (GDPR) (GUUE) · art. 6 · vigente")
    assert _intestazione(_riga("urn:nir:consiglio.nazionale.forense:codice.deontologico:2014-01-31", "Codice deontologico forense",
                               "2014-01-31", "", "1")).startswith("[1] Codice deontologico forense (CNF) · art. 1 · vigente")
    # gli atti Normattiva restano come prima
    assert _intestazione(_riga("urn:nir:stato:regio.decreto:1942-03-16;262", "Approvazione del testo del Codice civile.",
                               "1942-03-16", "262", "2043")) == "[1] Codice civile (Normattiva) · art. 2043 · vigente · 16/03/1942"


def test_ricerca_nell_archivio_porta_la_provenienza_guue(tmp_path):
    atto = dividi(CONSOLIDATO.encode("utf-8"))
    righe = righe_jsonl(atto, chiave="reg_ue_2012_1215", url="u", consolidato_al="2015-02-26")
    file = tmp_path / "ue.jsonl"
    file.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in righe), encoding="utf-8")
    db = tmp_path / "normattiva.sqlite"
    integra(db, jsonl=file)
    trovati = cerca_normattiva_indicizzata("art. 8 Reg. UE 1215/2012", db, limite=1)
    assert trovati and trovati[0]["fonte"] == "GUUE" and trovati[0]["vigenza"] == "VIGENTE"
