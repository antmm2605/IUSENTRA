"""Update published module links page-by-page, retaining unvisited evidence.

Publication is not approval to file. Only a successfully parsed page with the
same content digest may replace that page's previous links; an HTTP failure or
an unreviewed new domain must not erase or promote resources.
"""
from urllib.parse import urlsplit

from pct.mediazione_public_sources import public_url


def resource_catalog(row, monitoring):
    def host(url):
        try:
            return urlsplit(public_url(url)).hostname.removeprefix("www.")
        except ValueError:
            return ""

    owner = host(row.get("website", ""))
    previous = row.get("directory_check") or {}
    resources = {r["url"]: dict(r, observed_at=previous.get("checked_at", ""))
                 for r in previous.get("resources", [])
                 if owner and host(r.get("source_url", "")) == owner}
    # The successful inventory is independent of the latest attempt. A network
    # error leaves it usable as historical evidence, not as a fresh check.
    successful_pages = {p["url"] for p in monitoring.get("fonti_precedenti", [])
                        if p.get("status") == 200 and p.get("parsed") and p.get("sha256")
                        and host(p["url"]) == owner}
    # A later failed attempt must not resurrect a link already removed by a
    # successful inventory, including an inventory containing no resources.
    resources = {url: r for url, r in resources.items()
                 if r.get("source_url") not in successful_pages}
    for r in monitoring.get("risorse_precedenti", []):
        if owner and host(r.get("source_url", "")) == owner:
            resources[r["url"]] = dict(r, observed_at=monitoring.get("ultima_acquisizione", ""))
    pages = {p["url"]: p for p in monitoring.get("fonti", [])
             if p.get("status") == 200 and p.get("parsed") and p.get("sha256") and host(p["url"]) == owner}
    # Replace only the scope actually reread, including pages that now publish
    # zero links. Other pages remain explicitly historical.
    resources = {url: r for url, r in resources.items() if r.get("source_url") not in pages}
    for r in monitoring.get("risorse_osservate", []):
        page = pages.get(r.get("source_url"))
        if page and r.get("source_sha256") == page["sha256"]:
            resources[r["url"]] = dict(r, observed_at=page.get("read_at", monitoring.get("ultimo_controllo", "")))
    observed = max((r.get("observed_at", "") for r in resources.values()), default="")
    return list(resources.values()), observed
