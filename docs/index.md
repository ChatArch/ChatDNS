# ChatDNS

ChatDNS 是 ChatArch 的 DNS、DDNS 与 ACME DNS-01 证书工具。它把 Aliyun DNS、Tencent Cloud / DNSPod、ChatEnv profile、证书检查和中央证书目录组织为一套可审计的命令面。

## 按场景选择

| 场景 | 文档 | 建议起点 |
| --- | --- | --- |
| 第一次安装和配置 | [快速开始](quickstart.md) | 先执行只读检查 |
| 查命令和参数 | [CLI 树](cli-tree.md) | 先看副作用矩阵 |
| 申请或检查证书 | [证书目录与创建规则](certificate-storage.md) | staging 使用独立目录 |
| 接入 Python / MCP | [CLI 树](cli-tree.md) | 查看接口边界 |

<div class="grid cards" markdown>

- **快速开始**

  ---

  安装、ChatEnv profile、只读验证、DNS 写入和证书安全流程。

  [开始使用](quickstart.md)

- **CLI 树**

  ---

  真实命令拓扑、参数入口、profile 规则和副作用分级。

  [查看命令](cli-tree.md)

- **证书契约**

  ---

  registered domain、cert-path、SAN 复用、symlink 拒绝和 Infra 边界。

  [查看规则](certificate-storage.md)

</div>

## 推荐环境

推荐 **Python 3.12**；`requires-python >=3.10` 仅表示最低兼容版本。

```bash
uv venv --python 3.12
uv pip install ChatDNS
chatdns --help
```

## 副作用速查

| 类型 | 命令 |
| --- | --- |
| provider / 本地只读 | `list`、`records`、`ip`、`cert check`、`cert manifest` |
| DNS 写入 | `set`、`delete`、`ddns` |
| DNS + 本地证书写入 | `cert apply` |

第一次使用时先停在只读命令。ChatDNS 不负责 SSH 分发、Nginx rewrite/reload 或服务器 rollback；这些属于 Infra。

## 支持的 provider

- Aliyun DNS
- Tencent Cloud / DNSPod

账号通过 ChatEnv profile 隔离；使用 `chatdns --env PROFILE ...` 选择目标配置。
