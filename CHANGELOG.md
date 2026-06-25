# Changelog

## 0.1.0 - Unreleased

- Extract DNS record management and DDNS helpers from ChatTool into standalone ChatDNS.
- Add `chatdns` CLI with `list`, `records`, `set`, `delete`, `ip`, and `ddns` commands.
- Add importable provider/client APIs for Aliyun DNS and Tencent Cloud DNSPod.
- Add `chatenv.configs` provider registration for ChatDNS provider credentials.
- Add DNS-only MCP registration helpers.
- Keep certificate management (`chattool dns cert`) out of the first extraction boundary pending separate review.
