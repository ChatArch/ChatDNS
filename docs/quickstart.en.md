# ChatDNS Quick Start

This guide follows a safe sequence: install, configure a profile, run read-only checks, change DNS, then issue certificates. Stop after the read-only checks on a first use. Continue only after confirming the account, provider, and target zone.

<div class="grid cards" markdown>

- **Inspect Before Mutation**

  ---

  Start with `list`, `records`, `ip`, and `cert check`.

- **Record Lifecycle**

  ---

  Write with `set`, read back with `records`, and delete with an exact filter.

- **Dynamic Addresses**

  ---

  `ddns` runs once by default. Add `--monitor` only after verification.

- **Safe Certificate Path**

  ---

  Use a separate staging output root; only production leaves enter the central store.

</div>

## 1. Install and Verify

**Python 3.12** is recommended. `requires-python >=3.10` only declares the minimum compatibility floor.

Install the stable package:

```bash
python -m pip install -U ChatDNS
chatdns --version
chatdns --help
```

Install the optional MCP integration when needed:

```bash
python -m pip install -U 'ChatDNS[mcp]'
```

For source development:

```bash
git clone https://github.com/ChatArch/ChatDNS.git
cd ChatDNS
python -m pip install -e '.[dev,docs]'
python -m pytest -q
mkdocs build --strict
```

## 2. Select a Provider and ChatEnv Profile

Current providers:

| Provider | CLI value | ChatEnv type | Required credentials |
| --- | --- | --- | --- |
| Alibaba Cloud DNS | `aliyun` | `aliyun` | `ALIBABA_CLOUD_ACCESS_KEY_ID`, `ALIBABA_CLOUD_ACCESS_KEY_SECRET` |
| Tencent Cloud DNSPod | `tencent` | `tencent` | `TENCENT_SECRET_ID`, `TENCENT_SECRET_KEY` |

Inspect which packages own the registered schemas:

```bash
chatenv status -t chatdns --detail
chatenv status -t aliyun --detail
chatenv status -t tencent --detail
```

### Create a Tencent Named Profile

This example creates a profile named `work`. Replace placeholders with real values, but never commit credentials to a repository, documentation, or logs.

```bash
chatenv new -t tencent -I --yes work
printf '%s\n' \
  'TENCENT_SECRET_ID=[REDACTED]' \
  'TENCENT_SECRET_KEY=[REDACTED]' \
  'TENCENT_REGION_ID=ap-guangzhou' \
  | chatenv paste --profile work --stdin --yes -I
chatenv cat -t tencent work
```

### Create an Aliyun Named Profile

```bash
chatenv new -t aliyun -I --yes work
printf '%s\n' \
  'ALIBABA_CLOUD_ACCESS_KEY_ID=[REDACTED]' \
  'ALIBABA_CLOUD_ACCESS_KEY_SECRET=[REDACTED]' \
  'ALIBABA_CLOUD_REGION_ID=cn-hangzhou' \
  | chatenv paste --profile work --stdin --yes -I
chatenv cat -t aliyun work
```

`chatenv cat` masks sensitive fields by default. Public examples and routine checks should not use `--no-mask`.

### Set a Default Provider

To avoid repeating `--provider`, initialize the active ChatDNS configuration and set a default:

```bash
chatenv init -t chatdns -I
chatenv set -I CHATDNS_PROVIDER=tencent
chatenv cat -t chatdns
```

An explicit command `--provider` always overrides `CHATDNS_PROVIDER`. Keep `--env work` when selecting named provider credentials.

## 3. Begin with Read-Only Checks

Using the Tencent `work` profile:

```bash
chatdns --env work list --provider tencent
chatdns --env work records example.com --provider tencent -I
chatdns --env work records www.example.com --type A --provider tencent -I
```

Inspect current IP addresses:

```bash
chatdns ip --type public
chatdns ip --type local --local-ip-cidr 192.168.0.0/16
```

Read-only commands may still access provider APIs or public IP services, but they do not modify DNS records.

## 4. Create, Read Back, and Delete a Record

Use documentation-only address `192.0.2.10` for the lifecycle example:

```bash
chatdns --env work set host.example.com \
  --provider tencent \
  --type A \
  --value 192.0.2.10 \
  --ttl 600 \
  -I

chatdns --env work records host.example.com \
  --provider tencent \
  --type A \
  -I
```

After confirming the target and value, delete the exact match:

```bash
chatdns --env work delete host.example.com \
  --provider tencent \
  --type A \
  --value 192.0.2.10 \
  --yes \
  -I
```

Safety rules:

- read back every `set` with `records`;
- give `delete` both `--type` and `--value` whenever possible;
- use `-I` in automation to prevent missing-input prompts;
- require explicit `--yes` for non-interactive deletion.

## 5. DDNS: One Shot Before Monitoring

Run one update:

```bash
chatdns --env work ddns home.example.com \
  --provider tencent \
  --ip-type public \
  --ttl 600 \
  -I
```

Read it back, then start monitoring only if the result is correct:

```bash
chatdns --env work records home.example.com --provider tencent -I
chatdns --env work ddns home.example.com \
  --provider tencent \
  --ip-type public \
  --monitor \
  --interval 120 \
  --log-file dynamic_ip_updater.log \
  -I
```

`--monitor` is a long-running foreground mode. Service installation, process supervision, and restart policy are outside the current ChatDNS CLI tree.

## 6. Certificates: Check, Staging, Production

First inspect local state:

```bash
chatdns cert check '*.example.com' --cert-path default
```

Validate staging with a separate output root so the production central store stays clean:

```bash
chatdns --env work cert apply \
  --domain '*.example.com' \
  --email admin@example.com \
  --provider tencent \
  --staging \
  --cert-dir "$HOME/.cache/chatdns/staging-certs" \
  --cert-path default \
  -I
```

After validating provider credentials, DNS-01, and ACME, issue the production certificate:

```bash
chatdns --env work cert apply \
  --domain '*.example.com' \
  --email admin@example.com \
  --provider tencent \
  --cert-path default \
  -I

chatdns cert check '*.example.com' --cert-path default
```

Production certificates default to:

```text
$CHATARCH_HOME/certs/<registered-domain>/<cert-path>/
```

Each leaf contains only four PEM files. See [Certificate Storage and Creation Rules](certificate-storage.md) for allocation, reuse, SAN, wildcard, symlink, and remote deployment contracts.

## 7. Render a Separate Infra Manifest

`cert manifest` reads JSON and renders a table:

```bash
chatdns cert manifest ./manifest.json
```

It does not scan the central store or deploy certificates over SSH. Server inventory, backup, path changes, `nginx -t`, reload, SNI readback, and rollback belong to Infra.

## Next Steps

- Browse every command, option, and side effect: [CLI Tree](cli-tree.md)
- Understand certificate storage and creation: [Certificate Storage and Creation Rules](certificate-storage.md)
- Return to the documentation hub: [Home](index.md)
