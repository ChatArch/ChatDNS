#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
动态IP监控和DNS自动更新 CLI
"""

import os
import click
import asyncio

from chatstyle import (
    ask_confirm,
    ask_select,
    CommandConstraint,
    CommandField,
    CommandSchema,
    add_interactive_option,
    is_interactive_available,
    resolve_command_inputs,
)
from .logging_utils import setup_logger
from . import __version__, DynamicIPUpdater, create_dns_client
from .domain_utils import split_full_domain


# CLI 接口
@click.group(invoke_without_command=True)
@click.version_option(__version__, prog_name="ChatDNS")
@click.pass_context
def cli(ctx):
    """DNS helpers for record management, DDNS, and IP detection."""
    if ctx.invoked_subcommand is not None:
        return
    if not is_interactive_available():
        click.echo(ctx.get_help())
        return

    selected = ask_select(
        "选择 DNS 命令",
        choices=[
            "list - 查看域名列表",
            "ddns - 动态更新 DNS 记录",
            "set - 创建或更新 DNS 记录",
            "records - 查询 DNS 记录",
            "delete - 删除 DNS 记录",
            "ip - 查看当前 IP",
            "cert - 证书管理",
        ],
    )
    ctx.invoke(cli.get_command(ctx, selected.split(" - ", 1)[0]))


def _resolve_domain_inputs(full_domain, domain, rr):
    if full_domain:
        if domain or rr:
            click.echo(
                "警告: 当提供 full_domain 时，--domain 和 --rr 参数将被忽略。", err=True
            )

        try:
            return split_full_domain(full_domain)
        except ValueError as exc:
            raise click.ClickException(
                "无效的完整域名格式。应如 'sub.example.com'"
            ) from exc

    return domain, rr


def _resolve_records_inputs(target, domain, rr):
    if target:
        if domain or rr:
            click.echo(
                "警告: 当提供 target 时，--domain 和 --rr 参数将被忽略。", err=True
            )

        parts = target.split(".")
        if len(parts) == 2:
            return target, None
        try:
            return split_full_domain(target)
        except ValueError as exc:
            raise click.ClickException(
                "无效的域名格式。应如 'example.com' 或 'sub.example.com'"
            ) from exc

    return domain, rr


def _validate_dns_domain_pair(values):
    if values.get("domain") and values.get("rr"):
        return None
    return "必须提供 full_domain 位置参数，或者同时提供 --domain 和 --rr 选项。"


def _validate_dns_domain_only(values):
    if values.get("domain"):
        return None
    return "必须提供域名。"


DNS_PAIR_SCHEMA = CommandSchema(
    name="dns-domain-pair",
    fields=(
        CommandField(
            "domain",
            prompt="domain",
            required=True,
            missing_message="必须提供 full_domain 位置参数，或者同时提供 --domain 和 --rr 选项。",
        ),
        CommandField(
            "rr",
            prompt="rr",
            required=True,
            default="@",
            prompt_if_missing=True,
            missing_message="必须提供 full_domain 位置参数，或者同时提供 --domain 和 --rr 选项。",
        ),
    ),
    constraints=(CommandConstraint(_validate_dns_domain_pair),),
)


DNS_SET_SCHEMA = CommandSchema(
    name="dns-set",
    fields=(
        CommandField(
            "domain",
            prompt="domain",
            required=True,
            missing_message="必须提供 full_domain 或同时提供 -d 和 -r，并指定 --value。",
        ),
        CommandField(
            "rr",
            prompt="rr",
            required=True,
            default="@",
            prompt_if_missing=True,
            missing_message="必须提供 full_domain 或同时提供 -d 和 -r，并指定 --value。",
        ),
        CommandField(
            "value",
            prompt="value",
            required=True,
            missing_message="必须提供 full_domain 或同时提供 -d 和 -r，并指定 --value。",
        ),
    ),
    constraints=(CommandConstraint(_validate_dns_domain_pair),),
)


DNS_DELETE_SCHEMA = CommandSchema(
    name="dns-delete",
    fields=(
        CommandField(
            "domain",
            prompt="domain",
            required=True,
            missing_message="必须提供 full_domain 或同时提供 -d 和 -r，并指定 --type。",
        ),
        CommandField(
            "rr",
            prompt="rr",
            required=True,
            default="@",
            prompt_if_missing=True,
            missing_message="必须提供 full_domain 或同时提供 -d 和 -r，并指定 --type。",
        ),
        CommandField(
            "record_type",
            prompt="type",
            required=True,
            missing_message="必须提供要删除的记录类型，例如 -t A。",
        ),
    ),
    constraints=(CommandConstraint(_validate_dns_domain_pair),),
)


DNS_RECORDS_SCHEMA = CommandSchema(
    name="dns-records",
    fields=(
        CommandField(
            "domain", prompt="domain", required=True, missing_message="必须提供域名。"
        ),
    ),
    constraints=(CommandConstraint(_validate_dns_domain_only),),
)


def _print_domain_table(domains, provider):
    if not domains:
        click.echo("未找到域名")
        return

    click.echo(f"DNS域名 ({provider}):")
    click.echo(
        f"{'DomainName':<30} {'DomainId':<18} {'Status':<10} {'Records':<8} {'Remark'}"
    )
    click.echo("-" * 90)
    for domain in domains:
        click.echo(
            f"{domain.get('DomainName', '-'):<30} "
            f"{str(domain.get('DomainId', '-')):<18} "
            f"{str(domain.get('Status', '-')):<10} "
            f"{str(domain.get('RecordCount', '-')):<8} "
            f"{domain.get('Remark', '-') or '-'}"
        )


def _print_record_table(records, provider):
    if not records:
        click.echo("未找到匹配的记录")
        return

    click.echo(f"DNS记录 ({provider}):")
    click.echo(
        f"{'ID':<20} {'RR':<15} {'Type':<8} {'Value':<30} {'TTL':<6} {'Status'}"
    )
    click.echo("-" * 90)
    for record in records:
        click.echo(
            f"{record['RecordId']:<20} "
            f"{record['RR']:<15} "
            f"{record['Type']:<8} "
            f"{record['Value']:<30} "
            f"{record['TTL']:<6} "
            f"{record.get('Status', '-')}"
        )


async def _get_public_ip(timeout: int = 10):
    import aiohttp

    ip_check_urls = [
        "https://ipv4.icanhazip.com",
        "https://api.ipify.org",
        "https://ipinfo.io/ip",
        "https://checkip.amazonaws.com",
        "https://ident.me",
        "https://v4.ident.me",
    ]
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=timeout)
    ) as session:
        for url in ip_check_urls:
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        ip = (await response.text()).strip()
                        parts = ip.split(".")
                        if len(parts) == 4 and all(0 <= int(p) <= 255 for p in parts):
                            return ip
            except Exception:
                continue
    return None


def _get_local_ip(local_ip_cidr=None):
    import ipaddress
    import netifaces

    candidates = []
    network = None
    if local_ip_cidr:
        try:
            network = ipaddress.ip_network(local_ip_cidr, strict=False)
        except ValueError as exc:
            raise click.ClickException(f"无效的网段格式: {local_ip_cidr}") from exc

    for iface in netifaces.interfaces():
        if iface == "lo":
            continue
        addrs = netifaces.ifaddresses(iface)
        for addr_info in addrs.get(netifaces.AF_INET, []):
            ip = addr_info["addr"]
            if ip.startswith("127."):
                continue
            if network is not None:
                if ipaddress.ip_address(ip) in network:
                    candidates.append(ip)
                continue
            if ip.startswith(("192.168.", "10.", "172.", "100.")):
                candidates.append(ip)

    return candidates[0] if candidates else None


@cli.command(name="list")
@click.option(
    "--provider",
    "-p",
    default="aliyun",
    type=click.Choice(["aliyun", "tencent"]),
    help="DNS提供商 (默认: aliyun)",
)
@click.option("--page", "page_number", default=1, show_default=True, help="页码")
@click.option(
    "--page-size", default=20, show_default=True, help="每页数量，具体上限由云厂商决定"
)
def list_domains(provider, page_number, page_size):
    """List DNS domains in the provider account."""
    logger = setup_logger("dns_list", log_level="INFO", format_type="simple")
    try:
        client = create_dns_client(provider, logger=logger)
        domains = client.describe_domains(
            page_number=page_number,
            page_size=page_size,
        )
        _print_domain_table(domains, provider)
    except click.ClickException:
        raise
    except Exception as e:
        logger.error(f"获取DNS域名列表失败: {e}")
        raise click.ClickException(f"获取DNS域名列表失败: {e}")


@cli.command(name="ip")
@click.option(
    "--type",
    "ip_type",
    default="public",
    type=click.Choice(["public", "local"]),
    help="IP类型 (默认: public)",
)
@click.option(
    "--local-ip-cidr",
    help="局域网IP过滤网段 (例如: 192.168.0.0/16)，仅当 type=local 时有效",
)
def show_ip(ip_type, local_ip_cidr):
    """Show the current public or local IP without touching DNS records."""
    if ip_type == "public":
        current_ip = asyncio.run(_get_public_ip())
    else:
        current_ip = _get_local_ip(local_ip_cidr)

    if not current_ip:
        raise click.ClickException(f"无法获取当前 {ip_type} IP")
    click.echo(current_ip)


@cli.command()
@click.argument("full_domain", required=False)
@click.option("--domain", "-d", help="域名 (如 rexwang.site)")
@click.option("--rr", "-r", help="主机记录 (如 www, @)")
@click.option("--ttl", default=600, help="TTL值 (默认: 600)")
@click.option("--interval", default=120, help="检查间隔秒数 (默认: 120)")
@click.option("--max-retries", default=3, help="最大重试次数 (默认: 3)")
@click.option("--retry-delay", default=5, help="重试延迟秒数 (默认: 5)")
@click.option("--monitor", is_flag=True, help="持续监控IP变化")
@click.option(
    "--log-file",
    default=None,
    help="日志文件路径 (默认不记录到文件，除非开启监控模式且未指定则使用默认)",
)
@click.option("--log-level", default="INFO", help="日志级别 (默认: INFO)")
@click.option(
    "--ip-type",
    default="public",
    type=click.Choice(["public", "local"]),
    help="IP类型 (默认: public)",
)
@click.option(
    "--local-ip-cidr",
    help="局域网IP过滤网段 (例如: 192.168.0.0/16)，仅当 ip-type=local 时有效",
)
@click.option(
    "--provider",
    "-p",
    default="aliyun",
    type=click.Choice(["aliyun", "tencent"]),
    help="DNS提供商 (默认: aliyun)",
)
@add_interactive_option
def ddns(
    full_domain,
    domain,
    rr,
    ttl,
    interval,
    max_retries,
    retry_delay,
    monitor,
    log_file,
    log_level,
    ip_type,
    local_ip_cidr,
    provider,
    interactive,
):
    """Run dynamic DNS updates once or in continuous monitoring mode.

    支持两种参数方式:
    1. 完整域名位置参数:
       chatdns ddns public.rexwang.site

    2. 分别指定域名和记录 (通用模式):
       chatdns ddns -d rexwang.site -r public
    """
    record_type = "A"

    domain, rr = _resolve_domain_inputs(full_domain, domain, rr)
    inputs = resolve_command_inputs(
        schema=DNS_PAIR_SCHEMA,
        provided={"domain": domain, "rr": rr},
        interactive=interactive,
        usage="Usage: chatdns ddns [FULL_DOMAIN] [--domain TEXT] [--rr TEXT] [--provider aliyun|tencent] [-i|-I]",
    )
    domain = inputs["domain"]
    rr = inputs["rr"]

    # 设置日志
    # 如果开启监控且未指定log_file，使用默认 LOG_FILE (定义在本地，或 ip_updater)
    # 由于我们从 ip_updater 移除了默认 LOG_FILE，我们在 CLI 这里定义默认值
    DEFAULT_LOG_FILE = "dynamic_ip_updater.log"

    actual_log_file = log_file
    if monitor and not actual_log_file:
        actual_log_file = DEFAULT_LOG_FILE

    logger = setup_logger(
        name="dns_updater",
        log_file=actual_log_file,
        log_level=log_level,
        format_type="detailed" if monitor else "simple",
    )

    # 创建更新器
    updater = DynamicIPUpdater(
        domain_name=domain,
        rr=rr,
        dns_type=provider,
        record_type=record_type,
        dns_ttl=ttl,
        max_retries=max_retries,
        retry_delay=retry_delay,
        logger=logger,
        log_file=actual_log_file,
        ip_type=ip_type,
        local_ip_cidr=local_ip_cidr,
    )

    try:
        if monitor:
            # 运行持续监控
            asyncio.run(updater.run_continuous(interval))
        else:
            # 执行一次更新
            success = asyncio.run(updater.run_once())
            if success:
                logger.info("DNS更新完成")
            else:
                logger.error("DNS更新失败")
                raise click.ClickException("DNS更新失败")
    except KeyboardInterrupt:
        if monitor:
            logger.info("监控已停止")
        else:
            logger.info("程序被用户中断")
    except click.ClickException:
        raise
    except Exception as e:
        logger.error(f"运行失败: {e}")
        raise click.ClickException(f"运行失败: {e}")


@cli.command(name="set")
@click.argument("full_domain", required=False)
@click.option("--domain", "-d", help="域名")
@click.option("--rr", "-r", help="主机记录")
@click.option("--type", "-t", "record_type", default="A", help="记录类型 (默认: A)")
@click.option("--value", "-v", required=False, help="记录值")
@click.option("--ttl", default=600, help="TTL值 (默认: 600)")
@click.option(
    "--provider",
    "-p",
    default="aliyun",
    type=click.Choice(["aliyun", "tencent"]),
    help="DNS提供商 (默认: aliyun)",
)
@add_interactive_option
def set_record(full_domain, domain, rr, record_type, value, ttl, provider, interactive):
    """Create or update a DNS record.

    支持:
    1. 完整域名: chatdns set test.example.com -v 1.2.3.4
    2. 分开指定: chatdns set -d example.com -r test -v 1.2.3.4
    """
    domain, rr = _resolve_domain_inputs(full_domain, domain, rr)
    inputs = resolve_command_inputs(
        schema=DNS_SET_SCHEMA,
        provided={"domain": domain, "rr": rr, "value": value},
        interactive=interactive,
        usage="Usage: chatdns set [FULL_DOMAIN] [--domain TEXT] [--rr TEXT] --value TEXT [--provider aliyun|tencent] [-i|-I]",
    )
    domain = inputs["domain"]
    rr = inputs["rr"]
    value = inputs["value"]
    record_type = record_type.upper()

    logger = setup_logger("dns_set", log_level="INFO", format_type="simple")
    try:
        client = create_dns_client(provider, logger=logger)

        logger.info(f"设置记录 {rr}.{domain} ({record_type}) -> {value}")
        success = client.set_record_value(domain, rr, record_type, value, ttl)
        if success:
            click.echo(f"操作成功: {rr}.{domain} -> {value}")
        else:
            raise click.ClickException("操作失败")

    except click.ClickException:
        raise
    except Exception as e:
        logger.error(f"设置DNS记录失败: {e}")
        raise click.ClickException(f"设置DNS记录失败: {e}")


@cli.command(name="records")
@click.argument("target", required=False)
@click.option("--domain", "-d", help="域名")
@click.option("--rr", "-r", help="主机记录")
@click.option("--type", "-t", "record_type", help="记录类型过滤")
@click.option(
    "--provider",
    "-p",
    default="aliyun",
    type=click.Choice(["aliyun", "tencent"]),
    help="DNS提供商 (默认: aliyun)",
)
@add_interactive_option
def records(target, domain, rr, record_type, provider, interactive):
    """Show DNS record details.

    支持:
    1. 域名: chatdns records example.com
    2. 完整域名: chatdns records test.example.com
    3. 分开指定: chatdns records -d example.com -r test
    """
    domain, rr = _resolve_records_inputs(target, domain, rr)
    inputs = resolve_command_inputs(
        schema=DNS_RECORDS_SCHEMA,
        provided={"domain": domain},
        interactive=interactive,
        usage="Usage: chatdns records [TARGET] [--domain TEXT] [--rr TEXT] [--provider aliyun|tencent] [-i|-I]",
    )
    domain = inputs["domain"]
    if record_type:
        record_type = record_type.upper()

    logger = setup_logger("dns_records", log_level="INFO", format_type="simple")
    try:
        client = create_dns_client(provider, logger=logger)
        records = client.describe_domain_records(
            domain, subdomain=rr, record_type=record_type
        )
        _print_record_table(records, provider)

    except click.ClickException:
        raise
    except Exception as e:
        logger.error(f"获取DNS记录失败: {e}")
        raise click.ClickException(f"获取DNS记录失败: {e}")


@cli.command(name="delete")
@click.argument("full_domain", required=False)
@click.option("--domain", "-d", help="域名")
@click.option("--rr", "-r", help="主机记录")
@click.option("--type", "-t", "record_type", required=False, help="记录类型")
@click.option("--value", "-v", required=False, help="记录值过滤")
@click.option("--yes", "-y", is_flag=True, help="跳过确认并执行删除")
@click.option(
    "--provider",
    "-p",
    default="aliyun",
    type=click.Choice(["aliyun", "tencent"]),
    help="DNS提供商 (默认: aliyun)",
)
@add_interactive_option
def delete_record(full_domain, domain, rr, record_type, value, yes, provider, interactive):
    """Delete DNS records by domain, host record, type, and optional value."""
    domain, rr = _resolve_domain_inputs(full_domain, domain, rr)
    inputs = resolve_command_inputs(
        schema=DNS_DELETE_SCHEMA,
        provided={"domain": domain, "rr": rr, "record_type": record_type},
        interactive=interactive,
        usage="Usage: chatdns delete [FULL_DOMAIN] --type TYPE [--value TEXT] [--provider aliyun|tencent] [-i|-I]",
    )
    domain = inputs["domain"]
    rr = inputs["rr"]
    record_type = inputs["record_type"].upper()

    logger = setup_logger("dns_delete", log_level="INFO", format_type="simple")
    try:
        client = create_dns_client(provider, logger=logger)
        records = client.describe_domain_records(
            domain, subdomain=rr, record_type=record_type
        )
        matches = [
            record
            for record in records
            if record.get("Type") == record_type
            and (value is None or record.get("Value") == value)
        ]
        if not matches:
            click.echo("未找到匹配的记录")
            return

        click.echo("Matched records:")
        _print_record_table(matches, provider)
        if not yes:
            if interactive is False or not is_interactive_available():
                raise click.ClickException("删除记录需要确认；非交互环境请传入 --yes。")
            if not ask_confirm("Delete these DNS records?", default=False):
                click.echo("已取消")
                return

        deleted_count = 0
        for record in matches:
            if client.delete_domain_record(record["RecordId"], domain_name=domain):
                deleted_count += 1

        if deleted_count == len(matches):
            click.echo(f"删除成功: {deleted_count} 条记录")
            return
        raise click.ClickException(
            f"删除部分失败: {deleted_count}/{len(matches)} 条记录已删除"
        )
    except click.ClickException:
        raise
    except Exception as e:
        logger.error(f"删除DNS记录失败: {e}")
        raise click.ClickException(f"删除DNS记录失败: {e}")


@cli.group(name="cert")
def cert_group():
    """Manage Let's Encrypt certificates through DNS-01 validation."""


@cert_group.command(name="apply")
@click.option(
    "--domain",
    "-d",
    "domains",
    multiple=True,
    help="Certificate domain. Repeat for SANs/wildcards; first domain is the primary name.",
)
@click.option("--email", "-e", help="Let's Encrypt account email.")
@click.option(
    "--provider",
    "-p",
    default="aliyun",
    type=click.Choice(["aliyun", "tencent"]),
    show_default=True,
    help="DNS provider used for DNS-01 TXT records.",
)
@click.option("--cert-dir", default="certs", show_default=True, help="Certificate output directory.")
@click.option("--staging", is_flag=True, help="Use Let's Encrypt staging directory.")
@click.option("--force", is_flag=True, help="Force renewal/application even if local cert is still valid.")
@click.option("--log-file", default=None, help="Optional detailed log file path.")
@click.option("--log-level", default="INFO", show_default=True, help="Log level.")
@add_interactive_option
def cert_apply(domains, email, provider, cert_dir, staging, force, log_file, log_level, interactive):
    """Apply or renew certificates using ACME DNS-01 validation."""
    provided_domains = list(domains)
    if not provided_domains and interactive is not False and is_interactive_available():
        answer = resolve_command_inputs(
            schema=CommandSchema(
                name="cert-domain",
                fields=(
                    CommandField(
                        "domain",
                        prompt="domain",
                        required=True,
                        missing_message="必须提供至少一个 --domain。",
                    ),
                ),
            ),
            provided={"domain": None},
            interactive=interactive,
            usage="Usage: chatdns cert apply -d example.com [-d '*.example.com'] -e EMAIL [--provider aliyun|tencent] [-i|-I]",
        )
        provided_domains = [answer["domain"]]

    email_inputs = resolve_command_inputs(
        schema=CommandSchema(
            name="cert-email",
            fields=(
                CommandField(
                    "email",
                    prompt="email",
                    required=True,
                    missing_message="必须提供 Let's Encrypt 邮箱，例如 -e admin@example.com。",
                ),
            ),
        ),
        provided={"email": email},
        interactive=interactive,
        usage="Usage: chatdns cert apply -d example.com [-d '*.example.com'] -e EMAIL [--provider aliyun|tencent] [-i|-I]",
    )
    email = email_inputs["email"]

    if not provided_domains:
        raise click.ClickException("必须提供至少一个 --domain。")

    from .cert import SSLCertUpdater

    logger = setup_logger(
        name="chatdns_cert",
        log_file=log_file,
        log_level=log_level,
        format_type="detailed" if log_file else "simple",
    )
    updater = SSLCertUpdater(
        domains=provided_domains,
        email=email,
        cert_dir=cert_dir,
        staging=staging,
        force=force,
        dns_type=provider,
        logger=logger,
    )
    success = asyncio.run(updater.run_once())
    if not success:
        raise click.ClickException("证书申请/续期失败。")
    click.echo(f"证书申请/续期成功: {', '.join(provided_domains)}")


@cert_group.command(name="check")
@click.argument("domains", nargs=-1)
@click.option("--cert-dir", default="certs", show_default=True, help="Certificate directory.")
@click.option(
    "--provider",
    "-p",
    default="aliyun",
    type=click.Choice(["aliyun", "tencent"]),
    show_default=True,
    help="DNS provider used only to initialize the updater.",
)
def cert_check(domains, cert_dir, provider):
    """Check local certificate expiry for one or more domains."""
    if not domains:
        raise click.ClickException("请提供至少一个域名，例如: chatdns cert check example.com")

    from .cert import SSLCertUpdater

    logger = setup_logger("chatdns_cert_check", log_level="INFO", format_type="simple")
    updater = SSLCertUpdater(
        domains=list(domains),
        email="check@example.invalid",
        cert_dir=cert_dir,
        dns_type=provider,
        dns_client=object(),
        logger=logger,
    )
    for domain in domains:
        expiry = updater.check_cert_expiry(domain)
        if expiry is None:
            click.echo(f"{domain}: no local certificate")
            continue
        needs = updater.needs_renewal(domain)
        click.echo(f"{domain}: expires {expiry.isoformat()} renew={'yes' if needs else 'no'}")


def _certbot_challenge_record(domain: str, dns_client=None) -> tuple[str, str]:
    from .cert import normalize_certificate_domain

    normalized = normalize_certificate_domain(domain).lstrip("*.")
    main_domain = None
    describe_domains = getattr(dns_client, "describe_domains", None)
    if callable(describe_domains):
        try:
            zones = describe_domains(page_size=100)
            if not isinstance(zones, (list, tuple)):
                zones = []
        except Exception:
            zones = []
        zone_names = []
        for item in zones or []:
            name = item.get("DomainName") if isinstance(item, dict) else str(item)
            if name:
                zone_names.append(name.strip().rstrip(".").lower())
        matches = [zone for zone in zone_names if normalized == zone or normalized.endswith(f".{zone}")]
        if matches:
            main_domain = max(matches, key=len)
    if main_domain is None:
        parts = normalized.split(".")
        main_domain = ".".join(parts[-2:]) if len(parts) >= 2 else normalized
    if normalized == main_domain:
        return main_domain, "_acme-challenge"
    prefix = normalized[: -len(main_domain) - 1]
    return main_domain, f"_acme-challenge.{prefix}"


@cert_group.command(name="hook-auth", hidden=True)
def cert_hook_auth():
    """Certbot manual auth hook for DNS-01 validation."""
    domain = os.environ.get("CERTBOT_DOMAIN")
    validation = os.environ.get("CERTBOT_VALIDATION")
    if not domain or not validation:
        raise click.ClickException("CERTBOT_DOMAIN or CERTBOT_VALIDATION not set")

    provider = os.environ.get("CHATDNS_DNS_PROVIDER") or os.environ.get("CHATTOOL_DNS_PROVIDER", "tencent")
    logger = setup_logger("certbot_hook", log_level="INFO", format_type="simple")
    client = create_dns_client(provider, logger=logger)
    main_domain, rr = _certbot_challenge_record(domain, client)
    record_id = client.add_domain_record(
        domain_name=main_domain, rr=rr, type_="TXT", value=validation, ttl=120
    )
    if record_id is None or record_id is False:
        raise click.ClickException(f"failed to add DNS TXT record for {rr}.{main_domain}")
    click.echo(f"Added TXT record: {rr}.{main_domain}")


@cert_group.command(name="hook-cleanup", hidden=True)
def cert_hook_cleanup():
    """Certbot manual cleanup hook for DNS-01 validation."""
    domain = os.environ.get("CERTBOT_DOMAIN")
    validation = os.environ.get("CERTBOT_VALIDATION")
    if not domain:
        return
    if not validation:
        raise click.ClickException("CERTBOT_VALIDATION not set; refusing broad TXT cleanup")

    provider = os.environ.get("CHATDNS_DNS_PROVIDER") or os.environ.get("CHATTOOL_DNS_PROVIDER", "tencent")
    logger = setup_logger("certbot_hook", log_level="INFO", format_type="simple")
    client = create_dns_client(provider, logger=logger)
    main_domain, rr = _certbot_challenge_record(domain, client)
    client.delete_record_value(main_domain, rr, "TXT", validation)
    click.echo(f"Deleted TXT record value: {rr}.{main_domain}")


main = cli

if __name__ == "__main__":
    main()
