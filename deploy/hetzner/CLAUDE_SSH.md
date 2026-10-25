# Accesso dedicato Claude Code sul PC Antonio

Autorizzazione utente25/10/2026: modifiche e deploy sul server IUSENTRA.
Account separato `claude-iusentra`; chiave Ed25519 privata resta nel PC, fuori Git.
Accesso da100.69.184.43 tramite Tailscale, niente forwarding SSH/agent/X11.
Permessi: scrittura repository `/opt/iusentra/repo`, sudo Docker e wrapper deploy main.
Docker concede capacità equivalenti a root: questo è accesso operativo privilegiato,
non un account di sola consultazione. Nessuna distribuzione applicativa nel bootstrap.
Le altre chiavi SSH e il flusso CI/deploy restano conservati.

Uso: `ssh iusentra-claude`. Da Windows la connessione usa WSL come trasporto TCP
Tailscale e la chiave dedicata Windows. In WSL usa la chiave dedicata Linux.
Collaudo senza modifiche: `id`, `git -C /opt/iusentra/repo status --short`,
`sudo -n docker ps`. Non stampare file .env, segreti o dati dei fascicoli.
Deploy autorizzato: `sudo -n /usr/local/sbin/iusentra-claude-deploy` (main);
prima completare i gate CI e le verifiche richieste dal repository, preservare
hotfix/stato server e concorrenza con altri operatori. L'accesso non equivale
ad autorizzazione per cancellare dati, disabilitare gate o forzare Git.

Revoca: da un altro accesso amministrativo rimuovere soltanto la riga con
commento `claude-iusentra-pcantonio-20261025` da authorized_keys dell'account,
terminare le sue sessioni se necessario, revocare il suo file sudoers e ACL.
Backup ACL precedente: /opt/iusentra/backups/ssh-claude-20261025/repo-acl-before.txt.
Non rimuovere altre chiavi o ripristinare indiscriminatamente ACL dopo altri lavori.
