"""Installazione Tailscale senza cambiare DNS, route, SSH o applicazione."""
import json
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path


def main():
    if not shutil.which("tailscale"):
        release = dict(line.split("=", 1) for line in Path("/etc/os-release").read_text().splitlines() if "=" in line)
        distro = release.get("ID", "").strip('"')
        codename = release.get("VERSION_CODENAME", "").strip('"')
        if distro not in {"ubuntu", "debian"} or not re.fullmatch("[a-z]+", codename):
            raise RuntimeError("Distribuzione non prevista: nessuna modifica effettuata")
        key = Path("/usr/share/keyrings/tailscale-archive-keyring.gpg")
        source = Path("/etc/apt/sources.list.d/tailscale.list")
        origin = f"https://pkgs.tailscale.com/stable/{distro}/{codename}"
        key.write_bytes(urllib.request.urlopen(origin+".noarmor.gpg", timeout=30).read())
        source.write_bytes(urllib.request.urlopen(origin+".tailscale-keyring.list", timeout=30).read())
        with Path("/var/log/iusentra-tailscale-install.log").open("a") as log:
            for command in (["apt-get", "update", "-o", "Dir::Etc::sourcelist="+str(source), "-o", "Dir::Etc::sourceparts=-"],
                            ["apt-get", "install", "-y", "--no-install-recommends", "tailscale"],
                            ["systemctl", "enable", "--now", "tailscaled"]):
                subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
    state = json.loads(subprocess.check_output(["tailscale", "status", "--json"]))
    if state.get("BackendState") == "Running":
        print(json.dumps({"state":"Running", "addresses":state.get("Self", {}).get("TailscaleIPs", [])}))
        return
    if "--status" in sys.argv:
        print("NEEDS_LOGIN")
        return
    result = subprocess.run(["tailscale", "up", "--accept-dns=false", "--accept-routes=false", "--shields-up=true",
                             "--hostname=iusentra-hetzner-lex", "--timeout=10s"], capture_output=True, text=True, timeout=25, check=False)
    matches = re.findall(r"https://login\.tailscale\.com/a/[A-Za-z0-9]+", result.stdout+result.stderr)
    if not matches:
        raise RuntimeError("Collegamento di autorizzazione non disponibile; applicazione invariata")
    # stdout deve essere cifrato dal chiamante, mai scritto nei log Actions.
    print(matches[0])


if __name__ == "__main__":
    main()
