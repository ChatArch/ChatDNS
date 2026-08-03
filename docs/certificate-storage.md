# 证书目录与创建规则

ChatDNS 使用 DNS-01 申请证书，并将证书和私钥写入一个明确的证书根目录。本页说明目录如何选择、首次申请会创建哪些文件、泛域/SAN 证书如何分组，以及 ChatArch 中央证书库与远端 Infra 如何使用同一套相对路径。

## 目录选择优先级

证书根目录按以下顺序解析，前者覆盖后者：

1. CLI `--cert-dir` 或 Python `SSLCertUpdater(cert_dir=...)`；
2. ChatEnv 的 `CHATDNS_CERT_DIR`；
3. `$CHATARCH_HOME/certs`。

`CHATARCH_HOME` 本身按以下顺序确定：

1. CLI `--chatarch-home` 或 Python `chatarch_home=`；
2. 环境变量 `CHATARCH_HOME`；
3. `~/.chatarch`。

如果 `CHATDNS_CERT_DIR` 中引用 `$CHATARCH_HOME`，ChatDNS 使用本次命令的有效 ChatArch home 展开它，而不是进程环境中可能残留的其他 home。

## 用 ChatEnv 管理

`CHATDNS_CERT_DIR` 是非敏感目录变量，可写入 active 或 named ChatDNS profile：

```bash
chatenv init -t chatdns -I
chatenv set 'CHATDNS_CERT_DIR=$CHATARCH_HOME/certs' -I
chatenv cat -t ChatDNS
```

把当前值保存为 named profile：

```bash
chatenv save -t ChatDNS work -I
chatdns --chatarch-home /srv/chatarch --env work cert check example.com
```

显式参数始终最高优先级：

```bash
chatdns cert check example.com --cert-dir /tmp/cert-audit
```

## ChatDNS 自动创建结构

假设有效证书根目录为 `$CHATARCH_HOME/certs`，申请：

```bash
chatdns cert apply \
  -d example.com \
  -d '*.example.com' \
  -e admin@example.com \
  --provider aliyun
```

成功后结构为：

```text
$CHATARCH_HOME/certs/
├── account.key
├── example.com.key
└── example.com/
    ├── cert.pem
    ├── chain.pem
    ├── fullchain.pem
    └── privkey.pem
```

规则如下：

- `account.key`：该证书根目录使用的 ACME account key；首次需要时生成。
- `<证书主域>.key`：持久化的证书私钥；证书主域是同一 DNS 托管 zone 组中的第一个请求域名。
- `<证书主域>/`：成功取得证书后创建的输出目录。
- 通配符用于文件名时，`*` 会转换为 `_`，避免形成非法或危险路径。
- ACME 在签发前失败时，account/domain key 可能已经创建，但证书输出目录可能尚不存在。

## 文件职责与权限

| 文件/目录 | 用途 | 权限 |
|---|---|---:|
| 证书根目录 | 保存 account key、domain key 与证书组 | `0700` |
| 证书组目录 | 保存一张 SAN 证书的部署文件 | `0700` |
| `account.key` | ACME 账户私钥 | `0600` |
| `<证书主域>.key` | 持久化证书私钥 | `0600` |
| `privkey.pem` | 部署给 Nginx 的私钥 | `0600` |
| `cert.pem` | 叶子证书 | `0644` |
| `chain.pem` | 中间证书链 | `0644` |
| `fullchain.pem` | 叶子证书加中间链，供 Nginx 使用 | `0644` |

不要把证书根目录提交到 Git，也不要在日志、报告或聊天中输出任何私钥内容。

## 泛域与多 SAN 分组

ChatDNS 先通过 provider 识别 DNS 托管 zone，再把同一 zone 的输入域名作为一张 SAN 证书处理。列表中的第一个域名决定证书目录和持久化 key 名称，因此建议把非通配主域放在第一位：

```bash
-d example.com -d '*.example.com'
```

续期判断以这张主证书为单位：

1. 检查主证书是否存在及是否接近到期；
2. 检查证书 SAN 是否完整覆盖本组所有请求域名；
3. 只有缺失、临期或 SAN 不完整时才续期。

这避免了把 `*.example.com` 误当成另一份本地证书并重复申请。

## ChatArch 中央证书库

多 zone 中央管理采用两层确定性路径：

```text
$CHATARCH_HOME/certs/<DNS 托管主域>/<证书主域>/
```

中央 runner 把 zone 目录显式传给 ChatDNS：

```bash
chatdns cert apply \
  --cert-dir "$CHATARCH_HOME/certs/example.com" \
  -d example.com \
  -d '*.example.com' \
  -e admin@example.com
```

ChatDNS 再按证书主域生成最后一层，结果为：

```text
$CHATARCH_HOME/certs/example.com/example.com/
```

manifest 中必须满足：

```text
managed_zone = example.com
primary_domain = example.com
local_dir = example.com/example.com
```

这种分层让 provider/profile、ACME account、日志、续期和部署都能按 DNS 托管主域审计。

## 远端 Infra 路径

ChatArch Infra 使用相同的相对路径，远端目标为：

```text
<remote-home>/.chatarch/certs/<DNS 托管主域>/<证书主域>/
```

Nginx 指向其中的 `fullchain.pem` 和 `privkey.pem`。远端迁移必须由 Infra 同步层完成，并遵循：备份旧证书和 Nginx 配置、原子写入、`nginx -t`、reload、失败回滚，以及最终按 SNI 回读线上证书。ChatDNS CLI 本身只负责申请和本地落盘，不会自动修改远端 Nginx。

## 安全检查

生产申请前建议先运行 `--staging`。正式申请后至少验证：

- SAN 完整覆盖预期域名；
- `cert.pem` 与 `privkey.pem` 公钥匹配；
- `_acme-challenge` 临时 TXT 已清理；
- 私钥权限为 `0600`；
- 远端 `nginx -t` 和线上 SNI 证书回读均通过。
