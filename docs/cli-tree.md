# ChatDNS CLI 树

这是一份以当前 `chatdns --help`、各级子命令 help、源码和测试为准的命令地图。它回答两个问题：命令如何调用，以及调用后是否会产生外部副作用。

需要先完成 provider profile 配置时，从[快速开始](quickstart.md)进入；证书文件布局和远端部署边界见[证书目录与创建规则](certificate-storage.md)。

## 顶层命令

```text
chatdns
├── cert                # DNS-01 证书申请、检查和 Infra manifest 展示
│   ├── apply           # 申请或续期证书；写 DNS TXT 和本地证书文件
│   ├── check           # 检查本地证书到期时间和续期状态
│   └── manifest        # 只读展示独立 Infra manifest
├── ddns                # 单次更新或持续监控动态 IP；可能写 DNS 记录
├── delete              # 按域名、主机记录、类型和值筛选并删除 DNS 记录
├── ip                  # 只探测公网或本地 IP，不修改 DNS
├── list                # 列出 provider 账号中的托管域
├── records             # 查询域名或完整主机名的 DNS 记录
└── set                 # 幂等创建或更新 DNS 记录
```

顶层公共选项：

| 选项 | 作用 |
| --- | --- |
| `--version` | 输出 ChatDNS 版本 |
| `-e, --env PROFILE` | 在命令前选择 provider 的 named ChatEnv profile |
| `--chatarch-home DIR` | 为本次命令覆盖读取 ChatEnv profile 时使用的 `CHATARCH_HOME` |
| `--help` | 输出顶层帮助 |

## 副作用分级

| 分级 | 命令 | 边界 |
| --- | --- | --- |
| 只读 | `list`、`records` | 调用 provider 查询 API，不写 DNS |
| 只读 | `ip` | 公网模式访问 IP 探测服务；本地模式只扫描本机网卡 |
| 只读 | `cert check` | 读取本地证书并计算续期状态，不执行 ACME |
| 只读 | `cert manifest` | 读取指定 JSON manifest 并渲染表格，不修改原文件 |
| 写 DNS | `set`、`delete`、`ddns` | 创建、更新或删除 provider 记录 |
| 写 DNS 与证书 | `cert apply` | 写 `_acme-challenge` TXT，执行 ACME，并安装本地 PEM |

“只读”只表示不修改 DNS/证书状态，不表示完全离线：`list`、`records` 和公网 `ip` 仍会访问网络。

## 域名与记录查询

```text
chatdns list
├── --provider aliyun|tencent    # 显式 provider；否则读 CHATDNS_PROVIDER
├── --page INTEGER               # 默认 1
├── --page-size INTEGER          # 默认 20
└── --env PROFILE                # 命令级 named provider profile

chatdns records [TARGET]
├── --domain DOMAIN              # 与 --rr 组合的替代输入
├── --rr RR                      # 可选主机记录过滤
├── --type TYPE                  # 可选记录类型过滤
├── --provider aliyun|tencent
├── --env PROFILE
└── -i | -I                      # 强制交互或禁用交互

chatdns ip
├── --type public|local          # 默认 public
└── --local-ip-cidr CIDR         # 只在 local 模式过滤候选网卡地址
```

`records` 的 `TARGET` 可以是托管域 `example.com`，也可以是完整主机名 `www.example.com`。如果同时给出位置参数和 `--domain/--rr`，位置参数优先，CLI 会输出忽略提示。

`list` 默认只请求第一页（`--page 1 --page-size 20`）。做完整 zone 盘点时，显式提高 `--page-size`（Aliyun/Tencent 常用 100）并按 `--page` 继续分页，直到返回不足一页或 provider 计数核对完成。

常用只读命令：

```bash
chatdns --env work list --provider tencent
chatdns --env work records example.com --provider tencent -I
chatdns --env work records www.example.com --type A --provider tencent -I
chatdns ip --type local --local-ip-cidr 192.168.0.0/16
```

## DNS 写入与 DDNS

```text
chatdns set [FULL_DOMAIN]
├── --domain DOMAIN + --rr RR    # FULL_DOMAIN 的替代输入
├── --type TYPE                  # 默认 A
├── --value VALUE                # 必填，可由交互补齐
├── --ttl INTEGER                # 默认 600
├── --provider aliyun|tencent
├── --env PROFILE
└── -i | -I

chatdns delete [FULL_DOMAIN]
├── --domain DOMAIN + --rr RR
├── --type TYPE                  # 必填，可由交互补齐
├── --value VALUE                # 可选，进一步收窄匹配记录
├── --yes                        # 非交互删除必须显式确认
├── --provider aliyun|tencent
├── --env PROFILE
└── -i | -I

chatdns ddns [FULL_DOMAIN]
├── --domain DOMAIN + --rr RR
├── --ttl INTEGER                # 默认 600
├── --ip-type public|local       # 默认 public
├── --local-ip-cidr CIDR
├── --monitor                    # 不传时只执行一次
├── --interval SECONDS           # 监控间隔，默认 120
├── --max-retries INTEGER        # 默认 3
├── --retry-delay SECONDS        # 默认 5
├── --log-file PATH
├── --log-level LEVEL            # 默认 INFO
├── --provider aliyun|tencent
├── --env PROFILE
└── -i | -I
```

`set` 调用 provider 的幂等设置路径；执行后仍应使用 `records` 回读。`delete` 会先列出匹配记录；非交互环境必须传 `--yes`，否则失败关闭。`ddns` 默认只运行一次，只有显式 `--monitor` 才持续轮询。

```bash
chatdns --env work set host.example.com -p tencent -t A -v 192.0.2.10 -I
chatdns --env work records host.example.com -p tencent -t A -I
chatdns --env work delete host.example.com -p tencent -t A -v 192.0.2.10 --yes -I

chatdns --env work ddns host.example.com -p tencent -I
chatdns --env work ddns host.example.com -p tencent --monitor --interval 120 -I
```

## 证书命令

```text
chatdns cert apply
├── --domain DOMAIN              # 可重复；支持 SAN / wildcard
├── --email EMAIL                # Let's Encrypt 账号邮箱；短选项为 -e
├── --provider aliyun|tencent
├── --env PROFILE                # 此处只提供长选项，避免与 -e 邮箱冲突
├── --cert-dir DIR               # 显式证书根目录
├── --cert-path NAME             # 注册域名下的安全单段目录名
├── --staging                    # 使用 Let's Encrypt staging
├── --force                      # 忽略本地仍有效状态，强制申请/续期
├── --log-file PATH
├── --log-level LEVEL            # 默认 INFO
└── -i | -I

chatdns cert check [DOMAINS]...
├── --cert-dir DIR
├── --cert-path NAME
└── --provider aliyun|tencent

chatdns cert manifest [MANIFEST_PATH]
└── MANIFEST_PATH                # 默认 ./manifest.json，只读
```

证书根目录优先级为：显式 `--cert-dir`，其次是 ChatEnv `CHATDNS_CERT_DIR`，最后是 `$CHATARCH_HOME/certs`。正式 leaf 位于：

```text
<certificate-root>/<registered-domain>/<cert-path>/
```

省略 `--cert-path` 时从 `default` 开始；冲突时选择 `default-2`、`default-3`，完整规范化 SAN 集相同则复用已有 leaf。每个 leaf 只允许 `cert.pem`、`chain.pem`、`fullchain.pem` 和 `privkey.pem`。

`cert apply` 是高副作用命令。先用单独的 staging 输出目录验证 provider、DNS-01 和 ACME，再执行生产申请；不要让 Nginx 或其他服务引用 staging 证书。

```bash
chatdns --env work cert apply \
  -d '*.example.com' \
  -e admin@example.com \
  -p tencent \
  --staging \
  --cert-dir "$HOME/.cache/chatdns/staging-certs" \
  --cert-path default \
  -I

chatdns --env work cert apply \
  -d '*.example.com' \
  -e admin@example.com \
  -p tencent \
  --cert-path default \
  -I

chatdns cert check '*.example.com' --cert-path default
```

`cert manifest` 不扫描证书根，也不部署证书；它只把独立 Infra manifest 渲染为表格。SSH 同步、Nginx 路径更新、`nginx -t`、reload 和 rollback 属于 Infra，而不是 ChatDNS。

## Profile 与交互规则

Provider 选择顺序：

1. 命令显式 `--provider`；
2. ChatEnv `CHATDNS_PROVIDER`；
3. 默认 `aliyun`。

Provider 凭据来自对应的 Aliyun 或 Tencent named/active ChatEnv profile。可在顶层选择 profile：

```bash
chatdns --env work list -p tencent
```

`list`、`ddns`、`set`、`records` 和 `delete` 也接受命令级 `--env/-e`，且命令级值覆盖顶层值。`cert apply` 的 `-e` 是邮箱，因此 named profile 必须写成长选项 `--env`，或放在 `cert` 前面的顶层位置。

带 `-i/-I` 的命令遵循 ChatStyle 交互契约：`-i` 强制在可用终端补问缺失参数，`-I` 禁止交互并快速失败。自动化建议显式传全参数和 `-I`。

## Python API 与 MCP 边界

CLI 不是唯一接口。包根导出的主要 Python API 包括：

```text
chatdns
├── DNSClient
├── AliyunDNSClient
├── TencentDNSClient
├── DynamicIPUpdater
├── SSLCertUpdater
├── DNSClientType
├── create_dns_client
└── split_full_domain
```

安装 `ChatDNS[mcp]` 后，`chatdns.mcp.register(mcp)` 注册以下工具：

| MCP 工具 | 类型 |
| --- | --- |
| `dns_list_domains` | 读 |
| `dns_get_records` | 读 |
| `dns_add_record` | 写 |
| `dns_delete_record` | 写 |
| `dns_ddns_update` | 写 |

MCP 工具不属于 `chatdns` CLI 子树。CLI 中刻意隐藏的 Certbot hook 也是内部兼容面，不作为稳定用户命令记录在本树中。

## 文档更新契约

- 只有已出现在实际 Click help 中的公共命令才能进入本树。
- 新命令必须同步更新中英文页面、顶层副作用表和相关快速开始。
- 隐藏命令、规划能力和远端 Infra 流程不能伪装为稳定 CLI。
- 命令选项以 `chatdns <path> --help` 和测试为最终依据。
