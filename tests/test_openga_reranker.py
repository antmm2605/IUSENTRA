from pct.openga_reranker import estratti_strutturali


def test_estratto_e_una_sottostringa_senza_inventare_contenuto():
    text='ANNULLAMENTO DEL PROVVEDIMENTO AVENTE AD OGGETTO "CONFERMA DI UN CONTENUTO ORIGINALE COMPLETO"'
    spans=estratti_strutturali(text)
    assert len(spans)==1
    begin,end=spans[0]
    assert text[begin:end]=='CONFERMA DI UN CONTENUTO ORIGINALE COMPLETO"'
    assert text.startswith('ANNULLAMENTO')


def test_codice_in_intestazione_e_preservato_nel_testo_originale():
    text='ANNULLAMENTO DECRETO 123/CAT. A.2, DI RIGETTO DELLA RICHIESTA DI UN PROVVEDIMENTO'
    spans=estratti_strutturali(text)
    assert text[spans[0][0]:spans[0][1]].startswith('RIGETTO')
    assert '123/CAT.' in text
    assert estratti_strutturali('SILENZIO SULLA RICHIESTA DI UN DOCUMENTO')==[]


def test_diversita_non_cancella_e_non_privilegia_un_anno():
    from pct.openga_reranker import diversifica_descrizioni
    def row(i,year,text="identico oggetto"):
        return {"id":i,"oggetto":text,"organo_giudicante":"Ufficio","tipo_provvedimento":"sentenza","anno_sentenza":year}
    rows=[row(1,2001),row(2,2001),row(3,2002),row(4,2001,"altro oggetto")]
    assert [r["id"] for r in diversifica_descrizioni("cerca un oggetto",rows)]==[1,3,4,2]
    assert [r["id"] for r in diversifica_descrizioni("cerca nel 2001",rows)]==[1,2,3,4]
    assert [r["id"] for r in diversifica_descrizioni("cerca un oggetto",rows,2)]==[1,2,3,4]
    assert [r["id"] for r in rows]==[1,2,3,4]


def test_model_manifest_errato_fallisce_prima_di_caricare_torch(tmp_path):
    import json,pytest
    from pct.openga_reranker import RerankerOpenGALocale,MODEL_REVISION
    (tmp_path/"iusentra-model-manifest.json").write_text(json.dumps({"repo":"BAAI/bge-reranker-v2-m3","revision":MODEL_REVISION,"files":[{"file":"model.safetensors","sha256":"0"*64}]}))
    (tmp_path/"model.safetensors").write_bytes(b"fake")
    with pytest.raises(ValueError,match="Impronta"):
        RerankerOpenGALocale(tmp_path)


def test_documenti_privati_non_raggiungono_il_modello():
    import pytest
    from pct.openga_reranker import RerankerOpenGALocale
    uninitialized=object.__new__(RerankerOpenGALocale)
    with pytest.raises(ValueError,match="solo metadati OpenGA"):
        uninitialized("domanda",[{"evidence_scope":"private_fascicolo"}])
