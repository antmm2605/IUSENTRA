"""Commi non numerati dall'XML ufficiale Normattiva: rientro d'inizio comma, lettere, intestazione e note escluse."""

from __future__ import annotations

import zipfile

from pct.normattiva_commi_xml import commi_dell_articolo
from pct.normattiva_commi_xml import testo_comma_da_xml as comma_da_xml

_XML_RIENTRO_2 = (
    '<articolo id="6"><num>Art. 6.</num><comma id="art6-com1"><num>1</num><corpo>'
    '<h:p h:style="text-align: center;">Art. 6. </h:p><h:p h:style="text-align: center;">Effettuazione delle operazioni. </h:p><h:br/>'
    '<h:p h:style="padding-left:2px;">Le cessioni di beni si considerano effettuate nella stipulazione. </h:p>'
    '<h:p h:style="padding-left:2px;">In deroga al precedente comma l&apos;operazione si considera effettuata: </h:p>'
    '<h:p h:style="padding-left:4px;">a) per le cessioni periodiche, all&apos;atto del pagamento; </h:p>'
    '<h:p h:style="padding-left:2px;">Le prestazioni di servizi si considerano effettuate all&apos;atto del pagamento del corrispettivo. </h:p>'
    '<h:p>------------- </h:p><h:p>AGGIORNAMENTO (1) </h:p><h:p h:style="padding-left:2px;">Nota da non leggere. </h:p>'
    '</corpo></comma></articolo>'
)
_XML_RIENTRO_6 = (
    '<articolo id="15"><num>Art. 15.</num><comma id="art15-com1"><num>1</num><corpo>'
    '<h:p h:style="padding-left:32px;">Art. 15. </h:p><h:p h:style="padding-left:14px;">Esclusioni </h:p><h:br/>'
    '<h:p h:style="padding-left:6px;">Non concorrono a formare la base imponibile: </h:p>'
    '<h:p h:style="padding-left:8px;">3) le somme dovute a titolo di rimborso delle anticipazioni </h:p>'
    '<h:p h:style="padding-left:4px;">fatte in nome e per conto della controparte, purche&apos; documentate; </h:p>'
    '<h:p h:style="padding-left:6px;">Non si tiene conto delle penalita&apos;. </h:p>'
    '</corpo></comma></articolo>'
)


def test_commi_con_rientro_di_primo_livello_e_lettere_nel_comma():
    commi = commi_dell_articolo(_XML_RIENTRO_2, "6")
    assert len(commi) == 3
    assert commi[1].startswith("In deroga") and "a) per le cessioni periodiche" in commi[1]
    assert commi[2] == "Le prestazioni di servizi si considerano effettuate all'atto del pagamento del corrispettivo."


def test_il_rientro_d_inizio_comma_si_ricava_dall_atto():
    commi = commi_dell_articolo(_XML_RIENTRO_6, "15")
    assert len(commi) == 2
    assert "3) le somme dovute a titolo di rimborso delle anticipazioni fatte in nome e per conto" in commi[0]
    assert commi[1] == "Non si tiene conto delle penalita'."


def test_articolo_assente_o_comma_oltre_il_numero_non_inventano_testo(tmp_path):
    assert commi_dell_articolo(_XML_RIENTRO_2, "7") == []
    archivio = tmp_path / "DPR.zip"
    with zipfile.ZipFile(archivio, "w") as z:
        z.writestr("atto.xml", _XML_RIENTRO_2)
    assert comma_da_xml(str(archivio), "atto.xml", "6", "3").startswith("Le prestazioni di servizi")
    assert comma_da_xml(str(archivio), "atto.xml", "6", "9") == ""
    assert comma_da_xml(str(archivio), "assente.xml", "6", "1") == ""
    assert comma_da_xml(str(tmp_path / "nessuno.zip"), "atto.xml", "6", "1") == ""


def test_cartella_alternativa_per_gli_archivi(tmp_path):
    archivio = tmp_path / "DPR.zip"
    with zipfile.ZipFile(archivio, "w") as z:
        z.writestr("atto.xml", _XML_RIENTRO_2)
    assert comma_da_xml("/percorso/del/server/DPR.zip", "atto.xml", "6", "1", raw_dir=str(tmp_path)).startswith("Le cessioni")
