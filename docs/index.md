# ChatDNS 文档

ChatDNS 是从 ChatTool 分离出的独立 DNS helper，当前提供：

- 域名列表：`chatdns list`
- 记录查询：`chatdns records`
- 幂等设置：`chatdns set`
- 安全删除：`chatdns delete`
- IP 探测：`chatdns ip`
- DDNS：`chatdns ddns`
- DNS-01 证书申请/检查：`chatdns cert apply` / `chatdns cert check`
- MCP 工具注册：`chatdns.mcp.register`

`chatdns cert` 由旧 `chattool dns cert` 边界迁入，用 ACME DNS-01 验证并通过配置的 DNS provider 写入 `_acme-challenge` TXT 记录。证书申请和 DNS 写入是外部副作用；生产申请前建议先使用 `--staging` 验证。

证书根目录解析、首次创建结构、文件权限、泛域/SAN 分组、中央证书库和远端 Infra 约定见[证书目录与创建规则](certificate-storage.md)。
