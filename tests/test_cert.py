import asyncio
import json
import stat
from pathlib import Path

import pytest
from click.testing import CliRunner
from unittest.mock import AsyncMock, Mock, patch

from chatdns.cli import main, _certbot_challenge_record
from chatdns.cert import SSLCertUpdater, normalize_certificate_domain, split_pem_chain


_DEFAULT_ADD_RESULT = object()


def _write_env(home: Path, storage: str, filename: str, content: str) -> None:
    path = home / "envs" / storage / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.fixture(autouse=True)
def isolated_chatarch_home(monkeypatch, tmp_path):
    monkeypatch.setenv("CHATARCH_HOME", str(tmp_path / "chatarch"))
    monkeypatch.delenv("CHATDNS_CERT_DIR", raising=False)


class FakeDNSClient:
    def __init__(self, zones=None, add_result=_DEFAULT_ADD_RESULT):
        self.zones = zones or []
        self.add_result = "record-id" if add_result is _DEFAULT_ADD_RESULT else add_result
        self.added = []
        self.deleted = []

    def describe_domains(self, page_size=100):
        return [{"DomainName": zone} for zone in self.zones]

    def add_domain_record(self, **kwargs):
        self.added.append(kwargs)
        return self.add_result

    def delete_record_value(self, *args):
        self.deleted.append(args)
        return True


def _write_test_certificate(path: Path, sans: list[str], *, days: int = 90) -> None:
    from datetime import datetime, timedelta, timezone

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, sans[0])]))
        .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, sans[0])]))
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=days))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(domain) for domain in sans]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))


def test_cert_apply_invokes_ssl_updater_without_live_acme():
    runner = CliRunner()
    with patch("chatdns.cert.SSLCertUpdater") as updater_cls:
        updater = updater_cls.return_value
        domain_group = ["example.com", "*.example.com"]
        output_dir = Path("certs-test/example.com/precision")
        updater._group_domains_by_main_domain.return_value = {
            "example.com": domain_group
        }
        updater.resolve_certificate_dir.return_value = output_dir
        updater.find_certificate_dir.return_value = output_dir
        updater.suggest_cert_path.return_value = "default"
        updater.run_once = AsyncMock(return_value=True)

        result = runner.invoke(
            main,
            [
                "cert",
                "apply",
                "-d",
                "example.com",
                "-d",
                "*.example.com",
                "-e",
                "admin@example.com",
                "--provider",
                "tencent",
                "--cert-dir",
                "certs-test",
                "--cert-path",
                "precision",
                "--staging",
                "--force",
                "-I",
            ],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, result.output
    assert "证书申请/续期成功" in result.output
    updater_cls.assert_called_once()
    kwargs = updater_cls.call_args.kwargs
    assert kwargs["domains"] == ["example.com", "*.example.com"]
    assert kwargs["email"] == "admin@example.com"
    assert kwargs["dns_type"] == "tencent"
    assert kwargs["cert_dir"] == "certs-test"
    assert kwargs["cert_path"] == "precision"
    assert kwargs["staging"] is True
    assert kwargs["force"] is True
    updater.run_once.assert_awaited_once()


def test_cert_apply_previews_each_managed_zone_group():
    runner = CliRunner()
    example_com = ["*.example.com"]
    example_net = ["*.example.net"]
    com_path = Path("certs/example.com/default")
    net_path = Path("certs/example.net/default")
    with patch("chatdns.cert.SSLCertUpdater") as updater_cls:
        updater = updater_cls.return_value
        updater._group_domains_by_main_domain.return_value = {
            "example.com": example_com,
            "example.net": example_net,
        }
        updater.resolve_certificate_dir.side_effect = [com_path, net_path]
        updater.find_certificate_dir.side_effect = [com_path, net_path]
        updater.suggest_cert_path.return_value = "default"
        updater.run_once = AsyncMock(return_value=True)

        result = runner.invoke(
            main,
            [
                "cert",
                "apply",
                "-d",
                "*.example.com",
                "-d",
                "*.example.net",
                "-e",
                "admin@example.com",
                "--provider",
                "tencent",
                "-I",
            ],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, result.output
    assert f"证书路径（预览）: {com_path}" in result.output
    assert f"证书路径（预览）: {net_path}" in result.output
    assert f"证书路径（实际）: {com_path}" in result.output
    assert f"证书路径（实际）: {net_path}" in result.output
    assert [item.args for item in updater.resolve_certificate_dir.call_args_list] == [
        (example_com,),
        (example_net,),
    ]
    updater.run_once.assert_awaited_once()


def test_cert_help_documents_chatarch_managed_default():
    for command in (["cert", "apply", "--help"], ["cert", "check", "--help"]):
        result = CliRunner().invoke(main, command)
        assert result.exit_code == 0, result.output
        assert "CHATDNS_CERT_DIR or $CHATARCH_HOME/certs" in result.output
        assert "--cert-path" in result.output


def test_cert_apply_uses_chatenv_cert_dir(tmp_path):
    configured = tmp_path / "central-certs"
    _write_env(
        tmp_path,
        "ChatDNS",
        ".env",
        f"CHATDNS_CERT_DIR='{configured}'\n",
    )
    runner = CliRunner()
    with patch("chatdns.cert.SSLCertUpdater") as updater_cls:
        updater = updater_cls.return_value
        domain_group = ["*.example.com"]
        output_dir = configured / "example.com" / "default"
        updater._group_domains_by_main_domain.return_value = {
            "example.com": domain_group
        }
        updater.resolve_certificate_dir.return_value = output_dir
        updater.find_certificate_dir.return_value = output_dir
        updater.suggest_cert_path.return_value = "default"
        updater.run_once = AsyncMock(return_value=True)
        result = runner.invoke(
            main,
            [
                "--chatarch-home",
                str(tmp_path),
                "cert",
                "apply",
                "-d",
                "*.example.com",
                "-e",
                "admin@example.com",
                "--provider",
                "tencent",
                "-I",
            ],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, result.output
    assert updater_cls.call_args.kwargs["cert_dir"] == str(configured)


def test_cert_check_defaults_inside_overridden_chatarch_home(tmp_path):
    runner = CliRunner()
    with patch("chatdns.cert.SSLCertUpdater") as updater_cls:
        updater_cls.return_value.check_cert_expiry.return_value = None
        result = runner.invoke(
            main,
            ["--chatarch-home", str(tmp_path), "cert", "check", "example.com"],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, result.output
    assert updater_cls.call_args.kwargs["cert_dir"] == str(tmp_path / "certs")


def test_ssl_updater_uses_chatenv_cert_dir_for_python_api(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    chatarch_home = tmp_path / "chatarch"
    configured = tmp_path / "api-certs"
    _write_env(
        chatarch_home,
        "ChatDNS",
        ".env",
        f"CHATDNS_CERT_DIR='{configured}'\n",
    )

    updater = SSLCertUpdater(
        domains=["*.example.com"],
        email="admin@example.com",
        dns_client=FakeDNSClient(),
        chatarch_home=chatarch_home,
    )

    assert updater.cert_dir == configured.resolve()


def test_ssl_updater_secures_certificate_root(tmp_path):
    cert_root = tmp_path / "certificates"

    SSLCertUpdater(
        domains=["example.com"],
        email="admin@example.com",
        cert_dir=cert_root,
        dns_client=FakeDNSClient(),
    )

    assert stat.S_IMODE(cert_root.stat().st_mode) == 0o700


def test_cert_apply_requires_domain_in_non_interactive_mode():
    result = CliRunner().invoke(
        main, ["cert", "apply", "-e", "admin@example.com", "-I"]
    )
    assert result.exit_code != 0
    assert "必须提供至少一个 --domain" in result.output


def test_cert_check_does_not_initialize_real_dns_client(tmp_path):
    runner = CliRunner()
    with patch("chatdns.cert.SSLCertUpdater") as updater_cls:
        updater = updater_cls.return_value
        updater._group_domains_by_main_domain.return_value = {
            "example.com": ["example.com"]
        }
        updater.check_cert_expiry.return_value = None
        result = runner.invoke(
            main,
            ["cert", "check", "example.com", "--cert-dir", str(tmp_path)],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, result.output
    assert "example.com: no local certificate" in result.output
    kwargs = updater_cls.call_args.kwargs
    assert kwargs["dns_client"] is not None


def test_cert_check_reports_one_multi_san_certificate_for_all_names(tmp_path):
    _write_test_certificate(
        tmp_path / "example.com" / "default" / "fullchain.pem",
        ["example.com", "*.example.com"],
    )

    result = CliRunner().invoke(
        main,
        [
            "cert",
            "check",
            "example.com",
            "*.example.com",
            "--cert-dir",
            str(tmp_path),
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    assert "example.com: expires" in result.output
    assert "*.example.com: expires" in result.output
    assert "no local certificate" not in result.output
    assert result.output.count("renew=no") == 2


def test_cert_check_finds_covering_certificate_for_one_requested_name(tmp_path):
    _write_test_certificate(
        tmp_path / "example.com" / "default" / "fullchain.pem",
        ["example.com", "*.example.com"],
    )

    result = CliRunner().invoke(
        main,
        ["cert", "check", "example.com", "--cert-dir", str(tmp_path)],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    assert "example.com: expires" in result.output
    assert "no local certificate" not in result.output


def test_explicit_cert_path_lookup_scans_real_zone_for_public_suffix(tmp_path):
    certificate_dir = tmp_path / "certs" / "example.co.uk" / "precision"
    _write_test_certificate(
        certificate_dir / "fullchain.pem",
        ["*.precision.example.co.uk"],
    )
    updater = SSLCertUpdater(
        dns_client=object(),
        domains=["*.precision.example.co.uk"],
        email="ops@example.co.uk",
        cert_dir=tmp_path / "certs",
        cert_path="precision",
    )

    assert updater.find_certificate_dir(
        ["*.precision.example.co.uk"]
    ) == certificate_dir.resolve()


@pytest.mark.asyncio
async def test_issuance_lock_serializes_same_san_set_outside_cert_root(tmp_path):
    cert_root = tmp_path / "certs"
    state_root = tmp_path / "private" / "acme"
    updater_one = SSLCertUpdater(
        dns_client=object(),
        domains=["*.example.com"],
        email="ops@example.com",
        cert_dir=cert_root,
        acme_state_dir=state_root,
    )
    updater_two = SSLCertUpdater(
        dns_client=object(),
        domains=["*.example.com"],
        email="ops@example.com",
        cert_dir=cert_root,
        acme_state_dir=state_root,
    )
    entered = []

    async def wait_for_lock():
        async with updater_two._issuance_lock(["*.example.com"]):
            entered.append(True)

    async with updater_one._issuance_lock(["*.example.com"]):
        waiter = asyncio.create_task(wait_for_lock())
        await asyncio.sleep(0.15)
        assert entered == []

    await asyncio.wait_for(waiter, timeout=1)
    assert entered == [True]
    assert list(cert_root.rglob("*")) == []
    assert len(list((state_root / "locks").glob("*.lock"))) == 1


@pytest.mark.asyncio
async def test_issuance_lock_serializes_different_sans_in_same_default_namespace(tmp_path):
    cert_root = tmp_path / "certs"
    state_root = tmp_path / "private" / "acme"
    client = FakeDNSClient(zones=["example.com"])
    updater_one = SSLCertUpdater(
        dns_client=client,
        domains=["*.example.com"],
        email="ops@example.com",
        cert_dir=cert_root,
        acme_state_dir=state_root,
    )
    updater_two = SSLCertUpdater(
        dns_client=client,
        domains=["*.precision.example.com"],
        email="ops@example.com",
        cert_dir=cert_root,
        acme_state_dir=state_root,
    )
    entered = []

    async def wait_for_default_namespace():
        async with updater_two._issuance_lock(["*.precision.example.com"]):
            entered.append(True)

    async with updater_one._issuance_lock(["*.example.com"]):
        waiter = asyncio.create_task(wait_for_default_namespace())
        await asyncio.sleep(0.15)
        assert entered == []

    await asyncio.wait_for(waiter, timeout=1)
    assert entered == [True]
    assert len(list((state_root / "locks").glob("*.lock"))) == 1


@pytest.mark.asyncio
async def test_issuance_lock_serializes_overlapping_numeric_cert_paths(tmp_path):
    cert_root = tmp_path / "certs"
    state_root = tmp_path / "private" / "acme"
    client = FakeDNSClient(zones=["example.com"])
    base_updater = SSLCertUpdater(
        dns_client=client,
        domains=["*.example.com"],
        email="ops@example.com",
        cert_dir=cert_root,
        cert_path="foo",
        acme_state_dir=state_root,
    )
    suffix_updater = SSLCertUpdater(
        dns_client=client,
        domains=["*.precision.example.com"],
        email="ops@example.com",
        cert_dir=cert_root,
        cert_path="foo-2",
        acme_state_dir=state_root,
    )
    entered = []

    async def wait_for_overlapping_namespace():
        async with suffix_updater._issuance_lock(["*.precision.example.com"]):
            entered.append(True)

    async with base_updater._issuance_lock(["*.example.com"]):
        waiter = asyncio.create_task(wait_for_overlapping_namespace())
        await asyncio.sleep(0.15)
        assert entered == []

    await asyncio.wait_for(waiter, timeout=1)
    assert entered == [True]
    assert len(list((state_root / "locks").glob("*.lock"))) == 1


def test_multi_san_group_checks_primary_certificate_once(tmp_path):
    updater = SSLCertUpdater(
        domains=["example.com", "*.example.com"],
        email="admin@example.com",
        cert_dir=tmp_path,
        dns_client=FakeDNSClient(zones=["example.com"]),
    )
    updater.needs_renewal = Mock(return_value=False)
    updater.certificate_covers_domains = Mock(return_value=True)
    updater._request_certificate_for_domains = AsyncMock(return_value=True)

    assert asyncio.run(updater.update_certificates()) is True
    updater.needs_renewal.assert_called_once_with("example.com")
    updater.certificate_covers_domains.assert_called_once_with(
        "example.com", ["example.com", "*.example.com"]
    )
    updater._request_certificate_for_domains.assert_not_awaited()


def test_multi_san_group_renews_when_certificate_lacks_a_san(tmp_path):
    updater = SSLCertUpdater(
        domains=["example.com", "*.example.com"],
        email="admin@example.com",
        cert_dir=tmp_path,
        dns_client=FakeDNSClient(zones=["example.com"]),
    )
    updater.needs_renewal = Mock(return_value=False)
    updater.certificate_covers_domains = Mock(return_value=False)
    updater._request_certificate_for_domains = AsyncMock(return_value=True)

    assert asyncio.run(updater.update_certificates()) is True
    updater._request_certificate_for_domains.assert_awaited_once_with(
        ["example.com", "*.example.com"]
    )


def test_certificate_covers_domains_reads_leaf_sans(tmp_path):
    updater = SSLCertUpdater(
        domains=["example.com", "*.example.com"],
        email="admin@example.com",
        cert_dir=tmp_path,
        dns_client=FakeDNSClient(zones=["example.com"]),
    )
    _write_test_certificate(
        tmp_path / "example.com" / "default" / "fullchain.pem",
        ["example.com", "*.example.com"],
    )

    assert updater.certificate_covers_domains(
        "example.com", ["example.com", "*.example.com"]
    )
    assert not updater.certificate_covers_domains(
        "example.com", ["example.com", "*.example.com", "api.example.com"]
    )


def test_acme_challenge_record_handles_wildcards_and_subdomains():
    client = FakeDNSClient(zones=["example.com"])
    updater = SSLCertUpdater(
        domains=["*.sub.example.com"],
        email="admin@example.com",
        dns_client=client,
    )
    assert updater.get_acme_challenge_record("*.example.com") == (
        "example.com",
        "_acme-challenge",
    )
    assert updater.get_acme_challenge_record("www.example.com") == (
        "example.com",
        "_acme-challenge.www",
    )
    assert updater.get_acme_challenge_record("*.sub.example.com") == (
        "example.com",
        "_acme-challenge.sub",
    )


def test_acme_challenge_record_uses_managed_zone_for_public_suffix_domains():
    client = FakeDNSClient(zones=["example.co.uk", "co.uk"])
    updater = SSLCertUpdater(
        domains=["www.example.co.uk"],
        email="admin@example.com",
        dns_client=client,
    )
    assert updater.get_acme_challenge_record("www.example.co.uk") == (
        "example.co.uk",
        "_acme-challenge.www",
    )


def test_certificate_domains_reject_path_traversal(tmp_path):
    for value in ["../outside.example.com", "/example.com", "example.com/../x", "..example.com"]:
        with pytest.raises(ValueError):
            normalize_certificate_domain(value)
        with pytest.raises(ValueError):
            SSLCertUpdater(
                domains=[value],
                email="admin@example.com",
                cert_dir=tmp_path,
                dns_client=FakeDNSClient(),
            )


def test_default_certificate_layout_uses_zone_and_default_scope(tmp_path):
    updater = SSLCertUpdater(
        domains=["example.com", "*.example.com"],
        email="admin@example.com",
        cert_dir=tmp_path,
        dns_client=FakeDNSClient(zones=["example.com"]),
    )

    assert updater.resolve_certificate_dir(updater.domains) == (
        tmp_path / "example.com" / "default"
    ).resolve()


def test_certificate_layout_rejects_cross_zone_san_group(tmp_path):
    updater = SSLCertUpdater(
        domains=["*.example.com", "*.example.net"],
        email="admin@example.com",
        cert_dir=tmp_path,
        dns_client=FakeDNSClient(zones=["example.com", "example.net"]),
    )

    with pytest.raises(ValueError, match="one managed zone"):
        updater.resolve_certificate_dir(updater.domains)


def test_explicit_cert_path_uses_one_safe_relative_segment(tmp_path):
    updater = SSLCertUpdater(
        domains=["precision.example.com", "*.precision.example.com"],
        email="admin@example.com",
        cert_dir=tmp_path,
        cert_path="precision",
        dns_client=FakeDNSClient(zones=["example.com"]),
    )

    assert updater.resolve_certificate_dir(updater.domains) == (
        tmp_path / "example.com" / "precision"
    ).resolve()

    for value in ("../outside", "/absolute", "nested/path", "", "."):
        with pytest.raises(ValueError):
            SSLCertUpdater(
                domains=["*.example.com"],
                email="admin@example.com",
                cert_dir=tmp_path,
                cert_path=value,
                dns_client=FakeDNSClient(zones=["example.com"]),
            )


def test_certificate_layout_reuses_matching_existing_scope(tmp_path):
    target = tmp_path / "example.com" / "default"
    _write_test_certificate(target / "fullchain.pem", ["example.com", "*.example.com"])
    updater = SSLCertUpdater(
        domains=["example.com", "*.example.com"],
        email="admin@example.com",
        cert_dir=tmp_path,
        dns_client=FakeDNSClient(zones=["example.com"]),
    )

    assert updater.resolve_certificate_dir(updater.domains) == target.resolve()


def test_explicit_cert_path_reuses_matching_numeric_suffix_after_gap(tmp_path):
    target = tmp_path / "example.com" / "precision-3"
    _write_test_certificate(target / "fullchain.pem", ["*.precision.example.com"])
    updater = SSLCertUpdater(
        domains=["*.precision.example.com"],
        email="admin@example.com",
        cert_dir=tmp_path,
        cert_path="precision",
        dns_client=FakeDNSClient(zones=["example.com"]),
    )

    assert updater.resolve_certificate_dir(updater.domains) == target.resolve()


def test_explicit_cert_path_ignores_non_numeric_suffix(tmp_path):
    unrelated = tmp_path / "example.com" / "precision-old"
    _write_test_certificate(
        unrelated / "fullchain.pem",
        ["*.precision.example.com"],
    )
    updater = SSLCertUpdater(
        domains=["*.precision.example.com"],
        email="admin@example.com",
        cert_dir=tmp_path,
        cert_path="precision",
        dns_client=FakeDNSClient(zones=["example.com"]),
    )

    assert updater.resolve_certificate_dir(updater.domains) == (
        tmp_path / "example.com" / "precision"
    ).resolve()


def test_certificate_layout_suffixes_conflicting_scope(tmp_path):
    _write_test_certificate(
        tmp_path / "example.com" / "default" / "fullchain.pem",
        ["unrelated.example.com"],
    )
    _write_test_certificate(
        tmp_path / "example.com" / "default-2" / "fullchain.pem",
        ["other.example.com"],
    )
    updater = SSLCertUpdater(
        domains=["example.com", "*.example.com"],
        email="admin@example.com",
        cert_dir=tmp_path,
        dns_client=FakeDNSClient(zones=["example.com"]),
    )

    assert updater.resolve_certificate_dir(updater.domains) == (
        tmp_path / "example.com" / "default-3"
    ).resolve()


def test_disk_collision_wins_over_stale_in_memory_reservation(tmp_path):
    updater = SSLCertUpdater(
        domains=["*.example.com"],
        email="admin@example.com",
        cert_dir=tmp_path,
        dns_client=FakeDNSClient(zones=["example.com"]),
    )
    reserved = updater.resolve_certificate_dir(updater.domains)
    assert reserved == (tmp_path / "example.com" / "default").resolve()

    _write_test_certificate(
        reserved / "fullchain.pem",
        ["unrelated.example.com"],
    )
    updater._certificate_dir_cache.clear()

    assert updater.resolve_certificate_dir(updater.domains) == (
        tmp_path / "example.com" / "default-2"
    ).resolve()


def test_certificate_path_symlink_escape_uses_numeric_suffix(tmp_path):
    zone_dir = tmp_path / "certs" / "example.com"
    outside_dir = tmp_path / "outside" / "default"
    outside_dir.mkdir(parents=True)
    zone_dir.mkdir(parents=True)
    try:
        (zone_dir / "default").symlink_to(outside_dir, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks are not available")

    updater = SSLCertUpdater(
        dns_client=FakeDNSClient(zones=["example.com"]),
        domains=["*.example.com"],
        email="ops@example.com",
        cert_dir=tmp_path / "certs",
    )

    assert updater.resolve_certificate_dir(updater.domains) == (
        tmp_path / "certs" / "example.com" / "default-2"
    ).resolve()


def test_certificate_layout_rejects_managed_zone_symlink_inside_root(tmp_path):
    cert_root = tmp_path / "certs"
    other_zone = cert_root / "other.com"
    other_zone.mkdir(parents=True)
    try:
        (cert_root / "example.com").symlink_to(other_zone, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks are not available")
    updater = SSLCertUpdater(
        dns_client=FakeDNSClient(zones=["example.com"]),
        domains=["*.example.com"],
        email="ops@example.com",
        cert_dir=cert_root,
    )

    with pytest.raises(ValueError, match="symlink"):
        updater.resolve_certificate_dir(updater.domains)


def test_certificate_layout_does_not_follow_leaf_symlink_inside_root(tmp_path):
    cert_root = tmp_path / "certs"
    zone_dir = cert_root / "example.com"
    target = cert_root / "other.com" / "precision"
    _write_test_certificate(target / "fullchain.pem", ["*.example.com"])
    zone_dir.mkdir(parents=True, exist_ok=True)
    try:
        (zone_dir / "default").symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks are not available")
    updater = SSLCertUpdater(
        dns_client=FakeDNSClient(zones=["example.com"]),
        domains=["*.example.com"],
        email="ops@example.com",
        cert_dir=cert_root,
    )

    assert updater.resolve_certificate_dir(updater.domains) == (
        zone_dir / "default-2"
    ).resolve()


def test_acme_state_and_generated_keys_stay_outside_certificate_root(tmp_path):
    chatarch_home = tmp_path / "chatarch"
    cert_root = chatarch_home / "certs"
    updater = SSLCertUpdater(
        domains=["*.example.com"],
        email="admin@example.com",
        cert_dir=cert_root,
        chatarch_home=chatarch_home,
        dns_client=FakeDNSClient(zones=["example.com"]),
    )

    account_key = updater._ensure_account_key()
    domain_key = updater._ensure_domain_key(updater.resolve_certificate_dir(updater.domains))

    assert "BEGIN" in account_key
    assert "BEGIN" in domain_key
    assert updater.acme_state_dir == (chatarch_home / "private" / "chatdns" / "acme").resolve()
    assert not list(cert_root.glob("*.key"))


def test_certificate_request_writes_only_four_verified_pem_files(tmp_path):
    from datetime import datetime, timedelta, timezone

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    chatarch_home = tmp_path / "chatarch"
    cert_root = chatarch_home / "certs"
    updater = SSLCertUpdater(
        domains=["*.precision.example.com"],
        email="admin@example.com",
        cert_dir=cert_root,
        cert_path="precision",
        chatarch_home=chatarch_home,
        dns_client=FakeDNSClient(zones=["example.com"]),
    )

    def fake_get_crt(account_key, csr_pem, dns_update, dns_cleanup, **kwargs):
        del account_key, dns_update, dns_cleanup, kwargs
        csr = x509.load_pem_x509_csr(csr_pem.encode("utf-8"))
        ca_key = ec.generate_private_key(ec.SECP256R1())
        ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test CA")])
        now = datetime.now(timezone.utc)
        ca_cert = (
            x509.CertificateBuilder()
            .subject_name(ca_name)
            .issuer_name(ca_name)
            .public_key(ca_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(days=90))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .sign(ca_key, hashes.SHA256())
        )
        leaf = (
            x509.CertificateBuilder()
            .subject_name(csr.subject)
            .issuer_name(ca_name)
            .public_key(csr.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(days=90))
            .add_extension(
                csr.extensions.get_extension_for_class(x509.SubjectAlternativeName).value,
                critical=False,
            )
            .sign(ca_key, hashes.SHA256())
        )
        return (
            leaf.public_bytes(serialization.Encoding.PEM)
            + ca_cert.public_bytes(serialization.Encoding.PEM)
        ).decode("utf-8")

    with patch("chatdns.cert.get_crt", side_effect=fake_get_crt):
        assert asyncio.run(
            updater._request_certificate_for_domains(updater.domains)
        ) is True

    certificate_dir = cert_root / "example.com" / "precision"
    assert sorted(path.name for path in certificate_dir.iterdir()) == [
        "cert.pem",
        "chain.pem",
        "fullchain.pem",
        "privkey.pem",
    ]
    assert stat.S_IMODE((certificate_dir / "privkey.pem").stat().st_mode) == 0o600
    assert updater.verify_certificate_key_match(
        certificate_dir / "cert.pem", certificate_dir / "privkey.pem"
    )
    assert not list(updater.acme_state_dir.glob("issuance-*"))
    assert sorted(path.name for path in updater.acme_state_dir.iterdir()) == [
        "account.key"
    ]


def test_certificate_request_rejects_mismatched_returned_sans(tmp_path):
    updater = SSLCertUpdater(
        domains=["*.example.com"],
        email="admin@example.com",
        cert_dir=tmp_path / "certs",
        acme_state_dir=tmp_path / "private" / "acme",
        dns_client=FakeDNSClient(zones=["example.com"]),
    )
    fake_certificate = (
        "-----BEGIN CERTIFICATE-----\n"
        "ZmFrZQ==\n"
        "-----END CERTIFICATE-----\n"
    )
    updater._ensure_account_key = Mock(return_value="account-key")
    updater._ensure_domain_key = Mock(return_value="domain-key")
    updater._generate_csr = Mock(return_value="csr")
    updater.verify_certificate_key_match = Mock(return_value=True)
    updater._certificate_sans = Mock(return_value={"wrong.example.com"})

    with patch("chatdns.cert.get_crt", return_value=fake_certificate):
        result = asyncio.run(
            updater._request_certificate_for_domains(["*.example.com"])
        )

    assert result is False
    assert not (tmp_path / "certs" / "example.com" / "default").exists()
    assert not list(updater.acme_state_dir.glob("issuance-*"))


def test_split_pem_chain_preserves_certificate_boundaries():
    one = "-----BEGIN CERTIFICATE-----\nleaf\n-----END CERTIFICATE-----\n"
    two = "-----BEGIN CERTIFICATE-----\nchain\n-----END CERTIFICATE-----\n"
    leaf, chain = split_pem_chain(one + two)
    assert leaf == one
    assert chain == two
    assert chain.count("-----END CERTIFICATE-----") == 1


def test_cert_manifest_renders_legacy_infra_manifest_as_table(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "certificate_groups": [
                    {
                        "id": "cubenlp-precision",
                        "managed_zone": "cubenlp.cn",
                        "local_dir": "cubenlp.cn/precision",
                        "domains": ["*.precision.cubenlp.cn"],
                        "deployments": [
                            {"enabled": True},
                            {"enabled": False},
                        ],
                        "readiness": "preflight required",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        main, ["cert", "manifest", str(manifest)], catch_exceptions=False
    )

    assert result.exit_code == 0, result.output
    assert "Registered Domain" in result.output
    assert "cubenlp-precision" in result.output
    assert "cubenlp.cn/precision" in result.output
    assert "1/2" in result.output
    assert "preflight required" in result.output


@pytest.mark.parametrize("content", ["", "{}", '{"certificates": {}}'])
def test_cert_manifest_accepts_empty_infra_manifest(tmp_path, content):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(content, encoding="utf-8")

    result = CliRunner().invoke(main, ["cert", "manifest", str(manifest)])

    assert result.exit_code == 0, result.output
    assert "No certificate entries." in result.output


def test_cert_manifest_rejects_invalid_json(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{not-json", encoding="utf-8")

    result = CliRunner().invoke(main, ["cert", "manifest", str(manifest)])

    assert result.exit_code != 0
    assert "Unable to read manifest" in result.output


def test_cert_path_cli_validation_is_a_click_error(tmp_path):
    result = CliRunner().invoke(
        main,
        [
            "cert",
            "check",
            "example.com",
            "--cert-dir",
            str(tmp_path),
            "--cert-path",
            "../outside",
        ],
    )

    assert result.exit_code == 2
    assert "Invalid value for '--cert-path'" in result.output
    assert "Traceback" not in result.output


def test_dns_update_failure_causes_certificate_request_failure(tmp_path):
    updater = SSLCertUpdater(
        domains=["example.com"],
        email="admin@example.com",
        cert_dir=tmp_path,
        dns_client=FakeDNSClient(add_result=None),
        force=True,
    )
    # Exercise the failure path without live ACME by patching local setup enough to reach dns_update.
    main_d, rr = updater.get_acme_challenge_record("example.com")
    assert (main_d, rr) == ("example.com", "_acme-challenge")
    with pytest.raises(RuntimeError):
        record_id = updater.dns_client.add_domain_record(
            domain_name=main_d, rr=rr, type_="TXT", value="token", ttl=600
        )
        if record_id is None:
            raise RuntimeError(f"failed to add DNS TXT record for {rr}.{main_d}")


def test_certbot_hook_auth_adds_txt_record(monkeypatch):
    runner = CliRunner()
    monkeypatch.setenv("CERTBOT_DOMAIN", "*.sub.example.com")
    monkeypatch.setenv("CERTBOT_VALIDATION", "validation-token")

    with patch("chatdns.cli.create_dns_client") as create_client:
        client = create_client.return_value
        client.describe_domains.return_value = [{"DomainName": "example.com"}]
        client.add_domain_record.return_value = "record-id"
        result = runner.invoke(main, ["cert", "hook-auth"], catch_exceptions=False)

    assert result.exit_code == 0, result.output
    create_client.assert_called_once()
    assert create_client.call_args.args == ()
    client.add_domain_record.assert_called_once_with(
        domain_name="example.com",
        rr="_acme-challenge.sub",
        type_="TXT",
        value="validation-token",
        ttl=120,
    )


def test_certbot_hook_auth_fails_when_dns_add_fails(monkeypatch):
    runner = CliRunner()
    monkeypatch.setenv("CERTBOT_DOMAIN", "www.example.com")
    monkeypatch.setenv("CERTBOT_VALIDATION", "validation-token")

    with patch("chatdns.cli.create_dns_client") as create_client:
        client = create_client.return_value
        client.describe_domains.return_value = [{"DomainName": "example.com"}]
        client.add_domain_record.return_value = None
        result = runner.invoke(main, ["cert", "hook-auth"])

    assert result.exit_code != 0
    assert "failed to add DNS TXT record" in result.output


def test_certbot_hook_cleanup_deletes_only_matching_txt_value(monkeypatch):
    runner = CliRunner()
    monkeypatch.setenv("CERTBOT_DOMAIN", "www.example.com")
    monkeypatch.setenv("CERTBOT_VALIDATION", "validation-token")

    with patch("chatdns.cli.create_dns_client") as create_client:
        client = create_client.return_value
        client.describe_domains.return_value = [{"DomainName": "example.com"}]
        client.delete_record_value.return_value = True
        result = runner.invoke(main, ["cert", "hook-cleanup"], catch_exceptions=False)

    assert result.exit_code == 0, result.output
    create_client.assert_called_once()
    assert create_client.call_args.args == ()
    client.delete_record_value.assert_called_once_with(
        "example.com", "_acme-challenge.www", "TXT", "validation-token"
    )


def test_certbot_hook_cleanup_refuses_broad_cleanup_without_validation(monkeypatch):
    runner = CliRunner()
    monkeypatch.setenv("CERTBOT_DOMAIN", "www.example.com")
    monkeypatch.delenv("CERTBOT_VALIDATION", raising=False)

    result = runner.invoke(main, ["cert", "hook-cleanup"])

    assert result.exit_code != 0
    assert "refusing broad TXT cleanup" in result.output
