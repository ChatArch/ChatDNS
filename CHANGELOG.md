# Changelog

## Unreleased

- Document the planned certificate-operations CLI contract for internal certificate `status`, manifest creation, and sync-script generation.

## 0.1.7 - 2026-08-05

- Correct README CLI-tree descriptions for the current A-only DDNS updater and public/local IP detection.
- Clarify `chatdns list` pagination expectations for complete zone inventory audits.
- Add CLI help smoke coverage for `chatdns cert manifest --help`.

## 0.1.6 - 2026-08-04

- Serialize explicit certificate paths that overlap generated numeric suffix families, such as `foo` and `foo-2`.
- Reject managed-zone symlinks and skip symlinked certificate leaves, including links whose targets remain inside the certificate root.
- Reject one-path resolution across multiple managed zones and preview each CLI issuance group independently.

## 0.1.5 - 2026-08-04

- Store every certificate at `<registered-domain>/<cert-path>/` below the configured certificate root.
- Add `--cert-path` to `chatdns cert apply` and `chatdns cert check`; default to `default`, suffix collisions, and reuse exact SAN sets.
- Keep ACME account and issuance state outside `certs/` under ChatArch private storage.
- Stage and verify certificate/key output before writing the four deployment PEM files.
- Reject ACME responses whose normalized SAN set differs from the requested domains.
- Add the read-only `chatdns cert manifest` table for separate Infra manifests, including empty manifests and legacy `certificate_groups` data.
- Document the strict two-level tree, one-level wildcard coverage, and model-authored remote Infra boundary.
- Build the existing bilingual documentation through the standard `/ChatDNS/` and `/ChatDNS/en/` language paths.

## 0.1.4 - 2026-08-04

- Add the ChatEnv-managed `CHATDNS_CERT_DIR` certificate-directory setting.
- Default certificate storage to `$CHATARCH_HOME/certs` instead of a relative `certs/` directory.
- Keep explicit `--cert-dir` / Python `cert_dir` values as the highest-priority override.
- Apply the same directory resolution to `chatdns cert apply`, `chatdns cert check`, and `SSLCertUpdater`.
- Expand `$CHATARCH_HOME` in configured paths against the effective `--chatarch-home` value.
- Check one primary certificate per multi-SAN group and renew when SAN coverage is incomplete.
- Document generated files, permissions, managed-zone layout, and the remote infrastructure boundary.

## 0.1.3 - 2026-07-07

- Add command-level `--env/-e PROFILE` support for DNS provider commands such as `chatdns list -p tencent -e work`.
- Keep global `chatdns --env/-e PROFILE ...` support and let command-level env selection override it.
- Add `chatdns cert apply --env PROFILE`; `-e` remains reserved for Let's Encrypt email on certificate commands.

## 0.1.2 - 2026-07-06

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
