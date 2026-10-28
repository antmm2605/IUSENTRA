"""Un rifiuto della fonte non attiva retry di trasporto."""
import urllib.error
import pytest
from lex.normativa.biblioteca.normattiva_akn import _apri

@pytest.mark.parametrize("status", [400,403,404,429])
def test_errore_richiesta_o_accesso_non_viene_ritentato(status):
    class Fonte:
        chiamate=0
        def open(self,url,timeout):
            self.chiamate+=1
            raise urllib.error.HTTPError(url,status,"risposta primaria",{},None)
    fonte=Fonte()
    with pytest.raises(urllib.error.HTTPError):
        _apri(fonte,"https://www.normattiva.it/",1,pausa=0)
    assert fonte.chiamate==1


PAGINA=b'<a href="/do/atto/caricaAKN?dataGU=18620125&amp;codiceRedaz=061U0408">AKN</a>'

XML=b'''<akomaNtoso xmlns="http://docs.oasis-open.org/legaldocml/ns/akn/3.0"><act><meta>
<identification><FRBRWork><FRBRalias value="urn:nir:stato:regio.decreto:1861-12-29;408"/>
<FRBRalias name="eli" value="eli/id/1862/01/25/061U0408/CONSOLIDATED/18620125"/>
<FRBRdate date="1861-12-29"/></FRBRWork><FRBRExpression><FRBRdate date="1862-01-25"/>
</FRBRExpression></identification><publication date="1862-01-25"/></meta>
<preface><docDate date="1861-12-29"/><docNumber>408</docNumber></preface>
<body><article><num>Art. 1.</num><paragraph><content><p>Corpo.</p></content></paragraph></article></body>
</act></akomaNtoso>'''


def test_identita_gu_diretta_non_usa_risolutore_che_ignora_data_atto():
    from lex.normativa.biblioteca.normattiva_akn import scarica
    class Risposta:
        def __init__(self,data):self.data=data
        def read(self):return self.data
    class Fonte:
        chiamate=[]
        def open(self,url,timeout):
            self.chiamate.append(url)
            return Risposta(PAGINA if "caricaDettaglioAtto" in url else XML)
    fonte=Fonte()
    doc=scarica("urn:nir:stato:regio.decreto:1861-12-29;408","20261026",opener=fonte,
                identita_gu=("1862-01-25","061U0408"))
    assert len(fonte.chiamate)==2
    assert "caricaDettaglioAtto" in fonte.chiamate[0]
    assert all("uri-res/N2Ls" not in url for url in fonte.chiamate)
    assert "caricaAKN?dataGU=18620125&codiceRedaz=061U0408" in fonte.chiamate[1]
    assert doc.codice_redazionale=="061U0408"


def test_numero_408_bis_non_si_confonde_con_408():
    from lex.normativa.biblioteca.normattiva_akn import scarica
    class Risposta:
        def __init__(self,data):self.data=data
        def read(self):return self.data
    class Fonte:
        def open(self,url,timeout):
            return Risposta(PAGINA if "caricaDettaglioAtto" in url else XML.replace(b"<docNumber>408</docNumber>",b"<docNumber>408 bis</docNumber>"))
    with pytest.raises(ValueError,match="Numero nell.intestazione documentale"):
        scarica("urn:nir:stato:regio.decreto:1861-12-29;408","20261026",opener=Fonte(),
                identita_gu=("1862-01-25","061U0408"))


def test_gu_dettaglio_senza_link_coerente_non_scarica_altro_atto():
    from lex.normativa.biblioteca.normattiva_akn import scarica
    class Risposta:
        def read(self):return PAGINA.replace(b"061U0408",b"061U9202")
    class Fonte:
        def __init__(self):self.chiamate=[]
        def open(self,url,timeout):self.chiamate.append(url);return Risposta()
    fonte=Fonte()
    with pytest.raises(ValueError,match="GU esatta"):
        scarica("urn:nir:stato:regio.decreto:1861-12-29;408","20261026",opener=fonte,
                identita_gu=("1862-01-25","061U0408"))
    assert len(fonte.chiamate)==1


@pytest.mark.parametrize("numero,romano", [("99","XCIX"),("290","CCXC"),("507","DVII"),("177","CLXXVII"),("461","CCCCLXI"),("33","XXXIII")])
def test_numero_atto_romano_storico_equivale_solo_a_numero_esatto(numero,romano):
    from lex.normativa.biblioteca.normattiva_akn import scarica
    xml=XML.replace(b";408",(";"+numero).encode()).replace(b"<docNumber>408</docNumber>",("<docNumber>"+romano+"</docNumber>").encode())
    class Risposta:
        def __init__(self,data):self.data=data
        def read(self):return self.data
    class Fonte:
        def open(self,url,timeout):return Risposta(PAGINA if "caricaDettaglioAtto" in url else xml)
    doc=scarica("urn:nir:stato:regio.decreto:1861-12-29;"+numero,"20261026",opener=Fonte(),identita_gu=("1862-01-25","061U0408"))
    assert doc.xml==xml


@pytest.mark.parametrize("anno,ammesso", [("1862",True),("1999",False)])
def test_annotazione_raccolta_deve_corrispondere_all_anno_della_fonte(anno,ammesso):
    from lex.normativa.biblioteca.normattiva_akn import scarica
    xml=XML.replace(b"<docNumber>408</docNumber>",("<docNumber>408 (Raccolta "+anno+")</docNumber>").encode())
    class Risposta:
        def __init__(self,data):self.data=data
        def read(self):return self.data
    class Fonte:
        def open(self,url,timeout):return Risposta(PAGINA if "caricaDettaglioAtto" in url else xml)
    if ammesso:
        assert scarica("urn:nir:stato:regio.decreto:1861-12-29;408","20261026",opener=Fonte(),identita_gu=("1862-01-25","061U0408")).xml==xml
    else:
        with pytest.raises(ValueError,match="Numero nell.intestazione documentale"):
            scarica("urn:nir:stato:regio.decreto:1861-12-29;408","20261026",opener=Fonte(),identita_gu=("1862-01-25","061U0408"))


def test_eli_di_altra_pubblicazione_non_viene_accettato_anche_con_urn_identico():
    from lex.normativa.biblioteca.normattiva_akn import scarica
    class Response:
        def __init__(self,raw):self.raw=raw
        def read(self):return self.raw
    class Source:
        def open(self,url,timeout):return Response(PAGINA if "caricaDettaglioAtto" in url else XML.replace(b"/061U0408/",b"/061U0409/"))
    with pytest.raises(ValueError,match="ELI"):
        scarica("urn:nir:stato:regio.decreto:1861-12-29;408","20261026",opener=Source(),identita_gu=("1862-01-25","061U0408"))
