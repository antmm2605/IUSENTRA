"""Migrazione React della stanza cliente dell'assistenza remota (/support/join/<token>).

Verifica che la pagina servita di default sia la radice React con il bootstrap
del solo cliente, che la vista classica resti raggiungibile con ``?_legacy=1``,
che le intestazioni di sicurezza (Permissions-Policy per schermo e microfono,
CSP con nonce) valgano per entrambe e che i sorgenti React coprano i
comportamenti dello script legacy ``web/static/js/support_customer_room.js``.
"""

from __future__ import annotations

import json
import re
import urllib.parse
from datetime import datetime
from pathlib import Path

import pytest

from tests.test_support_remote import _seed_runtime

REPO = Path(__file__).resolve().parents[1]
FRONTEND_SRC = REPO / "frontend" / "src"
CUSTOMER_COMPONENT = FRONTEND_SRC / "components" / "SupportCustomerRoom.tsx"
CUSTOMER_MODULES = FRONTEND_SRC / "components" / "supportCustomer"


def _login_superadmin(client, superadmin) -> None:
    with client.session_transaction() as session_tx:
        session_tx["user_id"] = superadmin.id
        session_tx["auth_scope"] = "global"
        session_tx["auth_tenant_slug"] = ""
        session_tx["last_activity"] = datetime.now().isoformat()


def _create_session(client, superadmin, customer_name: str = "Cliente React") -> dict:
    _login_superadmin(client, superadmin)
    response = client.post("/support/api/session", json={"customer_name": customer_name})
    assert response.status_code == 200
    payload = response.get_json()
    # Il cliente apre il link senza essere autenticato nello studio.
    with client.session_transaction() as session_tx:
        session_tx.clear()
    return payload


def _json_script(html: str, script_id: str) -> dict:
    match = re.search(rf'<script id="{script_id}" type="application/json">(.*?)</script>', html, re.S)
    assert match, f"blocco JSON {script_id} mancante"
    return json.loads(match.group(1))


def _csp_header(response) -> str:
    # In test la CSP può essere in sola segnalazione (CSP_REPORT_ONLY): stesso contenuto.
    return response.headers.get("Content-Security-Policy") or response.headers.get("Content-Security-Policy-Report-Only", "")


def _csp_nonce(response) -> str:
    csp = _csp_header(response)
    match = re.search(r"'nonce-([^']+)'", csp)
    assert match, f"CSP senza nonce: {csp}"
    return match.group(1)


def _customer_sources() -> str:
    files = [CUSTOMER_COMPONENT, *sorted(CUSTOMER_MODULES.glob("*.ts")), *sorted(CUSTOMER_MODULES.glob("*.tsx"))]
    return "\n".join(path.read_text(encoding="utf-8") for path in files)


def test_stanza_cliente_react_servita_con_bootstrap_del_solo_cliente(tmp_path: Path):
    app, superadmin, _, _ = _seed_runtime(tmp_path)
    with app.test_client() as client:
        payload = _create_session(client, superadmin)
        session = payload["session"]
        response = client.get(f"/support/join/{session['client_token']}")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'id="support-customer-react-root" data-support-customer-room="1"' in html
    assert "window.SUPPORT_BOOTSTRAP" in html
    assert "/static/js/support_customer_room.js" not in html
    assert 'id="startBtn"' not in html
    # Il modulo React parte solo se caricato con il parametro di versione (main.tsx).
    assert re.search(r'<script type="module" src="/static/react/assets/[^"]+\?v=[^"]+"></script>', html)
    assert response.headers.get("Cache-Control") == "no-store"

    bootstrap = _json_script(html, "support-customer-bootstrap")
    assert bootstrap["role"] == "client"
    assert bootstrap["publicId"] == session["public_id"]
    assert bootstrap["authToken"] == session["client_token"]
    assert bootstrap["apiPrefix"] == f"/support/api/{session['public_id']}"
    assert bootstrap["wsBase"] == "/support/ws"
    assert bootstrap["closed"] is False
    assert not any("operator" in key.lower() for key in bootstrap)
    assert "customerJoinUrl" not in bootstrap

    operator_token = urllib.parse.parse_qs(urllib.parse.urlparse(payload["operator_url"]).query)["token"][0]
    assert operator_token
    assert operator_token not in html
    assert "/support/operatore/" not in html

    sessione = _json_script(html, "support-customer-session")
    assert set(sessione) == {
        "public_id",
        "status",
        "status_label",
        "customer_name",
        "practice_label",
        "advanced_control_requested",
        "advanced_control_approved",
        "presence",
    }
    assert sessione["status"] == "waiting_operator"
    assert sessione["presence"] == {"client": False, "operator": False}


def test_stanza_cliente_vista_classica_con_legacy(tmp_path: Path):
    app, superadmin, _, _ = _seed_runtime(tmp_path)
    with app.test_client() as client:
        payload = _create_session(client, superadmin)
        response = client.get(f"/support/join/{payload['session']['client_token']}?_legacy=1")

    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "support-customer-react-root" not in html
    assert 'id="startBtn" type="button" disabled' in html
    assert "js/support_customer_room.js" in html
    assert 'id="support-customer-bootstrap" type="application/json"' in html


def test_stanza_cliente_sessione_chiusa_e_link_non_valido(tmp_path: Path):
    app, superadmin, _, _ = _seed_runtime(tmp_path)
    with app.test_client() as client:
        payload = _create_session(client, superadmin, "Cliente chiuso React")
        public_id = payload["session"]["public_id"]
        client_token = payload["session"]["client_token"]
        close = client.post(
            f"/support/api/{public_id}/close?role=client",
            json={},
            headers={"X-Support-Token": client_token},
        )
        closed_page = client.get(f"/support/join/{client_token}")
        invalid = client.get("/support/join/token-inesistente")

    assert close.status_code == 200
    html = closed_page.get_data(as_text=True)
    assert closed_page.status_code == 200
    bootstrap = _json_script(html, "support-customer-bootstrap")
    assert bootstrap["closed"] is True
    assert bootstrap["status"] == "closed"
    assert "Sessione conclusa" in html
    assert invalid.status_code == 404


def test_stanza_cliente_api_accetta_token_in_intestazione(tmp_path: Path):
    """La stanza React manda il token in X-Support-Token, non nella query."""
    app, superadmin, _, _ = _seed_runtime(tmp_path)
    with app.test_client() as client:
        payload = _create_session(client, superadmin)
        public_id = payload["session"]["public_id"]
        token = payload["session"]["client_token"]
        headers = {"X-Support-Token": token}
        state = client.get(f"/support/api/{public_id}/state?role=client&events=0", headers=headers)
        webrtc = client.get(f"/support/api/{public_id}/webrtc-config?role=client", headers=headers)
        consent = client.post(
            f"/support/api/{public_id}/consent?role=client",
            json={"consent_screen": True, "consent_audio": False, "consent_chat": True},
            headers=headers,
        )
        wrong = client.get(f"/support/api/{public_id}/state?role=client", headers={"X-Support-Token": "sbagliato"})

    assert state.status_code == 200
    assert "events" not in state.get_json()
    assert webrtc.status_code == 200
    assert webrtc.get_json()["rtcConfiguration"]["iceServers"]
    assert consent.status_code == 200
    assert consent.get_json()["session"]["consent_screen"] is True
    assert wrong.status_code == 401


@pytest.mark.parametrize("legacy", [False, True])
def test_stanza_cliente_intestazioni_sicurezza(tmp_path: Path, legacy: bool):
    app, superadmin, _, _ = _seed_runtime(tmp_path)
    with app.test_client() as client:
        payload = _create_session(client, superadmin)
        suffix = "?_legacy=1" if legacy else ""
        response = client.get(f"/support/join/{payload['session']['client_token']}{suffix}")

    html = response.get_data(as_text=True)
    policy = response.headers.get("Permissions-Policy", "")
    assert "display-capture=(self)" in policy
    assert "microphone=(self)" in policy
    assert "camera=(self)" in policy
    assert "loopback-network=(self)" in policy

    csp = _csp_header(response)
    script_src = next(part for part in csp.split(";") if part.strip().startswith("script-src"))
    assert "'unsafe-inline'" not in script_src
    nonce = _csp_nonce(response)
    # Ogni script in linea eseguibile porta il nonce della richiesta.
    inline_scripts = re.findall(r"<script(?![^>]*\bsrc=)(?![^>]*application/json)([^>]*)>", html, re.I)
    assert inline_scripts
    for attributes in inline_scripts:
        assert f'nonce="{nonce}"' in attributes
    assert " on" + "click=" not in html


def test_rotta_cliente_precarica_il_proprio_chunk():
    from web.blueprints import react_shell

    assert react_shell._route_component_key("/support/join/AbC123") == "src/components/SupportCustomerRoom.tsx"
    assert react_shell._route_component_key("/support/operatore/xyz") != "src/components/SupportCustomerRoom.tsx"


def test_entry_react_monta_la_stanza_cliente_in_modo_pigro():
    main = (FRONTEND_SRC / "main.tsx").read_text(encoding="utf-8")
    entry = (FRONTEND_SRC / "reactEntry.tsx").read_text(encoding="utf-8")
    template = (REPO / "web" / "templates" / "support" / "customer_room_react.html").read_text(encoding="utf-8")

    assert "document.getElementById('support-customer-react-root')" in main
    assert "supportCustomerRoot?.dataset.supportCustomerRoom === '1'" in main
    assert "shouldMountSupportCustomer" in main
    assert "await import('./components/SupportCustomerRoom')" in entry
    assert "import SupportCustomerRoom from" not in entry
    assert '<script nonce="{{ csp_nonce() }}">' in template
    assert 'src="{{ js_file }}?v={{ app_version }}"' in template
    assert 'data-support-customer-room="1"' in template


def test_sorgenti_react_coprono_i_comportamenti_legacy():
    sources = _customer_sources()
    # Condivisione schermo: browser prima, agente locale come riserva.
    for snippet in (
        "getDisplayMedia",
        "getUserMedia({ audio: true, video: false })",
        "frameRate: { ideal: 15, max: 30 }",
        "Per continuare devi autorizzare la condivisione schermo.",
        "Condivisione schermo dal browser annullata: provo l'agente locale se installato.",
        "Hai interrotto la condivisione dello schermo.",
        "Microfono non autorizzato o non disponibile sul PC: assistenza avviata senza audio.",
        "Microfono non disponibile: assistenza avviata senza audio.",
        "Microfono cliente disattivato all'avvio",
        "Microfono cliente disattivato",
        # Agente locale / Local Signer
        "http://127.0.0.1:27273",
        "http://127.0.0.1:27272/support",
        "targetAddressSpace: 'loopback'",
        "iusentra-local-signer://update",
        "Local Signer pronto per il controllo PC",
        "Verifico Local Signer o agente IUSENTRA Assistenza sul PC",
        "'/screenshot'",
        "'/arm'",
        "'/disarm'",
        "'/execute'",
        "screen_frame",
        "remote_control_ack",
        "La sola visualizzazione dello schermo funziona già dal browser.",
        # Canale realtime, WebRTC, stato e token
        "Canale realtime chiuso prima della connessione.",
        "WS_PING_INTERVAL_MS = 20000",
        "WS_RECONNECT_BASE_DELAY_MS = 800",
        "WS_RECONNECT_MAX_DELAY_MS = 6000",
        "STATE_POLL_DELAY_MS = 12000",
        "'X-Support-Token'",
        "'/webrtc-config'",
        "'/consent'",
        "'/start'",
        "'/close'",
        "'/escalation'",
        "Candidato ICE scartato dopo descrizione remota.",
        "visibilitychange",
        "fullscreenchange",
        "beforeunload",
        # Testi del template legacy
        "Assistenza remota con consenso esplicito",
        "Richiesta visualizzata dal SUPERADMIN",
        "Autorizzo la condivisione dello schermo",
        "Autorizzo il microfono",
        "Autorizzo la chat tecnica",
        "Richiesta controllo remoto del PC",
        "Local Signer aggiornato o l&apos;agente IUSENTRA Assistenza",
        "Sessione conclusa",
    ):
        assert snippet in sources, snippet
    # Stessi id del legacy: li usa l'audit reale nel browser (local_real_workflow_audit.py).
    for element_id in (
        "statusBadge",
        "peerBadge",
        "takeChargeNotice",
        "consentScreen",
        "consentAudio",
        "consentChat",
        "startBtn",
        "customerMuteMicBtn",
        "stopBtn",
        "remoteAudio",
        "chatLog",
        "chatInput",
        "sendBtn",
        "advancedBanner",
        "approveAdvancedBtn",
        "rejectAdvancedBtn",
        "customerFullscreenBtn",
        "compactChatBtn",
        "supportCustomerShell",
        "customerScreenPanel",
        "customerChatPanel",
    ):
        assert f'"{element_id}"' in sources or f"'{element_id}'" in sources, element_id


def test_sorgenti_react_rispettano_la_governance():
    tsx_files = [CUSTOMER_COMPONENT, *sorted(CUSTOMER_MODULES.glob("*.tsx"))]
    for path in tsx_files:
        source = path.read_text(encoding="utf-8")
        assert not re.search(r"style\s*=\s*\{\{", source), f"stile inline in {path.name}"
        assert 'method="post"' not in source.lower(), f"form POST in {path.name}"
        assert "dangerouslySetInnerHTML" not in source, path.name
    governance = json.loads((REPO / "scripts" / "react-migration" / "design-system-governance.json").read_text(encoding="utf-8"))
    css_path = "frontend/src/components/SupportCustomerRoom.css"
    assert css_path in governance["approvedCssFiles"]
    assert css_path in governance["approvedCssRationale"]
    assert "import './SupportCustomerRoom.css'" in CUSTOMER_COMPONENT.read_text(encoding="utf-8")


def test_bundle_committato_contiene_la_stanza_cliente():
    """Il bundle in web/static/react è la fonte del rilascio: va ricompilato con i sorgenti."""
    assets = REPO / "web" / "static" / "react" / "assets"
    bundle = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in assets.glob("index-*.js"))
    assert "support-customer-react-root" in bundle
    manifest = json.loads((REPO / "web" / "static" / "react" / ".vite" / "manifest.json").read_text(encoding="utf-8"))
    assert "src/components/SupportCustomerRoom.tsx" in manifest
