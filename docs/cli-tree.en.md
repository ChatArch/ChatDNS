# ChatDNS CLI Tree

This page maps the current public CLI from `chatdns --help`, command-level help, source, and tests. It answers two questions: how to invoke a command, and whether the invocation has external side effects.

Start with the [Quick Start](quickstart.md) if provider profiles are not configured yet. See [Certificate Storage and Creation Rules](certificate-storage.md) for certificate files and the remote infrastructure boundary.

## Top-Level Commands

```text
chatdns
├── cert                # DNS-01 certificate issuance, checks, and Infra manifest rendering
│   ├── apply           # Issue or renew; writes DNS TXT records and local certificate files
│   ├── check           # Inspect local expiry and renewal status
│   └── manifest        # Render a separate Infra manifest without modifying it
├── ddns                # Update once or monitor a dynamic IP; may write DNS records
├── delete              # Filter and delete DNS records
├── ip                  # Detect public or local IP without changing DNS
├── list                # List managed zones in the provider account
├── records             # Query records for a zone or full hostname
└── set                 # Idempotently create or update a DNS record
```

Public top-level options:

| Option | Purpose |
| --- | --- |
| `--version` | Print the ChatDNS version |
| `-e, --env PROFILE` | Select a named provider ChatEnv profile before the command |
| `--chatarch-home DIR` | Override `CHATARCH_HOME` for profile loading in this invocation |
| `--help` | Print top-level help |

## Side-Effect Levels

| Level | Commands | Boundary |
| --- | --- | --- |
| Read | `list`, `records` | Query provider APIs without changing DNS |
| Read | `ip` | Public mode calls IP detection services; local mode scans local interfaces |
| Read | `cert check` | Reads local certificates and computes renewal state; no ACME request |
| Read | `cert manifest` | Reads and renders a JSON manifest without modifying it |
| DNS write | `set`, `delete`, `ddns` | Create, update, or delete provider records |
| DNS and certificate write | `cert apply` | Write `_acme-challenge` TXT records, run ACME, and install local PEM files |

“Read” means no DNS or certificate mutation. It does not mean offline: `list`, `records`, and public `ip` still access the network.

## Domain and Record Discovery

```text
chatdns list
├── --provider aliyun|tencent    # Explicit provider; otherwise use CHATDNS_PROVIDER
├── --page INTEGER               # Default: 1
├── --page-size INTEGER          # Default: 20
└── --env PROFILE                # Command-level named provider profile

chatdns records [TARGET]
├── --domain DOMAIN              # Alternative input paired with --rr
├── --rr RR                      # Optional host-record filter
├── --type TYPE                  # Optional record-type filter
├── --provider aliyun|tencent
├── --env PROFILE
└── -i | -I                      # Force or disable interaction

chatdns ip
├── --type public|local          # Default: public
└── --local-ip-cidr CIDR         # Filter interface addresses in local mode
```

`records` accepts either a managed zone such as `example.com` or a full hostname such as `www.example.com`. If a positional target and `--domain/--rr` are both present, the positional target wins and the CLI prints a warning.

```bash
chatdns --env work list --provider tencent
chatdns --env work records example.com --provider tencent -I
chatdns --env work records www.example.com --type A --provider tencent -I
chatdns ip --type local --local-ip-cidr 192.168.0.0/16
```

## DNS Writes and DDNS

```text
chatdns set [FULL_DOMAIN]
├── --domain DOMAIN + --rr RR    # Alternative to FULL_DOMAIN
├── --type TYPE                  # Default: A
├── --value VALUE                # Required; interaction may supply it
├── --ttl INTEGER                # Default: 600
├── --provider aliyun|tencent
├── --env PROFILE
└── -i | -I

chatdns delete [FULL_DOMAIN]
├── --domain DOMAIN + --rr RR
├── --type TYPE                  # Required; interaction may supply it
├── --value VALUE                # Optional exact-value filter
├── --yes                        # Required for non-interactive deletion
├── --provider aliyun|tencent
├── --env PROFILE
└── -i | -I

chatdns ddns [FULL_DOMAIN]
├── --domain DOMAIN + --rr RR
├── --ttl INTEGER                # Default: 600
├── --ip-type public|local       # Default: public
├── --local-ip-cidr CIDR
├── --monitor                    # Omit for a one-shot update
├── --interval SECONDS           # Default: 120
├── --max-retries INTEGER        # Default: 3
├── --retry-delay SECONDS        # Default: 5
├── --log-file PATH
├── --log-level LEVEL            # Default: INFO
├── --provider aliyun|tencent
├── --env PROFILE
└── -i | -I
```

`set` uses the provider's idempotent update path; read the record back with `records`. `delete` displays matching records first and fails closed in non-interactive mode unless `--yes` is present. `ddns` runs once by default and loops only with explicit `--monitor`.

```bash
chatdns --env work set host.example.com -p tencent -t A -v 192.0.2.10 -I
chatdns --env work records host.example.com -p tencent -t A -I
chatdns --env work delete host.example.com -p tencent -t A -v 192.0.2.10 --yes -I

chatdns --env work ddns host.example.com -p tencent -I
chatdns --env work ddns host.example.com -p tencent --monitor --interval 120 -I
```

## Certificate Commands

```text
chatdns cert apply
├── --domain DOMAIN              # Repeat for SANs and wildcards
├── --email EMAIL                # Let's Encrypt account email; short form is -e
├── --provider aliyun|tencent
├── --env PROFILE                # Long form only because -e is email here
├── --cert-dir DIR               # Explicit certificate root
├── --cert-path NAME             # Safe single-segment name under the registered domain
├── --staging                    # Use Let's Encrypt staging
├── --force                      # Force issuance/renewal despite a valid local certificate
├── --log-file PATH
├── --log-level LEVEL            # Default: INFO
└── -i | -I

chatdns cert check [DOMAINS]...
├── --cert-dir DIR
├── --cert-path NAME
└── --provider aliyun|tencent

chatdns cert manifest [MANIFEST_PATH]
└── MANIFEST_PATH                # Default: ./manifest.json; read-only
```

Certificate-root precedence is explicit `--cert-dir`, then ChatEnv `CHATDNS_CERT_DIR`, then `$CHATARCH_HOME/certs`. Production leaves live at:

```text
<certificate-root>/<registered-domain>/<cert-path>/
```

Without `--cert-path`, allocation starts at `default`; collisions use `default-2`, `default-3`, and so on. An existing leaf is reused only for the same fully normalized SAN set. A leaf contains only `cert.pem`, `chain.pem`, `fullchain.pem`, and `privkey.pem`.

`cert apply` has high-impact side effects. Validate provider credentials, DNS-01, and ACME with a separate staging output root before production issuance. Never point Nginx or another consumer at staging certificates.

```bash
chatdns --env work cert apply \
  -d '*.example.com' \
  -e admin@example.com \
  -p tencent \
  --staging \
  --cert-dir "$HOME/.cache/chatdns/staging-certs" \
  --cert-path default \
  -I

chatdns --env work cert apply \
  -d '*.example.com' \
  -e admin@example.com \
  -p tencent \
  --cert-path default \
  -I

chatdns cert check '*.example.com' --cert-path default
```

`cert manifest` does not scan the certificate root or deploy certificates. It only renders a separate Infra manifest. SSH synchronization, Nginx path updates, `nginx -t`, reload, and rollback belong to Infra, not ChatDNS.

## Profiles and Interaction

Provider selection order:

1. explicit command `--provider`;
2. ChatEnv `CHATDNS_PROVIDER`;
3. default `aliyun`.

Provider credentials come from the matching Aliyun or Tencent active/named ChatEnv profile. A profile can be selected globally:

```bash
chatdns --env work list -p tencent
```

`list`, `ddns`, `set`, `records`, and `delete` also accept command-level `--env/-e`, and the command-level value overrides the global value. On `cert apply`, `-e` means email, so use long-form `--env` or place the global profile before `cert`.

Commands with `-i/-I` follow the ChatStyle interaction contract: `-i` forces prompts when a terminal is available; `-I` disables prompts and fails fast when required values are missing. Automation should pass complete inputs and `-I`.

## Python API and MCP Boundary

The CLI is not the only interface. Main package-root Python exports include:

```text
chatdns
├── DNSClient
├── AliyunDNSClient
├── TencentDNSClient
├── DynamicIPUpdater
├── SSLCertUpdater
├── DNSClientType
├── create_dns_client
└── split_full_domain
```

With `ChatDNS[mcp]` installed, `chatdns.mcp.register(mcp)` registers:

| MCP tool | Type |
| --- | --- |
| `dns_list_domains` | read |
| `dns_get_records` | read |
| `dns_add_record` | write |
| `dns_delete_record` | write |
| `dns_ddns_update` | write |

MCP tools are not `chatdns` subcommands. Intentionally hidden Certbot hooks are internal compatibility surfaces and are not documented as stable user commands in this tree.

## Documentation Update Contract

- Add a command here only after it appears in actual public Click help.
- Keep the English and Chinese pages, side-effect table, and related quick-start flows synchronized.
- Do not present hidden commands, planned capabilities, or remote Infra operations as stable CLI.
- Treat `chatdns <path> --help` and tests as the final authority for options.
