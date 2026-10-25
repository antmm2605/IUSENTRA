"""Provision dedicated PC-only SSH deployment access; no existing keys removed."""
from pathlib import Path
import base64
import datetime
import json
import os
import pwd
import re
import shutil
import subprocess
import sys

USER = "claude-iusentra"
PEER = "100.69.184.43"
REPO = Path("/opt/iusentra/repo")

def run(*args):
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode:
        detail = result.stderr[-2000:]
        if args[:2] == ("systemctl", "restart"):
            detail += subprocess.run(["journalctl", "-u", "iusentra-claude-ssh-firewall", "-n", "20", "--no-pager", "-o", "cat"], capture_output=True, text=True).stdout
        raise RuntimeError(str(args[:2]) + ": " + detail)
    return result

def main():
    public = sys.stdin.read().strip()
    if not re.fullmatch(r"ssh-ed25519 [A-Za-z0-9+/]+={0,2} claude-iusentra-pcantonio-20261025", public):
        raise ValueError("Unexpected public key or identity")
    base64.b64decode(public.split()[1], validate=True)
    assert os.geteuid() == 0 and REPO.is_dir()
    backup = Path("/opt/iusentra/backups/ssh-claude-20261025")
    backup.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        account = pwd.getpwnam(USER)
        if account.pw_dir != "/home/" + USER or account.pw_shell != "/bin/bash":
            raise ValueError("Existing account has unexpected identity")
    except KeyError:
        run("useradd", "--create-home", "--shell", "/bin/bash", "--user-group", USER)
        account = pwd.getpwnam(USER)
    if not shutil.which("setfacl"):
        run("apt-get", "update")
        run("apt-get", "install", "-y", "--no-install-recommends", "acl")
    if not (backup / "repo-acl-before.txt").exists():
        (backup / "repo-acl-before.txt").write_text(run("getfacl", "-R", "-p", str(REPO)).stdout)
    run("setfacl", "-R", "-m", "u:" + USER + ":rwX", str(REPO))
    run("setfacl", "-R", "-d", "-m", "u:" + USER + ":rwX", str(REPO))
    run("setfacl", "-m", "u:" + USER + ":--x", "/opt/iusentra")
    home = Path(account.pw_dir)
    ssh = home / ".ssh"
    ssh.mkdir(mode=0o700, exist_ok=True)
    os.chown(ssh, account.pw_uid, account.pw_gid)
    auth = ssh / "authorized_keys"
    existing = auth.read_text() if auth.exists() else ""
    entry = 'from="' + PEER + '",no-agent-forwarding,no-port-forwarding,no-X11-forwarding ' + public
    if public.split()[1] not in existing:
        with auth.open("a") as stream:
            stream.write(("\n" if existing and not existing.endswith("\n") else "") + entry + "\n")
    auth.chmod(0o600)
    os.chown(auth, account.pw_uid, account.pw_gid)
    wrapper = Path("/usr/local/sbin/iusentra-claude-deploy")
    body = '#!/bin/sh\nset -eu\ntest "$#" -eq 0\ncd /opt/iusentra/repo\nexec /usr/bin/env -i HOME=/root PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin BRANCH=main /bin/bash deploy/hetzner/deploy.sh\n'
    if wrapper.exists() and wrapper.read_text() != body:
        raise ValueError("Deployment wrapper exists with different content")
    wrapper.write_text(body);wrapper.chmod(0o755)
    sudo = Path("/etc/sudoers.d/iusentra-claude")
    content = USER + ' ALL=(root) NOPASSWD: /usr/bin/docker, /usr/local/sbin/iusentra-claude-deploy ""\n'
    if sudo.exists() and sudo.read_text() != content:
        raise ValueError("Existing sudo grant differs")
    candidate = backup / "sudoers-candidate"
    candidate.write_text(content);candidate.chmod(0o440)
    run("visudo", "-cf", str(candidate))
    shutil.copyfile(candidate, sudo);sudo.chmod(0o440)
    run("visudo", "-c")
    run("runuser", "-u", USER, "--", "git", "config", "--global", "--add", "safe.directory", str(REPO))
    host = Path("/etc/ssh/ssh_host_ed25519_key.pub").read_text().split()
    prefs = json.loads(run("tailscale", "debug", "prefs").stdout)
    # Preserve shields-up semantics for all new inbound Tailscale traffic except
    # this single PC/SSH capability. Public interfaces are never matched.
    if not shutil.which("nft"):
        raise RuntimeError("nft unavailable: do not relax shields-up")
    rules = ('table inet iusentra_claude_ssh { chain input { '
             'type filter hook input priority -20; policy accept; '
             'iifname "tailscale0" ct state established,related accept; '
             'iifname "tailscale0" ip saddr 100.69.184.43 tcp dport 22 accept; '
             'iifname "tailscale0" counter drop; } }\n')
    config = Path("/etc/iusentra-claude-ssh.nft")
    if config.exists() and config.read_text() != rules:
        raise ValueError("Dedicated network policy changed: preserve it")
    config.write_text(rules);config.chmod(0o600)
    loader = Path("/usr/local/sbin/iusentra-claude-ssh-firewall")
    loader_body = ('#!/bin/sh\nset -eu\n{ if /usr/sbin/nft list table inet iusentra_claude_ssh >/dev/null 2>&1; then '
                   'printf "delete table inet iusentra_claude_ssh\\n"; fi; '
                   'cat /etc/iusentra-claude-ssh.nft; } | /usr/sbin/nft -f -\n')
    if loader.exists() and loader.read_text() != loader_body:
        raise ValueError("Dedicated firewall loader changed")
    loader.write_text(loader_body);loader.chmod(0o700)
    unit = Path("/etc/systemd/system/iusentra-claude-ssh-firewall.service")
    unit_body = ('[Unit]\nDescription=PC-only IUSENTRA Claude SSH over Tailscale\n'
                 'Before=tailscaled.service\nAfter=network-pre.target\n'
                 '[Service]\nType=oneshot\nExecStart=/usr/local/sbin/iusentra-claude-ssh-firewall\n'
                 'RemainAfterExit=yes\n[Install]\nWantedBy=multi-user.target\n')
    if unit.exists() and unit.read_text() != unit_body:
        raise ValueError("Dedicated firewall service changed")
    unit.write_text(unit_body);unit.chmod(0o644)
    run("systemctl", "daemon-reload")
    run("systemctl", "enable", "iusentra-claude-ssh-firewall.service")
    run("systemctl", "restart", "iusentra-claude-ssh-firewall.service")
    run("nft", "list", "table", "inet", "iusentra_claude_ssh")
    run("tailscale", "set", "--shields-up=false")
    prefs = json.loads(run("tailscale", "debug", "prefs").stdout)

    network = {"shields_up": prefs.get("ShieldsUp"),
               "ufw": run("ufw", "status", "verbose").stdout,
               "sshd_listeners": [x for x in run("sshd", "-T").stdout.splitlines()
                                  if x.startswith("listenaddress ")]}

    print(json.dumps({"user": USER, "peer": PEER, "repo": str(REPO),
        "network": network, "host_public_key": " ".join(host[:2]), "key_fingerprint": run("ssh-keygen", "-lf", str(auth)).stdout.strip(),
        "privilege": "repository write, sudo docker (root-equivalent), governed main deployment wrapper",
        "existing_keys_preserved": True, "application_deployed": False,
        "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}))

if __name__ == "__main__":
    main()
