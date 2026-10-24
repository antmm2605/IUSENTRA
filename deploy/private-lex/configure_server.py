"""Read private configuration from SSH stdin; probe before updating the app environment."""
import datetime
import ipaddress
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.request import Request, urlopen


def main():
    data = json.load(sys.stdin)
    address = ipaddress.ip_address(data["pc_address"])
    if address not in ipaddress.ip_network("100.64.0.0/10"):
        raise ValueError("Private address required")
    key = data["api_key"]
    if len(key) < 32 or any(c in key for c in "\r\n'\"$"):
        raise ValueError("Invalid private key format")
    state = json.loads(subprocess.check_output(["tailscale", "status", "--json"]))
    if state.get("BackendState") != "Running":
        raise RuntimeError("Server is not enrolled")
    request = Request(f"http://{address}:8091/v1/models", headers={"Authorization":"Bearer " + key})
    with urlopen(request, timeout=15) as response:
        models = json.load(response).get("data", [])
    if len(models) != 1 or not models[0].get("id"):
        raise RuntimeError("Expected one verified local model")
    model = models[0]["id"]
    if any(c in model for c in "\r\n'\"$"):
        raise ValueError("Unexpected model identifier")
    path = Path("/opt/iusentra/.env.hetzner")
    original = path.read_text()
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = path.with_name(path.name + ".before-private-lex-" + stamp)
    shutil.copy2(path, backup)
    os.chmod(backup, 0o600)
    values = {"LLAMACPP_ENABLED":"1", "LLAMACPP_BASE_URL":f"http://{address}:8091/v1", "LLAMACPP_API_KEY":key,
              "LLAMACPP_DEFAULT_MODEL":model, "LLAMACPP_TIMEOUT_SECONDS":"600", "LEX_STESURA_PROVIDER":"llamacpp"}
    lines = [line for line in original.splitlines() if line.split("=",1)[0].strip() not in values]
    lines.extend(name + "='" + value + "'" for name, value in values.items())
    temporary = path.with_name(path.name + ".private-lex-tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    os.fchmod(descriptor, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write("\n".join(lines) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
    print("Private model verified; environment updated atomically; application restart remains gated by deployment CI.")


if __name__ == "__main__":
    main()
