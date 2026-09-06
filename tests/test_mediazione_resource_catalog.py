from pct.mediazione_resource_catalog import resource_catalog

HOME = "https://organismo.example.test/"


def resource(name, source=HOME):
    return dict(url=HOME + name, label=name, kind="istanza", source_url=source, source_sha256="a" * 64)


def test_fresh_page_replaces_removed_links_without_erasing_other_pages():
    row = dict(website=HOME, directory_check=dict(resources=[resource("vecchia.pdf"), resource("procura.pdf", HOME + "delega")], checked_at="2026-09-05T12:00:00+00:00"))
    monitor = dict(fonti=[dict(url=HOME, status=200, parsed=True, sha256="a" * 64)], risorse_osservate=[resource("nuova.pdf")])
    current, _ = resource_catalog(row, monitor)
    assert {r["url"] for r in current} == {HOME + "nuova.pdf", HOME + "procura.pdf"}


def test_error_or_unparsed_page_preserves_old_modules():
    row = dict(website=HOME, directory_check=dict(resources=[resource("vecchia.pdf")]))
    for page in [dict(status=503), dict(status=200)]:
        current, _ = resource_catalog(row, dict(fonti=[dict(page, url=HOME, sha256="a" * 64)]))
        assert len(current) == 1 and current[0]["label"] == "vecchia.pdf"


def test_changed_ownership_or_wrong_digest_cannot_promote_a_module():
    monitor = dict(fonti=[dict(url=HOME, status=200, parsed=True, sha256="b" * 64)], risorse_osservate=[resource("nuova.pdf")])
    assert resource_catalog(dict(website=HOME), monitor)[0] == []
    assert resource_catalog(dict(website="https://altro.example.test/", directory_check=dict(resources=[resource("vecchia.pdf")])), {})[0] == []


def test_latest_error_uses_preserved_successful_inventory():
    current, _ = resource_catalog(dict(website=HOME), dict(risorse_precedenti=[resource("modulo.pdf")], fonti=[]))
    assert current[0]["url"] == HOME + "modulo.pdf"


def test_failed_refresh_does_not_resurrect_links_removed_by_successful_inventory():
    row = dict(website=HOME, directory_check=dict(resources=[
        resource("ritirato.pdf"), resource("procura.pdf", HOME + "delega")]))
    for links in [[], [resource("nuovo.pdf")]]:
        monitoring = dict(fonti=[], risorse_precedenti=links, fonti_precedenti=[
            dict(url=HOME, status=200, parsed=True, sha256="a" * 64)])
        current, _ = resource_catalog(row, monitoring)
        assert {r["url"] for r in current} == {HOME + "procura.pdf"} | {r["url"] for r in links}
