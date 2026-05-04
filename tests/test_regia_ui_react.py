from pathlib import Path


def test_ui_react_espone_regia_operativa_e_payload_reale():
    source = Path("frontend/src/components/FascicoliPage.tsx").read_text(encoding="utf-8")
    data = Path("frontend/src/fascicoliData.ts").read_text(encoding="utf-8")
    assert "RegiaOperativaSection" in source
    assert "Regia Operativa" in source
    assert "deposito non disponibile" in source.lower()
    assert "Deposito non disponibile" in source
    assert "Timeline ricevute" in source
    assert "Evidence pack" in source
    assert "mock_fallback: false" in data
    assert "regia: normalizeRegia(payload.regia)" in data
    assert "href={item.href || '#'}" not in source


def test_ui_mostra_dati_regia_senza_placeholder_operativi():
    source = Path("frontend/src/components/FascicoliPage.tsx").read_text(encoding="utf-8")
    regia = source[source.index("function RegiaOperativaSection"):source.index("function fLabel")]
    assert "Rossi" not in regia
    assert "Bianchi" not in regia
    assert "Cliente demo" not in regia
    assert "Dati fittizi" not in regia
    assert "ACQUISITO" in regia
