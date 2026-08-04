# ChatDNS

ChatDNS is ChatArch's DNS, DDNS, and ACME DNS-01 certificate tool. It organizes Aliyun DNS, Tencent Cloud / DNSPod, ChatEnv profiles, certificate checks, and the central certificate store behind one auditable command surface.

## Choose by scenario

| Scenario | Document | Recommended start |
| --- | --- | --- |
| First install and profile setup | [Quick Start](quickstart.md) | Begin with read-only checks |
| Find commands and options | [CLI Tree](cli-tree.md) | Review the side-effect matrix |
| Issue or check certificates | [Certificate Storage and Allocation](certificate-storage.md) | Use a separate staging directory |
| Integrate Python or MCP | [CLI Tree](cli-tree.md) | Review interface boundaries |

<div class="grid cards" markdown>

- **Quick Start**

  ---

  Installation, ChatEnv profiles, read-only verification, DNS writes, and the safe certificate flow.

  [Get started](quickstart.md)

- **CLI Tree**

  ---

  Real command topology, option entry points, profile rules, and side-effect levels.

  [Browse commands](cli-tree.md)

- **Certificate Contract**

  ---

  Registered domains, cert paths, SAN reuse, symlink rejection, and the Infra boundary.

  [Read the contract](certificate-storage.md)

</div>

## Recommended environment

**Python 3.12** is recommended. `requires-python >=3.10` only declares the minimum compatibility floor.

```bash
uv venv --python 3.12
uv pip install ChatDNS
chatdns --help
```

## Side-effect summary

| Type | Commands |
| --- | --- |
| Provider/local read-only | `list`, `records`, `ip`, `cert check`, `cert manifest` |
| DNS writes | `set`, `delete`, `ddns` |
| DNS plus local certificate writes | `cert apply` |

Stop after read-only commands on a first use. ChatDNS does not own SSH distribution, Nginx rewrite/reload, or server rollback; those belong to Infra.

## Supported providers

- Aliyun DNS
- Tencent Cloud / DNSPod

Accounts are isolated with ChatEnv profiles. Select one with `chatdns --env PROFILE ...`.
