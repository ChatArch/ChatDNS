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
| Inspect every public command directly | `chatdns --help` |

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
├── cert
│   ├── apply       # Issue/install through DNS-01; writes DNS and local certs
│   ├── check       # Read-only local certificate status
│   └── manifest    # Read-only Infra manifest rendering
├── ddns            # One-shot or monitored A updates
├── delete          # Delete a DNS record
├── ip              # Detect public/local IP
├── list            # List managed zones
├── records         # Query records
└── set             # Idempotently set a record
```

See the [CLI Tree](docs/cli-tree.en.md) for full options, profile placement rules, interactive flags, and the side-effect matrix.

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
| `cert check`, `cert manifest` | local read-only |
| `set`, `delete`, `ddns` | writes to the DNS provider |
| `cert apply` | writes DNS challenges and local certificates |

ChatDNS owns DNS operations, certificate issuance/checks, and manifest parsing. SSH distribution, Nginx rewrite/reload, and server rollback belong to Infra and are not executed by ChatDNS.

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
