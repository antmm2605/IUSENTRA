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
    return subprocess.run(args, check=True, capture_output=True, text=True)

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
    print(json.dumps({"user": USER, "peer": PEER, "repo": str(REPO),
        "host_public_key": " ".join(host[:2]), "key_fingerprint": run("ssh-keygen", "-lf", str(auth)).stdout.strip(),
        "privilege": "repository write, sudo docker (root-equivalent), governed main deployment wrapper",
        "existing_keys_preserved": True, "application_deployed": False,
        "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}))

if __name__ == "__main__":
    main()
