# ChatDNS 快速开始

本页按“安装 → 配置 profile → 只读检查 → DNS 写入 → 证书申请”的顺序组织。第一次使用时先停在只读检查；确认账号、provider 和目标域名无误后，再执行写操作。

<div class="grid cards" markdown>

- **先查看，不修改**

  ---

  从 `list`、`records`、`ip` 和 `cert check` 开始。

- **DNS 记录生命周期**

  ---

  用 `set` 写入、`records` 回读、`delete` 精确删除。

- **动态地址**

  ---

  `ddns` 默认只执行一次；确认无误后再启用 `--monitor`。

- **证书安全路径**

  ---

  staging 使用独立输出目录；生产 leaf 才进入中央证书库。

</div>

## 1. 安装与确认

推荐使用 **Python 3.12**；`requires-python >=3.10` 只表示最低兼容版本。

安装稳定版：

```bash
python -m pip install -U ChatDNS
chatdns --version
chatdns --help
```

需要 MCP 注册能力时：

```bash
python -m pip install -U 'ChatDNS[mcp]'
```

源码开发：

```bash
git clone https://github.com/ChatArch/ChatDNS.git
cd ChatDNS
python -m pip install -e '.[dev,docs]'
python -m pytest -q
mkdocs build --strict
```

## 2. 选择 provider 与 ChatEnv profile

ChatDNS 当前支持：

| Provider | CLI 值 | ChatEnv 类型 | 必需凭据 |
| --- | --- | --- | --- |
| 阿里云 DNS | `aliyun` | `aliyun` | `ALIBABA_CLOUD_ACCESS_KEY_ID`、`ALIBABA_CLOUD_ACCESS_KEY_SECRET` |
| 腾讯云 DNSPod | `tencent` | `tencent` | `TENCENT_SECRET_ID`、`TENCENT_SECRET_KEY` |

先确认 ChatDNS、Aliyun 和 Tencent 配置由哪些包注册：

```bash
chatenv status -t chatdns --detail
chatenv status -t aliyun --detail
chatenv status -t tencent --detail
```

### 创建 Tencent named profile

以下示例创建名为 `work` 的 profile。占位值必须替换为真实凭据，但不要把凭据提交到仓库、文档或日志。

```bash
chatenv new -t tencent -I --yes work
printf '%s\n' \
  'TENCENT_SECRET_ID=[REDACTED]' \
  'TENCENT_SECRET_KEY=[REDACTED]' \
  'TENCENT_REGION_ID=ap-guangzhou' \
  | chatenv paste --profile work --stdin --yes -I
chatenv cat -t tencent work
```

### 创建 Aliyun named profile

```bash
chatenv new -t aliyun -I --yes work
printf '%s\n' \
  'ALIBABA_CLOUD_ACCESS_KEY_ID=[REDACTED]' \
  'ALIBABA_CLOUD_ACCESS_KEY_SECRET=[REDACTED]' \
  'ALIBABA_CLOUD_REGION_ID=cn-hangzhou' \
  | chatenv paste --profile work --stdin --yes -I
chatenv cat -t aliyun work
```

`chatenv cat` 默认脱敏敏感字段。公共示例和日常检查不要使用 `--no-mask`。

### 设置默认 provider

不想每次传 `--provider` 时，可以初始化 ChatDNS active 配置并设置默认值：

```bash
chatenv init -t chatdns -I
chatenv set -I CHATDNS_PROVIDER=tencent
chatenv cat -t chatdns
```

命令显式 `--provider` 始终优先于 `CHATDNS_PROVIDER`。如果使用 named provider profile，继续传 `--env work`。

## 3. 先做只读检查

以 Tencent `work` profile 为例：

```bash
chatdns --env work list --provider tencent
chatdns --env work records example.com --provider tencent -I
chatdns --env work records www.example.com --type A --provider tencent -I
```

检查当前 IP：

```bash
chatdns ip --type public
chatdns ip --type local --local-ip-cidr 192.168.0.0/16
```

只读命令仍可能访问 provider API 或公网 IP 服务，但不会修改 DNS 记录。

## 4. 创建、回读和删除记录

使用文档示例保留地址 `192.0.2.10` 演示完整闭环：

```bash
chatdns --env work set host.example.com \
  --provider tencent \
  --type A \
  --value 192.0.2.10 \
  --ttl 600 \
  -I

chatdns --env work records host.example.com \
  --provider tencent \
  --type A \
  -I
```

确认目标和值都匹配后，再删除：

```bash
chatdns --env work delete host.example.com \
  --provider tencent \
  --type A \
  --value 192.0.2.10 \
  --yes \
  -I
```

安全约定：

- `set` 后必须用 `records` 回读；
- `delete` 尽量同时给出 `--type` 和 `--value`，收窄匹配范围；
- 自动化使用 `-I`，避免缺参时阻塞；
- 非交互删除必须显式 `--yes`。

## 5. DDNS：先单次，再监控

单次更新：

```bash
chatdns --env work ddns home.example.com \
  --provider tencent \
  --ip-type public \
  --ttl 600 \
  -I
```

回读记录确认后，再启动持续监控：

```bash
chatdns --env work records home.example.com --provider tencent -I
chatdns --env work ddns home.example.com \
  --provider tencent \
  --ip-type public \
  --monitor \
  --interval 120 \
  --log-file dynamic_ip_updater.log \
  -I
```

`--monitor` 是前台长运行模式。本地服务化、进程监督和重启策略不属于 ChatDNS CLI 的当前命令树。

## 6. 证书：检查、staging、生产

先查看本地是否已有匹配证书：

```bash
chatdns cert check '*.example.com' --cert-path default
```

用独立输出目录验证 staging，不污染正式中央证书库：

```bash
chatdns --env work cert apply \
  --domain '*.example.com' \
  --email admin@example.com \
  --provider tencent \
  --staging \
  --cert-dir "$HOME/.cache/chatdns/staging-certs" \
  --cert-path default \
  -I
```

确认 provider、DNS-01 和 ACME 流程后，再执行生产申请：

```bash
chatdns --env work cert apply \
  --domain '*.example.com' \
  --email admin@example.com \
  --provider tencent \
  --cert-path default \
  -I

chatdns cert check '*.example.com' --cert-path default
```

生产证书默认进入：

```text
$CHATARCH_HOME/certs/<registered-domain>/<cert-path>/
```

每个 leaf 只允许四个 PEM 文件。完整分配、复用、SAN、wildcard、symlink 和远端部署规则见[证书目录与创建规则](certificate-storage.md)。

## 7. 查看独立 Infra manifest

`cert manifest` 只读取 JSON 并渲染表格：

```bash
chatdns cert manifest ./manifest.json
```

它不会扫描中央证书库，也不会通过 SSH 部署证书。服务器 inventory、备份、路径替换、`nginx -t`、reload、SNI 回读和 rollback 属于 Infra。

## 下一步

- 查看完整命令、选项和副作用：[CLI 树](cli-tree.md)
- 理解证书目录和创建规则：[证书目录与创建规则](certificate-storage.md)
- 回到文档导航：[首页](index.md)
