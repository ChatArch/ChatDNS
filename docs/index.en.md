# ChatDNS Docs

ChatDNS is the standalone DNS helper extracted from ChatTool. The first extraction release focuses on DNS-only capabilities:

- Domain listing: `chatdns list`
- Record lookup: `chatdns records`
- Idempotent record setting: `chatdns set`
- Confirmed deletion: `chatdns delete`
- IP detection: `chatdns ip`
- DDNS updates: `chatdns ddns`
- MCP registration: `chatdns.mcp.register`

The previous `chattool dns cert` certificate surface is intentionally outside the first DNS-only extraction and should be reviewed separately before moving certificate code.
