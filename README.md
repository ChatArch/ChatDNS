# ChatDNS

[简体中文](README.md) · [English](README.en.md)

ChatDNS 是 ChatArch 的 DNS、DDNS 与 ACME DNS-01 证书工具。它统一 Aliyun DNS 与 Tencent Cloud / DNSPod provider，通过 ChatEnv profile 选择账号，并将证书安全写入 `$CHATARCH_HOME/certs/<registered-domain>/<cert-path>/`。

- 文档：<https://arch.gh.wzhecnu.cn/ChatDNS/>
- 快速开始：<https://arch.gh.wzhecnu.cn/ChatDNS/quickstart/>
- CLI 树：<https://arch.gh.wzhecnu.cn/ChatDNS/cli-tree/>
- 证书规则：<https://arch.gh.wzhecnu.cn/ChatDNS/certificate-storage/>

## 按场景进入

| 目标 | 入口 |
| --- | --- |
| 第一次安装并安全验证 profile | [快速开始](docs/quickstart.md) |
| 查找命令、参数和副作用 | [CLI 树](docs/cli-tree.md) |
| 理解证书目录、SAN 复用和 symlink 拒绝规则 | [证书目录与创建规则](docs/certificate-storage.md) |
| 直接查看所有公开命令 | `chatdns --tree` / `chatdns --help` |

## 安装

推荐使用 **Python 3.12**；包元数据中的 `>=3.10` 只表示最低兼容版本，不会把环境固定到 Python 3.10。

```bash
uv venv --python 3.12
uv pip install ChatDNS
chatdns --version
```

开发安装：

```bash
uv pip install -e '.[dev,docs]'
```

## 安全起步

先选择 ChatEnv profile 和 provider，再从只读命令开始：

```bash
chatdns --env work list --provider tencent
chatdns --env work records example.com --provider tencent
chatdns ip --type public
chatdns --env work cert check '*.example.com' --cert-path default
```

确认账号、zone 与记录无误后，再执行 `set`、`delete`、`ddns` 或 `cert apply`。

## CLI 树

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

完整参数、profile 位置规则、交互选项和副作用矩阵见 [CLI 树](docs/cli-tree.md)。

证书状态入口是 `chatdns cert status`。`chatdns cert manifest init` 会从当前证书根创建/更新 Infra 工作区里的 `manifest.json`，并创建 `scripts/README.md` 作为模型/人工手写同步脚本的说明入口；ChatDNS 不提供 `cert script` 生成或执行接口。

## 配置解析

Provider 选择顺序：

1. 命令行 `--provider`；
2. ChatDNS profile 的 `CHATDNS_PROVIDER`；
3. 默认 `aliyun`。

Profile 使用全局 `chatdns --env PROFILE ...` 选择；DNS 命令也支持命令级 `--env`。Aliyun 与 Tencent 凭据由同名 ChatEnv profile 读取，敏感值不写入仓库。

## 能力与边界

| 操作 | 副作用 |
| --- | --- |
| `list`、`records` | provider 只读 API |
| `ip` | 本机接口读取或公网 IP 查询 |
| `cert check`、`cert status`、`cert manifest show`、`cert manifest validate` | 本地只读 |
| `cert manifest init` | 只写本地 Infra `manifest.json` 与 `scripts/README.md` |
| `set`、`delete`、`ddns` | 写 DNS provider |
| `cert apply` | 写 DNS challenge 与本地证书 |

ChatDNS 负责 DNS、证书申请/检查、证书根状态扫描和 manifest 创建/解析；SSH 分发、Nginx rewrite/reload 与服务器 rollback 属于 Infra，不在 ChatDNS 中执行，也不生成同步脚本。

## Python API 与 MCP

```python
from chatdns import create_dns_client, DynamicIPUpdater, SSLCertUpdater
```

MCP 暴露 DNS 查询/设置、IP 查询、DDNS 与证书申请工具；MCP 工具不属于 CLI 子命令。完整映射见 [CLI 树](docs/cli-tree.md)。

## 验证

```bash
pytest -q
mkdocs build --strict
```

## License

MIT
