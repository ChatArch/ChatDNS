# ChatDNS 文档

ChatDNS 是从 ChatTool 分离出的独立 DNS helper，当前第一版聚焦 DNS-only 能力：

- 域名列表：`chatdns list`
- 记录查询：`chatdns records`
- 幂等设置：`chatdns set`
- 安全删除：`chatdns delete`
- IP 探测：`chatdns ip`
- DDNS：`chatdns ddns`
- MCP 工具注册：`chatdns.mcp.register`

`chattool dns cert` 证书管理面暂不并入第一版，后续单独 review 是否进入 ChatDNS 或拆成独立证书包。
