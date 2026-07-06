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

ChatDNS 是从 ChatTool 分离出来的 ChatArch DNS helper。它提供独立 `chatdns` CLI 和可导入 Python API，用于 DNS 记录管理、DDNS 更新、云厂商 provider client、IP 探测、DNS-01 证书自动化与 MCP 注册。

## 命令

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

当前支持：

- 阿里云 DNS
- 腾讯云 DNSPod

旧 `chattool dns cert` 证书管理面现已迁入 `chatdns cert`。该能力使用 ACME DNS-01 验证，并通过配置的 DNS provider 写入 `_acme-challenge` TXT 记录。证书申请和 DNS 写入是外部副作用；生产申请前建议先使用 `--staging` 验证。

## 配置

ChatDNS 通过环境变量 / ChatEnv-compatible config 字段读取 provider 凭证和默认渠道：

- `CHATDNS_PROVIDER`（默认 DNS provider/channel: `aliyun` 或 `tencent`）
- `ALIBABA_CLOUD_ACCESS_KEY_ID`
- `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
- `ALIBABA_CLOUD_REGION_ID`
- `TENCENT_SECRET_ID`
- `TENCENT_SECRET_KEY`
- `TENCENT_REGION_ID`

ChatDNS 会自动加载 `$CHATARCH_HOME/envs`（默认 `~/.chatarch/envs`）下的 active ChatEnv profile。使用 `--env/-e` 可切换 named provider profile：既可以放在全局位置（`chatdns --env work list -p tencent`），也可以放在 DNS 命令上跟随 provider 使用（`chatdns list -p tencent -e work`）。命令级 `--env/-e` 会覆盖全局值。`chatdns cert apply` 的 `-e` 保留给 email，因此证书命令使用 `--env work`。

包通过 `chatenv.configs` entry point 注册 `chatdns.config`。

## 开发

```bash
python -m pytest -q
chatpypi build --project-dir .
chatpypi check --project-dir .
PYTHONPATH=src python -m chatdns.cli --help
```
