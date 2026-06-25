# ChatDNS Docs

ChatDNS is the standalone DNS helper extracted from ChatTool. It now provides:

- Domain listing: `chatdns list`
- Record lookup: `chatdns records`
- Idempotent record setting: `chatdns set`
- Confirmed deletion: `chatdns delete`
- IP detection: `chatdns ip`
- DDNS updates: `chatdns ddns`
- DNS-01 certificate apply/check: `chatdns cert apply` / `chatdns cert check`
- MCP registration: `chatdns.mcp.register`

`chatdns cert` carries the old `chattool dns cert` boundary into ChatDNS. It uses ACME DNS-01 validation and writes `_acme-challenge` TXT records through the configured DNS provider. Certificate issuance and DNS writes are external side effects; test with `--staging` before production issuance.
