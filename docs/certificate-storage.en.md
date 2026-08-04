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

## Two-Level Certificate Layout

ChatDNS always stores a certificate at:

```text
$CHATARCH_HOME/certs/<registered-domain>/<cert-path>/
```

The registered domain is the longest provider-managed zone that matches the requested name. A root wildcard request is:

```bash
chatdns cert apply \
  -d '*.example.com' \
  -e admin@example.com \
  --provider aliyun
```

Without `--cert-path`, the default result is:

```text
$CHATARCH_HOME/certs/
├── README.md                 # optional; the only root-level note
└── example.com/
    └── default/
        ├── cert.pem
        ├── chain.pem
        ├── fullchain.pem
        └── privkey.pem
```

Use the URI name explicitly for a deeper wildcard:

```bash
chatdns cert apply \
  -d '*.precision.example.com' \
  -e admin@example.com \
  --provider aliyun \
  --cert-path precision
```

The result is `$CHATARCH_HOME/certs/example.com/precision/`. `--cert-path` must be one safe directory segment. Absolute paths, `/`, `\`, `.`, `..`, and traversal are rejected. ChatDNS can print a URI-style wildcard suggestion, but it never silently replaces an explicit name or the default behavior.

## Defaults, Collisions, And Renewal Reuse

- An omitted `--cert-path` starts at `default`.
- If that directory belongs to a different SAN set, ChatDNS tries `default-2`, then `default-3`.
- Explicit-name collisions use the same `<name>-2`, `<name>-3` sequence.
- Explicit names that can overlap generated suffixes share one lock namespace; for example, `foo` and `foo-2` cannot allocate the same directory concurrently.
- A directory with the exact normalized SAN set is reused for renewal and does not gain a new suffix.
- `chatdns cert check` accepts `--cert-path`; without it, ChatDNS scans the two-level tree for a certificate that covers the requested names.

A wildcard covers exactly one level: `*.example.com` covers `nas.example.com`, but not `foo.precision.example.com`. The latter requires `*.precision.example.com`.

## File Roles, Modes, And Private ACME State

Every leaf certificate directory contains exactly four PEM files:

| File or directory | Purpose | Mode |
|---|---|---:|
| Certificate root | Registered-domain directories and optional `README.md` | `0700` |
| Certificate leaf directory | Four deployment files for one certificate | `0700` |
| `privkey.pem` | Certificate private key | `0600` |
| `cert.pem` | Leaf certificate | `0644` |
| `chain.pem` | Intermediate chain | `0644` |
| `fullchain.pem` | Leaf plus intermediate chain | `0644` |

ACME account keys, issuance staging directories, and temporary keys never enter `certs/`. The default private state directory is:

```text
$CHATARCH_HOME/private/chatdns/acme/
```

For a new certificate, ChatDNS generates the key in memory. After ACME returns a chain, it splits and verifies the staged certificate/key pair in private state before writing the four PEM files. Never commit either certificate storage or private ACME state, and never expose private-key content.

## SAN Grouping And Renewal

Input names from one provider-managed zone form one SAN certificate. One directory-resolution call accepts exactly one managed zone; the CLI groups multi-zone input before previewing and issuing each certificate. Renewal:

1. locates the existing two-level directory for the complete SAN set;
2. checks whether the certificate is missing or expires within 30 days;
3. checks that every requested SAN is covered;
4. requests a certificate only when required or when `--force` is explicit.

## Infra Manifest, Status, And Scripts

In current `0.1.7`, `chatdns cert manifest` is only a read-only view:

```bash
cd Infra
chatdns cert manifest
chatdns cert manifest ./manifest.json
```

An empty file, empty object, or empty `certificates` container renders as an empty table. The command accepts top-level `certificate_groups`, `certificates`, or `groups` collections and shows ID, registered domain, certificate path, SANs, deployment counts, and status.

The aligned contract should split the workflow into three layers:

| Need | Target CLI | Write location |
| --- | --- | --- |
| View the current internal certificate state | `chatdns cert status [DOMAINS]...` | Read-only scan of the certificate root |
| Create/update the certificate inventory | `chatdns cert manifest init ./manifest.json --from-store` | Infra-workspace `manifest.json`, not the live certificate root |
| Generate common server sync scripts | `chatdns cert script render TEMPLATE --manifest ./manifest.json --output ./scripts` | Infra-workspace `scripts/`; write scripts only by default |

`manifest.json` and `scripts/` are Infra orchestration assets, not live certificate-root contents. The live root still contains only the two-level certificate tree and four PEM files per leaf. `status` can read the live root; `manifest init` writes leaf/SAN/expiry/deployment metadata into the manifest; `script render` then uses the manifest to generate common templates such as SSH+Nginx atomic sync, copy-only sync, and containerized Nginx reload.

## Remote Infrastructure Path

Remote infrastructure preserves the same relative path:

```text
<remote-home>/.chatarch/certs/<registered-domain>/<cert-path>/
```

Nginx references `fullchain.pem` and `privkey.pem`. Models write specific synchronization or update scripts from live server evidence; ChatDNS does not hard-code those deployment workflows. A remote change must back up certificates and configuration, install atomically, test configuration, reload, roll back on failure, and read the live certificate back with SNI.

## Safety Checks

Use `--staging` before a production request. After production issuance, verify at least:

- the target is exactly two directory levels below the root;
- neither the managed-zone directory nor the certificate leaf resolves through a symlink;
- the leaf directory contains only four PEM files;
- complete SAN coverage;
- matching public keys in `cert.pem` and `privkey.pem`;
- removal of temporary `_acme-challenge` TXT records;
- `0600` private-key modes;
- successful remote `nginx -t` and live SNI certificate readback.
