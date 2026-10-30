"""Peer-restricted transport of public SentenzeWeb responses over Tailscale.

This exposes no files and accepts no arbitrary upstream address or free-form
query. The official TLS connection is verified on the authorized PC.
"""

import argparse
import hashlib
import hmac
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from urllib.parse import parse_qs, urlsplit

import requests

from pct.sentenzeweb_nightly import tls_bundle

OFFICIAL_URL = "https://www.italgiure.giustizia.it/sncass/isapi/hc.dll/sn.solr/sn-collection/select"


def validate_params(params):
    if set(params) - {"q", "rows", "wt", "sort", "cursorMark", "fq", "fl"}:
        raise ValueError("Unsupported parameter")
    if params.get("q") != "kind:(snciv OR snpen)" and not re.fullmatch(
        r"id:sn(?:civ|pen)[A-Za-z0-9]{1,50}", params.get("q", "")
    ):
        raise ValueError("Unsupported public query")
    if not params.get("rows", "").isdigit() or not 1 <= int(params["rows"]) <= 100 or params.get("wt") != "json":
        raise ValueError("Invalid response bounds")
    if "sort" in params and params["sort"] not in {"id asc", "_version_ desc"}:
        raise ValueError("Unsupported ordering")
    if "fl" in params and params["fl"] not in {"*", "_version_"}:
        raise ValueError("Unsupported fields")
    if "cursorMark" in params and not re.fullmatch(r"[A-Za-z0-9+/=*]{1,512}", params["cursorMark"]):
        raise ValueError("Invalid cursor")
    if "fq" in params and not re.fullmatch(r"_version_:\{[0-9]{1,20} TO [0-9]{1,20}\]", params["fq"]):
        raise ValueError("Invalid incremental bounds")
    return params


def handler_type(token, peers, bundle):
    upstream_lock = Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            return

        def do_GET(self):
            address = urlsplit(self.path)
            authorization = self.headers.get("Authorization", "")
            if self.client_address[0] not in peers or not hmac.compare_digest(authorization, "Bearer " + token):
                self.send_error(404)
                return
            try:
                if address.path != "/sentenzeweb":
                    raise ValueError("Unknown endpoint")
                parsed = parse_qs(address.query, strict_parsing=True)
                if any(len(values) != 1 for values in parsed.values()):
                    raise ValueError("Ambiguous parameters")
                params = validate_params({key: values[0] for key, values in parsed.items()})
            except ValueError:
                self.send_error(400)
                return
            try:
                with (
                    upstream_lock,
                    requests.get(
                        OFFICIAL_URL,
                        params=params,
                        verify=str(bundle),
                        timeout=(10, 35),
                        allow_redirects=False,
                        stream=True,
                    ) as response,
                ):
                    if response.status_code != 200:
                        self.send_error(502)
                        return
                    body = bytearray()
                    for part in response.iter_content(65536):
                        body.extend(part)
                        if len(body) > 32 * 1024**2:
                            raise ValueError("Public response exceeds bound")
                    json.loads(body)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-IUSENTRA-Source-Transport", "official-tls-verified")
                self.send_header("X-IUSENTRA-Body-SHA256", hashlib.sha256(body).hexdigest())
                self.end_headers()
                self.wfile.write(body)
            except (requests.RequestException, ValueError):
                self.send_error(502)

    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-config", required=True)
    args = parser.parse_args()
    config = json.loads(Path(args.private_config).read_text())
    address = str(config["bind"])
    if not re.fullmatch(r"100\.(?:6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\.[0-9]{1,3}\.[0-9]{1,3}", address):
        raise ValueError("Only the configured Tailscale interface may be bound")
    directory = Path(config["state_directory"])
    bundle = tls_bundle(directory)
    server = ThreadingHTTPServer(
        (address, int(config["port"])), handler_type(config["token"], set(config["peers"]), bundle)
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
