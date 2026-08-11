# ChatDNS

[English](README.en.md) · [简体中文](README.md)

ChatDNS is ChatArch's DNS, DDNS, and ACME DNS-01 certificate tool. It presents one workflow across Aliyun DNS and Tencent Cloud / DNSPod providers, selects accounts through ChatEnv profiles, and safely installs certificates under `$CHATARCH_HOME/certs/<registered-domain>/<cert-path>/`.

- Documentation: <https://arch.gh.wzhecnu.cn/ChatDNS/en/>
- Quick Start: <https://arch.gh.wzhecnu.cn/ChatDNS/en/quickstart/>
- CLI Tree: <https://arch.gh.wzhecnu.cn/ChatDNS/en/cli-tree/>
- Certificate Contract: <https://arch.gh.wzhecnu.cn/ChatDNS/en/certificate-storage/>

## Choose by scenario

| Goal | Entry point |
| --- | --- |
| Install ChatDNS and validate a profile safely | [Quick Start](docs/quickstart.en.md) |
| Find commands, options, and side effects | [CLI Tree](docs/cli-tree.en.md) |
| Understand certificate paths, SAN reuse, and symlink rejection | [Certificate Storage and Allocation](docs/certificate-storage.en.md) |
| Inspect every public command directly | `chatdns --tree` / `chatdns --help` |

## Install

**Python 3.12** is recommended. The package metadata value `>=3.10` is only the minimum compatibility floor; it does not pin an environment to Python 3.10.

```bash
uv venv --python 3.12
uv pip install ChatDNS
chatdns --version
```

For development:

```bash
uv pip install -e '.[dev,docs]'
```

## Start read-only

Select a ChatEnv profile and provider, then begin with read-only commands:

```bash
chatdns --env work list --provider tencent
chatdns --env work records example.com --provider tencent
chatdns ip --type public
chatdns --env work cert check '*.example.com' --cert-path default
```

Confirm the account, zone, and records before running `set`, `delete`, `ddns`, or `cert apply`.

## CLI tree

```text
chatdns
├── --help  # Show this message and exit.
├── --version  # Show the installed ChatDNS version.
├── --tree  # Print this registered command tree and exit.
├── cert  # Manage Let's Encrypt certificates through DNS-01 validation.
│   ├── apply [--domain DOMAINS] [--email EMAIL] [--provider PROVIDER] [--env ENV-PROFILE] [--cert-dir CERT-DIR] [--cert-path CERT-PATH] [--staging] [--force] [--log-file LOG-FILE] [--log-level LOG-LEVEL] [--interactive]  # Apply or renew certificates using ACME DNS-01 validation.
│   ├── check [DOMAINS...] [--cert-dir CERT-DIR] [--cert-path CERT-PATH] [--provider PROVIDER]  # Check local certificate expiry for one or more domains.
│   ├── manifest  # Show, create, or validate Infra certificate manifests.
│   │   ├── init [MANIFEST-PATH] [--cert-dir CERT-DIR] [--cert-path CERT-PATH] [--from-store] [--scripts-dir SCRIPTS-DIR] [--force] [--format OUTPUT-FORMAT]  # Create an Infra manifest and scripts/README scaffold from the local store.
│   │   ├── show [MANIFEST-PATH]  # Render an Infra certificate manifest as a table without modifying it.
│   │   └── validate [MANIFEST-PATH]  # Validate manifest shape and referenced local certificate files.
│   └── status [DOMAINS...] [--cert-dir CERT-DIR] [--cert-path CERT-PATH] [--expiring-within EXPIRING-WITHIN] [--format OUTPUT-FORMAT] [--strict]  # Scan the internal certificate store and report current leaf status.
├── ddns [FULL-DOMAIN] [--domain DOMAIN] [--rr RR] [--ttl TTL] [--interval INTERVAL] [--max-retries MAX-RETRIES] [--retry-delay RETRY-DELAY] [--monitor] [--log-file LOG-FILE] [--log-level LOG-LEVEL] [--ip-type IP-TYPE] [--local-ip-cidr LOCAL-IP-CIDR] [--provider PROVIDER] [--env ENV-PROFILE] [--interactive]  # Run dynamic DNS updates once or in continuous monitoring mode.
├── delete [FULL-DOMAIN] [--domain DOMAIN] [--rr RR] [--type RECORD-TYPE] [--value VALUE] [--yes] [--provider PROVIDER] [--env ENV-PROFILE] [--interactive]  # Delete DNS records by domain, host record, type, and optional value.
├── ip [--type IP-TYPE] [--local-ip-cidr LOCAL-IP-CIDR]  # Show the current public or local IP without touching DNS records.
├── list [--provider PROVIDER] [--page PAGE-NUMBER] [--page-size PAGE-SIZE] [--env ENV-PROFILE]  # List DNS domains in the provider account.
├── records [TARGET] [--domain DOMAIN] [--rr RR] [--type RECORD-TYPE] [--provider PROVIDER] [--env ENV-PROFILE] [--interactive]  # Show DNS record details.
└── set [FULL-DOMAIN] [--domain DOMAIN] [--rr RR] [--type RECORD-TYPE] [--value VALUE] [--ttl TTL] [--provider PROVIDER] [--env ENV-PROFILE] [--interactive]  # Create or update a DNS record.
```

See the [CLI Tree](docs/cli-tree.en.md) for the live `chatdns --tree` output, full options, profile placement rules, interactive flags, and the side-effect matrix.

Use `chatdns cert status` to inspect the current internal certificate store. `chatdns cert manifest init` creates or updates an Infra-workspace `manifest.json` and a `scripts/README.md` manual-edit scaffold; ChatDNS does not provide a `cert script` generation or execution interface.

## Configuration resolution

Provider precedence:

1. command-line `--provider`;
2. `CHATDNS_PROVIDER` in the ChatDNS profile;
3. `aliyun`.

Select a profile globally with `chatdns --env PROFILE ...`; DNS commands also expose command-level `--env`. Aliyun and Tencent credentials come from same-named ChatEnv profiles. Secrets never belong in the repository.

## Capabilities and boundaries

| Operation | Side effect |
| --- | --- |
| `list`, `records` | read-only provider API |
| `ip` | local interface reads or a public-IP request |
| `cert check`, `cert status`, `cert manifest show`, `cert manifest validate` | local read-only |
| `cert manifest init` | writes local Infra `manifest.json` and `scripts/README.md` only |
| `set`, `delete`, `ddns` | writes to the DNS provider |
| `cert apply` | writes DNS challenges and local certificates |

ChatDNS owns DNS operations, certificate issuance/checks, certificate-store status scans, and manifest creation/parsing. SSH distribution, Nginx rewrite/reload, and server rollback belong to Infra; ChatDNS does not execute or generate sync scripts.

## Python API and MCP

```python
from chatdns import create_dns_client, DynamicIPUpdater, SSLCertUpdater
```

MCP exposes DNS query/set, IP discovery, DDNS, and certificate issuance tools. MCP tools are not CLI subcommands. See the [CLI Tree](docs/cli-tree.en.md) for the mapping.

## Verify

```bash
pytest -q
mkdocs build --strict
```

## License

MIT
