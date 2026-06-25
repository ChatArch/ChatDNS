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

ChatDNS is a ChatArch DNS helper extracted from ChatTool. It provides a standalone `chatdns` CLI and importable Python API for DNS record management, DDNS updates, provider clients, IP detection, and MCP registration.

## Commands

```bash
chatdns --help
chatdns list --provider aliyun
chatdns records example.com
chatdns records test.example.com
chatdns set test.example.com -t A -v 1.2.3.4
chatdns delete test.example.com -t A -v 1.2.3.4 --yes
chatdns ip
chatdns ddns home.example.com
```

Supported providers in this release:

- Aliyun DNS
- Tencent Cloud DNSPod

Certificate management from the old `chattool dns cert` surface is intentionally not part of this first DNS-only extraction. It remains a separate boundary to review before moving certificate code.

## Configuration

ChatDNS reads provider credentials from environment / ChatEnv-compatible config fields:

- `ALIBABA_CLOUD_ACCESS_KEY_ID`
- `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
- `ALIBABA_CLOUD_REGION_ID`
- `TENCENT_SECRET_ID`
- `TENCENT_SECRET_KEY`
- `TENCENT_REGION_ID`

Provider aliases are registered through the package's `chatenv.configs` entry point as `chatdns.config`.

## Development

```bash
python -m pytest -q
chatpypi build --project-dir .
chatpypi check --project-dir .
PYTHONPATH=src python -m chatdns.cli --help
```
