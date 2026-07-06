<p align="center">
    <a href="https://pypi.python.org/pypi/ChatDNS">
        <img src="https://img.shields.io/pypi/v/ChatDNS.svg" alt="PyPI version" />
    </a>
    <a href="https://github.com/ChatArch/ChatDNS/actions/workflows/ci.yml">
        <img src="https://github.com/ChatArch/ChatDNS/actions/workflows/ci.yml/badge.svg" alt="Tests" />
    </a>
    <a href="https://ChatArch.github.io/ChatDNS">
        <img src="https://img.shields.io/badge/docs-latest-blue.svg" alt="Docs" />
    </a>
</p>

# ChatDNS

ChatDNS is a ChatArch DNS helper extracted from ChatTool. It provides a standalone `chatdns` CLI and importable Python API for DNS record management, DDNS updates, provider clients, IP detection, DNS-01 certificate automation, and MCP registration.

## Commands

```bash
chatdns --help
chatdns list
chatdns --env work list --provider tencent
chatdns list --provider tencent --env work
chatdns records example.com
chatdns records test.example.com
chatdns set test.example.com -t A -v 1.2.3.4
chatdns delete test.example.com -t A -v 1.2.3.4 --yes
chatdns ip
chatdns cert apply -d example.com -d '*.example.com' -e admin@example.com --provider aliyun
chatdns cert check example.com
```

Supported providers in this release:

- Aliyun DNS
- Tencent Cloud DNSPod

Certificate management from the old `chattool dns cert` surface is now available as `chatdns cert`. It uses ACME DNS-01 validation and writes TXT records through the configured DNS provider. Treat live certificate issuance as an external side effect: test with `--staging` first and verify provider credentials before production use.

## Configuration

ChatDNS reads provider credentials and defaults from environment / ChatEnv-compatible config fields:

- `CHATDNS_PROVIDER` (default DNS provider/channel: `aliyun` or `tencent`)
- `ALIBABA_CLOUD_ACCESS_KEY_ID`
- `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
- `ALIBABA_CLOUD_REGION_ID`
- `TENCENT_SECRET_ID`
- `TENCENT_SECRET_KEY`
- `TENCENT_REGION_ID`

Active ChatEnv profiles are loaded automatically from `$CHATARCH_HOME/envs` (default: `~/.chatarch/envs`). Use `--env/-e` to select a named provider profile, either globally before the command (`chatdns --env work list -p tencent`) or on DNS commands after the provider (`chatdns list -p tencent -e work`). Command-level `--env/-e` overrides the global value. `chatdns cert apply` keeps `-e` for email, so use `--env work` there.

Provider aliases are registered through the package's `chatenv.configs` entry point as `chatdns.config`.

## Development

```bash
python -m pytest -q
chatpypi build --project-dir .
chatpypi check --project-dir .
PYTHONPATH=src python -m chatdns.cli --help
```
