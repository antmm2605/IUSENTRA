import pytest

from pct.sentenzeweb_bridge import validate_params


@pytest.mark.parametrize("query", ["kind:(snciv OR snpen)", "id:snciv2026226870O", "id:snpen2026137151S"])
def test_only_bounded_public_queries(query):
    params = {"q": query, "rows": "1", "wt": "json"}
    assert validate_params(params) == params


@pytest.mark.parametrize(
    "extra",
    [
        {"q": "http://127.0.0.1/secrets"},
        {"url": "https://another-host.invalid"},
        {"rows": "101"},
        {"rows": "-1"},
        {"wt": "xml"},
        {"cursorMark": "../secrets"},
        {"fq": "*:*"},
        {"fl": "private"},
        {"sort": "arbitrary"},
    ],
)
def test_cannot_turn_public_source_transport_into_arbitrary_proxy(extra):
    with pytest.raises(ValueError):
        validate_params({"q": "kind:(snciv OR snpen)", "rows": "10", "wt": "json", **extra})
