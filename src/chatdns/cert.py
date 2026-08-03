#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SSL 证书自动更新工具 - 基于 Let's Encrypt 和阿里云 DNS

使用 Let's Encrypt 的 DNS-01 挑战验证方式自动申请和更新 SSL 证书。
支持多域名，自动管理 DNS TXT 记录，生成 nginx 可用的证书文件。
"""

import os
import asyncio
import hashlib
import re
import subprocess
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Dict, Optional, Union
from pathlib import Path

from chatenv.paths import get_paths

from .logging_utils import setup_logger
from .utils import create_dns_client, DNSClientType
from .env import load_chatdns_config, resolve_cert_dir

from .acme_dns_tiny import get_crt

try:
    import fcntl
except ImportError:  # pragma: no cover - certificate hosts are POSIX
    fcntl = None

# 证书相关配置
ACME_CHALLENGE_TTL = 120                 # DNS挑战记录TTL
CHALLENGE_WAIT_TIME = 60                 # 等待DNS传播时间
CERT_RENEWAL_DAYS = 30                   # 证书续期提前天数

_DOMAIN_RE = re.compile(
    r"^(?:\*\.)?(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}$"
)
_CERT_PATH_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,62}[A-Za-z0-9])?$")


def normalize_certificate_domain(domain: str) -> str:
    """Validate and normalize an ACME certificate DNS name."""
    normalized = (domain or "").strip().rstrip(".").lower()
    if not normalized:
        raise ValueError("domain must not be empty")
    if any(part in normalized for part in ("/", "\\", "\x00")) or ".." in normalized:
        raise ValueError(f"invalid domain name: {domain!r}")
    if not _DOMAIN_RE.match(normalized):
        raise ValueError(f"invalid domain name: {domain!r}")
    return normalized


def normalize_cert_path(cert_path: str) -> str:
    """Validate one relative certificate-directory name."""
    normalized = (cert_path or "").strip()
    if not normalized or normalized in {".", ".."}:
        raise ValueError("cert_path must be a non-empty relative directory name")
    if Path(normalized).is_absolute() or any(
        char in normalized for char in ("/", "\\", "\x00")
    ):
        raise ValueError(f"invalid cert_path: {cert_path!r}")
    if not _CERT_PATH_RE.fullmatch(normalized):
        raise ValueError(
            "cert_path may contain only ASCII letters, digits, dots, underscores, and hyphens"
        )
    return normalized


_CERT_RE = re.compile(
    r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----\s*",
    re.DOTALL,
)


def split_pem_chain(pem: str) -> tuple[str, str]:
    """Split a PEM fullchain into ``(leaf_cert, chain_cert)``."""
    certs = _CERT_RE.findall(pem)
    if not certs:
        raise ValueError("fullchain does not contain a PEM certificate")
    leaf_cert = certs[0].rstrip() + "\n"
    chain_cert = "".join(cert.rstrip() + "\n" for cert in certs[1:])
    return leaf_cert, chain_cert


class SSLCertUpdater:
    """SSL证书自动更新器"""

    def __init__(self,
                 domains: List[str],
                 email: str,
                 cert_dir: str | Path | None = None,
                 cert_path: str | None = None,
                 acme_state_dir: str | Path | None = None,
                 staging: bool = False,
                 force: bool = False,
                 logger=None,
                 log_file: Optional[str] = None,
                 dns_type: Union[DNSClientType, str]='aliyun',
                 dns_client=None,
                 env_profile: Optional[str] = None,
                 chatarch_home: str | Path | None = None,
                 **dns_client_kwargs
        ):
        """
        初始化SSL证书更新器

        Args:
            domains: 域名列表
            email: Let's Encrypt账户邮箱
            cert_dir: 证书存储目录；未提供时读取 CHATDNS_CERT_DIR，再回退到 CHATARCH_HOME/certs
            cert_path: 注册域名下的相对证书目录名；未提供时使用 default
            acme_state_dir: ACME 状态目录；默认位于 CHATARCH_HOME/private/chatdns/acme
            staging: 是否使用Let's Encrypt测试环境
            force: 是否跳过本地证书过期判断，强制申请/续期
            logger: 日志记录器
            log_file: 日志文件路径 (如果未提供 logger 且需要文件日志)
            dns_type: DNS客户端类型
            dns_client: 可选的已初始化 DNS 客户端（主要用于测试或本地 check 路径）
            env_profile: 可选 ChatEnv profile 名称
            chatarch_home: 可选 CHATARCH_HOME 覆盖路径
            dns_client_kwargs: DNS客户端初始化参数
        """
        self.domains = [normalize_certificate_domain(domain) for domain in domains]
        self.email = email
        if cert_dir is None:
            load_chatdns_config(env_profile=env_profile, home=chatarch_home)
        self.cert_dir = resolve_cert_dir(cert_dir, home=chatarch_home)
        self.cert_dir.mkdir(parents=True, exist_ok=True)
        self.cert_dir = self.cert_dir.resolve()
        self.cert_dir.chmod(0o700)
        self.cert_path = normalize_cert_path(cert_path) if cert_path is not None else None
        explicit_state_dir = acme_state_dir is not None
        selected_state_dir = acme_state_dir or (
            get_paths(chatarch_home).home_dir / "private" / "chatdns" / "acme"
        )
        self.acme_state_dir = Path(selected_state_dir).expanduser().resolve()
        try:
            self.acme_state_dir.relative_to(self.cert_dir)
        except ValueError:
            pass
        else:
            if explicit_state_dir:
                raise ValueError("acme_state_dir must be outside the certificate root")
            self.acme_state_dir = (
                self.cert_dir.parent / f".{self.cert_dir.name}.chatdns-private" / "acme"
            ).resolve()
        self.acme_state_dir.mkdir(parents=True, exist_ok=True)
        self.acme_state_dir.chmod(0o700)
        self._certificate_dir_cache: Dict[tuple[str, ...], Path] = {}
        self._reserved_certificate_dirs: Dict[Path, tuple[str, ...]] = {}
        self.staging = staging
        self.force = force
        self.logger = logger or setup_logger(__name__, log_file=log_file)

        # 初始化DNS客户端
        self.dns_client = dns_client or create_dns_client(
            dns_type,
            env_profile=env_profile,
            chatarch_home=chatarch_home,
            logger=self.logger,
            **dns_client_kwargs,
        )

        # Let's Encrypt服务器URL
        self.acme_server = (
            "https://acme-staging-v02.api.letsencrypt.org/directory" if staging
            else "https://acme-v02.api.letsencrypt.org/directory"
        )

        self.logger.info(f"SSL证书更新器初始化完成")
        self.logger.info(f"域名: {', '.join(self.domains)}")
        self.logger.info(f"邮箱: {self.email}")
        self.logger.info(f"证书目录: {self.cert_dir}")
        self.logger.info(f"证书相对目录: {self.cert_path or 'default'}")
        self.logger.info(f"环境: {'测试' if staging else '生产'}")

    def _path_in_cert_dir(self, *parts: str) -> Path:
        path = self.cert_dir.joinpath(*parts).resolve()
        path.relative_to(self.cert_dir)
        return path

    @staticmethod
    def _certificate_sans(directory: Path) -> Optional[set[str]]:
        """Read the normalized SAN set from a stored certificate directory."""
        from cryptography import x509
        from cryptography.x509.oid import ExtensionOID

        cert_file = directory / "fullchain.pem"
        if not cert_file.is_file():
            cert_file = directory / "cert.pem"
        if not cert_file.is_file():
            return None
        try:
            leaf_pem, _ = split_pem_chain(cert_file.read_text(encoding="utf-8"))
            certificate = x509.load_pem_x509_certificate(leaf_pem.encode("utf-8"))
            extension = certificate.extensions.get_extension_for_oid(
                ExtensionOID.SUBJECT_ALTERNATIVE_NAME
            ).value
            if not isinstance(extension, x509.SubjectAlternativeName):
                return None
            names = extension.get_values_for_type(x509.DNSName)
            return {normalize_certificate_domain(name) for name in names}
        except (OSError, ValueError, x509.ExtensionNotFound):
            return None

    def _matches_cert_path_name(self, name: str) -> bool:
        if self.cert_path is None:
            return True
        return bool(
            name == self.cert_path
            or re.fullmatch(rf"{re.escape(self.cert_path)}-(?:[2-9]|[1-9][0-9]+)", name)
        )

    def find_certificate_dir(self, domains: List[str]) -> Optional[Path]:
        """Find an existing two-level certificate that covers the requested names."""
        expected_sans = {
            normalize_certificate_domain(domain) for domain in domains
        }
        candidates: list[tuple[bool, Path]] = []
        zone_dirs = [
            path for path in sorted(self.cert_dir.iterdir()) if path.is_dir()
        ]

        for zone_dir in zone_dirs:
            try:
                resolved_zone_dir = zone_dir.resolve()
                resolved_zone_dir.relative_to(self.cert_dir)
            except (OSError, ValueError):
                continue
            for directory in sorted(
                resolved_zone_dir.iterdir(), key=lambda item: item.name
            ):
                if not directory.is_dir():
                    continue
                if not self._matches_cert_path_name(directory.name):
                    continue
                try:
                    resolved_directory = directory.resolve()
                    resolved_directory.relative_to(self.cert_dir)
                except (OSError, ValueError):
                    continue
                actual_sans = self._certificate_sans(resolved_directory)
                if actual_sans is None or not expected_sans.issubset(actual_sans):
                    continue
                candidates.append((actual_sans != expected_sans, resolved_directory))

        if not candidates:
            return None
        return min(candidates, key=lambda candidate: (candidate[0], str(candidate[1])))[1]

    def suggest_cert_path(self, domains: List[str]) -> str:
        """Suggest a URI-style name for a nested wildcard without selecting it."""
        zone = self.extract_domain_from_fqdn(domains[0])
        for domain in domains:
            normalized = normalize_certificate_domain(domain)
            if not normalized.startswith("*."):
                continue
            wildcard_base = normalized[2:]
            if wildcard_base == zone:
                return "default"
            suffix = f".{zone}"
            if wildcard_base.endswith(suffix):
                relative = wildcard_base[: -len(suffix)]
                if relative:
                    return normalize_cert_path(relative)
        return "default"

    def resolve_certificate_dir(self, domains: List[str]) -> Path:
        """Return the stable two-level output directory for one SAN group."""
        normalized_domains = [normalize_certificate_domain(domain) for domain in domains]
        key = tuple(sorted(normalized_domains))
        cached = self._certificate_dir_cache.get(key)
        if cached is not None:
            return cached

        zone = self.extract_domain_from_fqdn(normalized_domains[0])
        zone_dir = self._path_in_cert_dir(zone)
        expected_sans = set(normalized_domains)

        if zone_dir.is_dir():
            matches = []
            for child in sorted(zone_dir.iterdir(), key=lambda item: item.name):
                if not child.is_dir():
                    continue
                if not self._matches_cert_path_name(child.name):
                    continue
                try:
                    resolved_child = child.resolve()
                    resolved_child.relative_to(self.cert_dir)
                except (OSError, ValueError):
                    continue
                if self._certificate_sans(resolved_child) == expected_sans:
                    matches.append(resolved_child)
            if matches:
                selected = matches[0]
                self._certificate_dir_cache[key] = selected
                self._reserved_certificate_dirs[selected] = key
                return selected

        base_name = self.cert_path or "default"
        suffix_number = 1
        while True:
            name = base_name if suffix_number == 1 else f"{base_name}-{suffix_number}"
            try:
                candidate = self._path_in_cert_dir(zone, name)
            except ValueError:
                suffix_number += 1
                continue
            reserved_for = self._reserved_certificate_dirs.get(candidate)
            if candidate.exists():
                existing_sans = self._certificate_sans(candidate)
                if existing_sans == expected_sans:
                    selected = candidate
                    break
                suffix_number += 1
                continue
            if reserved_for == key:
                selected = candidate
                break
            if reserved_for is not None:
                suffix_number += 1
                continue
            self._reserved_certificate_dirs[candidate] = key
            selected = candidate
            break

        self._certificate_dir_cache[key] = selected
        self._reserved_certificate_dirs[selected] = key
        return selected

    def _domain_dir(self, domain: str) -> Path:
        normalized = normalize_certificate_domain(domain)
        for domain_list in self._group_domains_by_main_domain().values():
            if normalized in domain_list:
                return self.find_certificate_dir(domain_list) or self.resolve_certificate_dir(
                    domain_list
                )
        return self.resolve_certificate_dir([normalized])

    @asynccontextmanager
    async def _issuance_lock(self, domains: List[str]):
        """Serialize one registered-domain/path namespace outside the cert tree."""
        normalized_domains = [
            normalize_certificate_domain(domain) for domain in domains
        ]
        zone = self.extract_domain_from_fqdn(normalized_domains[0])
        namespace = f"{zone}\n{self.cert_path or 'default'}"
        digest = hashlib.sha256(namespace.encode("utf-8")).hexdigest()
        lock_dir = self.acme_state_dir / "locks"
        lock_dir.mkdir(parents=True, exist_ok=True)
        lock_dir.chmod(0o700)
        lock_path = lock_dir / f"{digest}.lock"
        with open(lock_path, "a+", encoding="utf-8") as lock_file:
            lock_path.chmod(0o600)
            if fcntl is not None:
                while True:
                    try:
                        fcntl.flock(
                            lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB
                        )
                        break
                    except BlockingIOError:
                        await asyncio.sleep(0.1)
            try:
                yield
            finally:
                if fcntl is not None:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def check_cert_expiry(self, domain: str) -> Optional[datetime]:
        """
        检查证书过期时间

        Args:
            domain: 域名

        Returns:
            证书过期时间，如果证书不存在返回None
        """
        cert_file = self._domain_dir(domain) / "fullchain.pem"

        if not cert_file.exists():
            return None

        try:
            result = subprocess.run([
                "openssl", "x509", "-in", str(cert_file),
                "-noout", "-enddate"
            ], capture_output=True, text=True, check=True)

            # 解析日期格式: notAfter=Dec 30 23:59:59 2024 GMT
            date_str = result.stdout.strip().split('=')[1]
            expiry_date = datetime.strptime(date_str, "%b %d %H:%M:%S %Y %Z")
            return expiry_date

        except (subprocess.CalledProcessError, ValueError, IndexError) as e:
            self.logger.warning(f"无法解析证书过期时间 {domain}: {e}")
            return None

    def needs_renewal(self, domain: str) -> bool:
        """
        检查证书是否需要续期

        Args:
            domain: 域名

        Returns:
            是否需要续期
        """
        expiry_date = self.check_cert_expiry(domain)
        if expiry_date is None:
            self.logger.info(f"域名 {domain} 证书不存在，需要申请")
            return True

        days_until_expiry = (expiry_date - datetime.now()).days
        self.logger.info(f"域名 {domain} 证书将在 {days_until_expiry} 天后过期")

        if days_until_expiry <= CERT_RENEWAL_DAYS:
            self.logger.info(f"域名 {domain} 证书需要续期")
            return True
        else:
            self.logger.info(f"域名 {domain} 证书暂不需要续期")
            return False

    def certificate_covers_domains(self, primary_domain: str, domains: List[str]) -> bool:
        """Return whether the stored primary certificate covers every requested SAN."""
        from cryptography import x509
        from cryptography.x509.oid import ExtensionOID

        cert_file = self._domain_dir(primary_domain) / "fullchain.pem"
        if not cert_file.is_file():
            return False
        try:
            leaf_pem, _ = split_pem_chain(cert_file.read_text())
            certificate = x509.load_pem_x509_certificate(leaf_pem.encode("utf-8"))
            extension = certificate.extensions.get_extension_for_oid(
                ExtensionOID.SUBJECT_ALTERNATIVE_NAME
            ).value
            if not isinstance(extension, x509.SubjectAlternativeName):
                return False
            names = extension.get_values_for_type(x509.DNSName)
        except (OSError, ValueError, x509.ExtensionNotFound) as exc:
            self.logger.warning(f"无法读取证书 SAN {primary_domain}: {exc}")
            return False

        expected = {normalize_certificate_domain(domain) for domain in domains}
        actual = {normalize_certificate_domain(domain) for domain in names}
        missing = sorted(expected - actual)
        if missing:
            self.logger.info(
                f"域名组 {primary_domain} 的证书缺少 SAN: {', '.join(missing)}"
            )
            return False
        return True

    def needs_group_renewal(self, domains: List[str]) -> bool:
        """Check one stored certificate for expiry and complete SAN coverage."""
        primary_domain = domains[0]
        return self.needs_renewal(primary_domain) or not self.certificate_covers_domains(
            primary_domain, domains
        )

    def extract_domain_from_fqdn(self, fqdn: str) -> str:
        """
        从FQDN中提取主域名

        Args:
            fqdn: 完整域名

        Returns:
            主域名
        """
        fqdn = normalize_certificate_domain(fqdn).lstrip("*.")
        managed_zone = self._find_managed_zone(fqdn)
        if managed_zone:
            return managed_zone
        parts = fqdn.split('.')
        # Fallback: take last two labels only when provider zone discovery is unavailable.
        if len(parts) >= 2:
            return '.'.join(parts[-2:])
        return fqdn

    def _find_managed_zone(self, fqdn: str) -> Optional[str]:
        """Return the longest provider-managed zone suffix for ``fqdn`` when available."""
        describe_domains = getattr(self.dns_client, "describe_domains", None)
        if not callable(describe_domains):
            return None
        try:
            zones = describe_domains(page_size=100)
            if not isinstance(zones, (list, tuple)):
                zones = []
        except Exception as exc:
            self.logger.debug(f"Unable to discover managed DNS zones: {exc}")
            return None
        zone_names = []
        for item in zones or []:
            name = item.get("DomainName") if isinstance(item, dict) else str(item)
            if name:
                zone_names.append(name.strip().rstrip(".").lower())
        matches = [zone for zone in zone_names if fqdn == zone or fqdn.endswith(f".{zone}")]
        if not matches:
            return None
        return max(matches, key=len)

    def get_acme_challenge_record(self, domain: str) -> tuple[str, str]:
        """Return ``(main_domain, rr)`` for an ACME DNS-01 TXT challenge."""
        normalized = normalize_certificate_domain(domain).lstrip("*.")
        main_domain = self.extract_domain_from_fqdn(normalized)
        if normalized == main_domain:
            return main_domain, "_acme-challenge"
        prefix = normalized[: -len(main_domain) - 1]
        return main_domain, f"_acme-challenge.{prefix}"

    async def update_certificates(self) -> bool:
        """
        更新所有域名的证书

        Returns:
            是否全部更新成功
        """
        success_count = 0

        # 按主域名分组
        domain_groups = self._group_domains_by_main_domain()

        for main_domain, domain_list in domain_groups.items():
            self.logger.info(f"处理域名组: {main_domain} -> {domain_list}")

            async with self._issuance_lock(domain_list):
                cache_key = tuple(
                    sorted(
                        normalize_certificate_domain(domain)
                        for domain in domain_list
                    )
                )
                self._certificate_dir_cache.pop(cache_key, None)

                # Re-check after acquiring the process lock because another
                # process may have installed this SAN set while we waited.
                needs_update = self.force or self.needs_group_renewal(domain_list)
                if self.force:
                    self.logger.info(f"域名组 {main_domain} 已启用强制申请/续期")

                if not needs_update:
                    self.logger.info(f"域名组 {main_domain} 的证书都不需要更新")
                    success_count += 1
                    continue

                if await self._request_certificate_for_domains(domain_list):
                    success_count += 1
                    self.logger.info(f"域名组 {main_domain} 证书更新成功")
                else:
                    self.logger.error(f"域名组 {main_domain} 证书申请失败")


        total_groups = len(domain_groups)
        self.logger.info(f"证书更新完成: {success_count}/{total_groups} 个域名组成功")

        return success_count == total_groups

    def _group_domains_by_main_domain(self) -> Dict[str, List[str]]:
        """
        按主域名对域名进行分组

        Returns:
            域名分组字典
        """
        groups = {}
        for domain in self.domains:
            main_domain = self.extract_domain_from_fqdn(domain)
            if main_domain not in groups:
                groups[main_domain] = []
            groups[main_domain].append(domain)
        return groups

    def _ensure_account_key(self) -> str:
        """Ensure the ACME account key exists outside the certificate tree."""
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        key_path = self.acme_state_dir / "account.key"
        if key_path.is_symlink():
            raise ValueError("ACME account key must not be a symbolic link")
        if not key_path.exists():
            self.logger.info("Generating new account key (RSA 2048)...")
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
            )
            pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
            temporary_path = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="wb",
                    prefix="account-",
                    suffix=".key",
                    dir=self.acme_state_dir,
                    delete=False,
                ) as temporary_file:
                    temporary_file.write(pem)
                    temporary_file.flush()
                    os.fsync(temporary_file.fileno())
                    temporary_path = Path(temporary_file.name)
                temporary_path.chmod(0o600)
                try:
                    os.link(temporary_path, key_path)
                except FileExistsError:
                    pass
            finally:
                if temporary_path is not None:
                    temporary_path.unlink(missing_ok=True)

        return key_path.read_text(encoding="utf-8")

    def _ensure_domain_key(self, certificate_dir: Path) -> str:
        """Reuse the deployed key or create an in-memory ECDSA key."""
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec

        key_path = certificate_dir / "privkey.pem"
        if key_path.is_symlink():
            raise ValueError("certificate private key must not be a symbolic link")
        if key_path.is_file():
            return key_path.read_text(encoding="utf-8")

        self.logger.info(
            f"Generating new private key for {certificate_dir.name} (ECDSA secp384r1)..."
        )
        private_key = ec.generate_private_key(ec.SECP384R1())
        pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
        return pem.decode("utf-8")

    def verify_certificate_key_match(self, cert_path: Path, key_path: Path) -> bool:
        """
        Verify that the certificate matches the private key.

        Args:
            cert_path: Path to the certificate file (PEM format)
            key_path: Path to the private key file (PEM format)

        Returns:
            True if they match, False otherwise
        """
        from cryptography import x509
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa, ec
        try:
            cert_pem = cert_path.read_bytes()
            key_pem = key_path.read_bytes()

            cert = x509.load_pem_x509_certificate(cert_pem)
            private_key = serialization.load_pem_private_key(key_pem, password=None)

            cert_public_key = cert.public_key()
            private_key_public_key = private_key.public_key()

            # For Elliptic Curve keys
            if isinstance(cert_public_key, ec.EllipticCurvePublicKey) and \
               isinstance(private_key_public_key, ec.EllipticCurvePublicKey):
                # Compare curve name and public numbers
                if cert_public_key.curve.name != private_key_public_key.curve.name:
                    return False
                return cert_public_key.public_numbers() == private_key_public_key.public_numbers()

            # For RSA keys (legacy)
            if isinstance(cert_public_key, rsa.RSAPublicKey) and \
               isinstance(private_key_public_key, rsa.RSAPublicKey):
                return cert_public_key.public_numbers() == private_key_public_key.public_numbers()

            # Mismatched key types
            return False

        except Exception as e:
            self.logger.error(f"Certificate/Key verification failed: {e}")
            return False

    def _generate_csr(self, main_domain: str, domains: List[str], domain_key_pem: str) -> str:
        """Generate CSR for the domain list"""
        from cryptography import x509
        from cryptography.hazmat.primitives import serialization, hashes
        from cryptography.x509.oid import NameOID

        private_key = serialization.load_pem_private_key(domain_key_pem.encode('utf8'), password=None)

        builder = x509.CertificateSigningRequestBuilder()
        builder = builder.subject_name(x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, main_domain),
        ]))

        builder = builder.add_extension(
            x509.SubjectAlternativeName([x509.DNSName(d) for d in domains]),
            critical=False,
        )

        csr = builder.sign(private_key, hashes.SHA256())
        return csr.public_bytes(serialization.Encoding.PEM).decode('utf8')

    async def _request_certificate_for_domains(self, domains: List[str]) -> bool:
        """
        使用 ACME 协议申请证书

        Args:
            domains: 域名列表

        Returns:
            是否申请成功

        Logic:
        1. 确定主域名 (用于文件名和 CN): 取列表第一个域名。
        2. 生成 Account Key (如果不存在): 使用 RSA 2048。
        3. 生成 Domain Private Key (如果不存在): 使用 ECDSA secp384r1 (更安全且短)。
        4. 生成 CSR (Certificate Signing Request)。
        5. 调用 `acme_dns_tiny.get_crt` 获取证书:
            - 该函数是同步阻塞的，因此在 `run_in_executor` 中运行以避免阻塞 asyncio 循环。
            - 传递两个回调函数 `dns_update` 和 `dns_cleanup` 用于处理 DNS-01 挑战。
            - 回调函数内部调用 `self.dns_client` (同步方法) 添加/删除 TXT 记录。
        6. 保存证书文件:
            - `privkey.pem`: 私钥
            - `fullchain.pem`: 完整证书链 (从 ACME 获取)
            - `cert.pem`: 叶子证书 (从 fullchain 分离)
            - `chain.pem`: 中间证书 (从 fullchain 分离)
        7. 验证证书与私钥是否匹配 (`verify_certificate_key_match`)。
        """
        self.logger.info(f"Starting ACME process for: {domains}")

        main_domain = normalize_certificate_domain(domains[0])
        domain_dir = self.resolve_certificate_dir(domains)

        try:
            account_key = self._ensure_account_key()
            domain_key = self._ensure_domain_key(domain_dir)
            csr = self._generate_csr(main_domain, domains, domain_key)

            # Callbacks for DNS challenge (executed in thread executor context)
            def dns_update(domain, token):
                self.logger.info(f"Callback: Updating DNS for {domain}")
                main_d, rr = self.get_acme_challenge_record(domain)
                record_id = self.dns_client.add_domain_record(
                    domain_name=main_d, rr=rr, type_="TXT", value=token, ttl=600
                )
                if record_id is None:
                    raise RuntimeError(f"failed to add DNS TXT record for {rr}.{main_d}")

            def dns_cleanup(domain, token=None):
                self.logger.info(f"Callback: Cleaning DNS for {domain}")
                main_d, rr = self.get_acme_challenge_record(domain)
                if token is None:
                    self.logger.warning(
                        "Skipping ACME TXT cleanup for %s.%s because challenge value is unknown",
                        rr,
                        main_d,
                    )
                    return
                self.dns_client.delete_record_value(main_d, rr, "TXT", token)

            # Run get_crt in executor to avoid blocking async loop
            loop = asyncio.get_running_loop()
            crt_pem = await loop.run_in_executor(
                None,
                lambda: get_crt(
                    account_key,
                    csr,
                    dns_update,
                    dns_cleanup,
                    directory_url=self.acme_server,
                    contact=[f"mailto:{self.email}"]
                )
            )

            leaf_cert, chain_cert = split_pem_chain(crt_pem)
            with tempfile.TemporaryDirectory(
                prefix="issuance-", dir=self.acme_state_dir
            ) as temporary_directory:
                staging_dir = Path(temporary_directory)
                staged_files = {
                    "cert.pem": leaf_cert,
                    "chain.pem": chain_cert,
                    "fullchain.pem": crt_pem,
                    "privkey.pem": domain_key,
                }
                for filename, content in staged_files.items():
                    path = staging_dir / filename
                    path.write_text(content, encoding="utf-8")
                    path.chmod(0o600 if filename == "privkey.pem" else 0o644)

                if not self.verify_certificate_key_match(
                    staging_dir / "cert.pem", staging_dir / "privkey.pem"
                ):
                    self.logger.error(
                        "Certificate verification FAILED: Does not match private key!"
                    )
                    return False

                expected_sans = {
                    normalize_certificate_domain(domain) for domain in domains
                }
                actual_sans = self._certificate_sans(staging_dir)
                if actual_sans != expected_sans:
                    self.logger.error(
                        "Certificate verification FAILED: returned SAN set does not "
                        "match requested domains"
                    )
                    return False

                domain_dir.mkdir(parents=True, exist_ok=True)
                domain_dir.chmod(0o700)
                for filename in ("chain.pem", "fullchain.pem", "cert.pem", "privkey.pem"):
                    os.replace(staging_dir / filename, domain_dir / filename)
                    self.logger.info(f"Saved {filename} to {domain_dir / filename}")

            self.logger.info("Certificate verification successful: Matches private key")

            return True

        except Exception as e:
            self.logger.error(f"ACME Tiny process failed: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    async def run_once(self) -> bool:
        """
        执行一次证书更新检查和更新

        Returns:
            是否执行成功
        """
        try:
            self.logger.info("开始执行SSL证书更新检查")
            result = await self.update_certificates()
            self.logger.info(f"SSL证书更新检查完成，结果: {'成功' if result else '失败'}")
            return result
        except Exception as e:
            self.logger.error(f"执行SSL证书更新时发生异常: {e}")
            return False
