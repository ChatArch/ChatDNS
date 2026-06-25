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

ChatDNS 是从 ChatTool 分离出来的 ChatArch DNS helper。它提供独立 `chatdns` CLI 和可导入 Python API，用于 DNS 记录管理、DDNS 更新、云厂商 provider client、IP 探测与 MCP 注册。

## 命令

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

当前支持：

- 阿里云 DNS
- 腾讯云 DNSPod

旧 `chattool dns cert` 证书管理面暂不放进第一版 DNS-only 分离；证书代码作为单独边界继续 review。

## 配置

ChatDNS 通过环境变量 / ChatEnv-compatible config 字段读取 provider 凭证：

- `ALIBABA_CLOUD_ACCESS_KEY_ID`
- `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
- `ALIBABA_CLOUD_REGION_ID`
- `TENCENT_SECRET_ID`
- `TENCENT_SECRET_KEY`
- `TENCENT_REGION_ID`

包通过 `chatenv.configs` entry point 注册 `chatdns.config`。

## 开发

```bash
python -m pytest -q
chatpypi build --project-dir .
chatpypi check --project-dir .
PYTHONPATH=src python -m chatdns.cli --help
```
