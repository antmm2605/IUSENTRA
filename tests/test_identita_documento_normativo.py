from lex.normativa.identita_documento import urn_documento


def test_identity_requires_type_number_full_date_in_source_metadata():
    entry="LEGGE_20170522_81/fonte.xml"
    assert urn_documento("urn:",entry,"81","2017-05-22")=="urn:nir:stato:legge:2017-05-22;81"
    assert not urn_documento("urn:",entry,"82","2017-05-22")
    assert not urn_documento("urn:",entry,"81","2017-05-23")
    assert not urn_documento("urn:","NON_NOTO_20170522_81/f.xml","81","2017-05-22")


def test_original_complete_identity_preserved():
    urn="urn:nir:stato:legge:2017-05-22;81"
    assert urn_documento(urn,"allegato.xml","81","2017-05-22")==urn
