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
| 直接查看所有公开命令 | `chatdns --help` |

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
├── cert
│   ├── apply       # DNS-01 申请并安装证书；写 DNS 与本地证书
│   ├── check       # 只读检查本地证书状态
│   └── manifest    # 只读渲染 Infra manifest
├── ddns            # 单次或持续更新 A 记录
├── delete          # 删除记录
├── ip              # 查询 public/local IP
├── list            # 列出 managed zones
├── records         # 查询记录
└── set             # 幂等设置记录
```

完整参数、profile 位置规则、交互选项和副作用矩阵见 [CLI 树](docs/cli-tree.md)。

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
| `cert check`、`cert manifest` | 本地只读 |
| `set`、`delete`、`ddns` | 写 DNS provider |
| `cert apply` | 写 DNS challenge 与本地证书 |

ChatDNS 负责 DNS、证书申请/检查和 manifest 解析；SSH 分发、Nginx rewrite/reload 与服务器 rollback 属于 Infra，不在 ChatDNS 中执行。

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
