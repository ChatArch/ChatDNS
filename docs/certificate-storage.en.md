# Certificate Storage And Creation Rules

ChatDNS uses DNS-01 to issue certificates and writes certificates and private keys below an explicit certificate root. This page defines root selection, first-use file creation, wildcard/SAN grouping, and the shared path convention used by the ChatArch central store and remote infrastructure.

## Root Precedence

The certificate root is resolved in this order, with earlier values taking precedence:

1. CLI `--cert-dir` or Python `SSLCertUpdater(cert_dir=...)`;
2. ChatEnv `CHATDNS_CERT_DIR`;
3. `$CHATARCH_HOME/certs`.

`CHATARCH_HOME` is selected in this order:

1. CLI `--chatarch-home` or Python `chatarch_home=`;
2. the `CHATARCH_HOME` environment variable;
3. `~/.chatarch`.

When `CHATDNS_CERT_DIR` contains `$CHATARCH_HOME`, ChatDNS expands it using the effective home for the current command. It does not use a stale ambient home when `--chatarch-home` selects another store.

## Managing The Variable With ChatEnv

`CHATDNS_CERT_DIR` is a non-secret directory setting and can be stored in an active or named ChatDNS profile:

```bash
chatenv init -t chatdns -I
chatenv set 'CHATDNS_CERT_DIR=$CHATARCH_HOME/certs' -I
chatenv cat -t ChatDNS
```

Save the active value as a named profile:

```bash
chatenv save -t ChatDNS work -I
chatdns --chatarch-home /srv/chatarch --env work cert check example.com
```

An explicit path always wins:

```bash
chatdns cert check example.com --cert-dir /tmp/cert-audit
```

## Automatically Created Layout

Given an effective root of `$CHATARCH_HOME/certs`, this request:

```bash
chatdns cert apply \
  -d example.com \
  -d '*.example.com' \
  -e admin@example.com \
  --provider aliyun
```

produces:

```text
$CHATARCH_HOME/certs/
├── account.key
├── example.com.key
└── example.com/
    ├── cert.pem
    ├── chain.pem
    ├── fullchain.pem
    └── privkey.pem
```

Rules:

- `account.key` is the ACME account key for this issuance root and is generated on first use.
- `<certificate-primary>.key` is the persistent certificate private key. The primary is the first requested name in a managed DNS-zone group.
- `<certificate-primary>/` is created after certificate issuance succeeds.
- A wildcard `*` is converted to `_` when a domain is used as a file name.
- If ACME fails before issuance, account/domain keys may exist while the certificate output directory does not.

## File Roles And Permissions

| File or directory | Purpose | Mode |
|---|---|---:|
| Certificate root | ACME keys and certificate groups | `0700` |
| Certificate group directory | Deployment files for one SAN certificate | `0700` |
| `account.key` | ACME account private key | `0600` |
| `<certificate-primary>.key` | Persistent certificate private key | `0600` |
| `privkey.pem` | Private key deployed to Nginx | `0600` |
| `cert.pem` | Leaf certificate | `0644` |
| `chain.pem` | Intermediate chain | `0644` |
| `fullchain.pem` | Leaf plus intermediate chain for Nginx | `0644` |

Never commit a certificate root to Git or expose private-key content in logs, reports, or chat.

## Wildcard And Multi-SAN Groups

ChatDNS discovers the provider-managed DNS zone and handles input names from the same zone as one SAN certificate. The first name selects the persistent key and output directory, so place the non-wildcard primary first:

```bash
-d example.com -d '*.example.com'
```

Renewal is evaluated for the stored group certificate:

1. verify that the primary certificate exists and is not near expiry;
2. verify that its SAN extension covers every requested name;
3. renew only when the certificate is missing, near expiry, or has incomplete SAN coverage.

This avoids treating `*.example.com` as an unrelated local certificate and requesting the same group repeatedly.

## ChatArch Central Store

Multi-zone central management uses a deterministic two-level path:

```text
$CHATARCH_HOME/certs/<managed-zone>/<certificate-primary>/
```

The central runner passes the zone root explicitly:

```bash
chatdns cert apply \
  --cert-dir "$CHATARCH_HOME/certs/example.com" \
  -d example.com \
  -d '*.example.com' \
  -e admin@example.com
```

ChatDNS creates the primary directory below it, resulting in:

```text
$CHATARCH_HOME/certs/example.com/example.com/
```

The manifest invariant is:

```text
managed_zone = example.com
primary_domain = example.com
local_dir = example.com/example.com
```

The zone partition makes provider/profile selection, ACME accounts, logs, renewal, and deployment auditable by authoritative DNS zone.

## Remote Infrastructure Path

ChatArch infrastructure preserves the same relative path:

```text
<remote-home>/.chatarch/certs/<managed-zone>/<certificate-primary>/
```

Nginx references `fullchain.pem` and `privkey.pem` there. Remote migration belongs to the infrastructure synchronization layer and must back up old certificates and Nginx configs, install atomically, run `nginx -t`, reload, roll back on failure, and read the live certificate back with SNI. The ChatDNS CLI only issues certificates and writes local files; it does not modify remote Nginx automatically.

## Safety Checks

Use `--staging` before a production request. After production issuance, verify at least:

- complete SAN coverage;
- matching public keys in `cert.pem` and `privkey.pem`;
- removal of temporary `_acme-challenge` TXT records;
- `0600` private-key modes;
- successful remote `nginx -t` and live SNI certificate readback.
