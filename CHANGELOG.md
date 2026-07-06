# Changelog

## Unreleased

- Load ChatDNS ChatEnv active profiles automatically for CLI/API DNS client creation.
- Add `CHATDNS_PROVIDER` as the ChatEnv default provider/channel setting.
- Add global `chatdns --env/-e PROFILE` support for selecting named provider profiles.
- Raise the ChatEnv dependency floor to `chatenv>=0.2.2,<0.3.0`.

## 0.1.1 - 2026-06-26

- Move the old `chattool dns cert` / DNS-01 certificate boundary into ChatDNS as `chatdns cert`.
- Add `SSLCertUpdater` importable API with ACME DNS-01 helpers.
- Add `chatdns cert apply` and `chatdns cert check` CLI commands.
- Add hidden `chatdns cert hook-auth` / `hook-cleanup` commands for certbot manual DNS-01 hook compatibility.
- Add runtime dependencies required by certificate issuance: `requests` and `cryptography`.
- Fix wildcard DNS-01 challenge record handling so `*.example.com` writes `_acme-challenge.example.com`.

## 0.1.0 - 2026-06-25

- Extract DNS record management and DDNS helpers from ChatTool into standalone ChatDNS.
- Add `chatdns` CLI with `list`, `records`, `set`, `delete`, `ip`, and `ddns` commands.
- Add importable provider/client APIs for Aliyun DNS and Tencent Cloud DNSPod.
- Add `chatenv.configs` provider registration for ChatDNS provider credentials.
- Add DNS-only MCP registration helpers.
- Keep certificate management (`chattool dns cert`) out of the first extraction boundary pending separate review.
