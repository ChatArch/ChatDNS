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

## 两层证书目录

ChatDNS 固定使用：

```text
$CHATARCH_HOME/certs/<注册域名>/<cert-path>/
```

这里的“注册域名”是 provider 中与请求名称最长匹配的托管 zone。申请根泛域证书时：

```bash
chatdns cert apply \
  -d '*.example.com' \
  -e admin@example.com \
  --provider aliyun
```

未指定 `--cert-path`，默认结果为：

```text
$CHATARCH_HOME/certs/
├── README.md                 # 可选；证书根唯一的说明文件
└── example.com/
    └── default/
        ├── cert.pem
        ├── chain.pem
        ├── fullchain.pem
        └── privkey.pem
```

申请更深一层的泛域证书时，建议显式使用 URI 对应名称：

```bash
chatdns cert apply \
  -d '*.precision.example.com' \
  -e admin@example.com \
  --provider aliyun \
  --cert-path precision
```

结果是 `$CHATARCH_HOME/certs/example.com/precision/`。`--cert-path` 必须是一个安全目录段，不能是绝对路径，不能包含 `/`、`\`、`.`、`..` 或路径穿越。ChatDNS 可以显示从泛域名推导的建议，但不会静默替换显式名称或默认行为。

## 默认名、冲突和续期复用

- 未指定 `--cert-path` 时先选择 `default`。
- 如果该目录已属于不同 SAN 集，依次选择 `default-2`、`default-3`。
- 显式名称冲突时同样使用 `<name>-2`、`<name>-3`。
- 可能与自动编号重叠的显式名称属于同一个锁定范围，例如 `foo` 和 `foo-2` 不会并发分配同一目录。
- 如果两层目录中已经存在完全相同的标准化 SAN 集，续期复用原目录，不产生新编号。
- `chatdns cert check` 可用 `--cert-path` 精确限定名称；未限定时会在两层目录中查找覆盖请求域名的证书。

一个泛域只覆盖一层：`*.example.com` 覆盖 `nas.example.com`，不覆盖 `foo.precision.example.com`；后一类名称需要 `*.precision.example.com`。

## 文件职责、权限和 ACME 私有状态

每个末级证书目录只允许四个 PEM：

| 文件/目录 | 用途 | 权限 |
|---|---|---:|
| 证书根目录 | 注册域名目录和可选 `README.md` | `0700` |
| 证书末级目录 | 一张证书的四个部署文件 | `0700` |
| `privkey.pem` | 证书私钥 | `0600` |
| `cert.pem` | 叶子证书 | `0644` |
| `chain.pem` | 中间证书链 | `0644` |
| `fullchain.pem` | 叶子证书加中间链 | `0644` |

ACME account key、签发临时目录和临时 key 不进入 `certs/`。默认私有状态目录为：

```text
$CHATARCH_HOME/private/chatdns/acme/
```

新证书私钥先在内存中生成；签发返回后，ChatDNS 在私有状态目录中完成拆链和证书/私钥匹配验证，再把四个 PEM 写入目标目录。不要把证书根或 ACME 私有状态提交到 Git，也不要输出私钥内容。

## SAN 分组和续期判断

同一 provider 托管 zone 的输入名称作为一张 SAN 证书处理。一次目录解析只接受同一个托管 zone；CLI 收到多个 zone 时会先分组，再分别预览和签发。续期时：

1. 定位完整 SAN 集对应的现有两层目录；
2. 检查证书是否存在及是否在 30 天内到期；
3. 检查 SAN 是否覆盖全部请求名称；
4. 仅在缺失、临期、SAN 不完整或显式 `--force` 时申请。

## Infra manifest 可视化

`manifest.json` 和模型按现场情况编写的 `scripts/` 属于独立 Infra 工作区，不属于证书根。ChatDNS 只读展示 manifest，不会创建或改写它：

```bash
cd Infra
chatdns cert manifest
chatdns cert manifest ./manifest.json
```

空文件、空对象和空 `certificates` 容器都会显示为空表。当前命令兼容 `certificate_groups`、`certificates` 和 `groups` 三种顶层集合，并显示 ID、注册域名、证书路径、SAN、部署数量与状态。

## 远端 Infra 路径

远端保持同一相对路径：

```text
<remote-home>/.chatarch/certs/<注册域名>/<cert-path>/
```

Nginx 指向其中的 `fullchain.pem` 和 `privkey.pem`。具体同步/更新脚本由模型根据实际服务器手写，不固化进 ChatDNS。远端变更必须先备份证书和配置，完成原子安装、配置测试、reload、失败回滚，并按 SNI 回读线上证书。

## 安全检查

生产申请前建议先运行 `--staging`。正式申请后至少验证：

- 目标路径严格是两层目录；
- 托管域目录不是 symlink，证书 leaf 也不会通过 symlink 解析；
- 末级目录只有四个 PEM；
- SAN 完整覆盖预期域名；
- `cert.pem` 与 `privkey.pem` 公钥匹配；
- `_acme-challenge` 临时 TXT 已清理；
- 私钥权限为 `0600`；
- 远端 `nginx -t` 和线上 SNI 证书回读均通过。
