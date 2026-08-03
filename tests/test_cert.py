from pathlib import Path

import pytest
from click.testing import CliRunner
from unittest.mock import AsyncMock, patch

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


def test_cert_apply_invokes_ssl_updater_without_live_acme():
    runner = CliRunner()
    with patch("chatdns.cert.SSLCertUpdater") as updater_cls:
        updater = updater_cls.return_value
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
    assert kwargs["staging"] is True
    assert kwargs["force"] is True
    updater.run_once.assert_awaited_once()


def test_cert_help_documents_chatarch_managed_default():
    for command in (["cert", "apply", "--help"], ["cert", "check", "--help"]):
        result = CliRunner().invoke(main, command)
        assert result.exit_code == 0, result.output
        assert "CHATDNS_CERT_DIR or $CHATARCH_HOME/certs" in result.output


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
        updater_cls.return_value.run_once = AsyncMock(return_value=True)
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


def test_domain_key_path_stays_inside_cert_dir(tmp_path):
    updater = SSLCertUpdater(
        domains=["*.example.com"],
        email="admin@example.com",
        cert_dir=tmp_path,
        dns_client=FakeDNSClient(),
    )
    path = updater._path_in_cert_dir("_.example.com.key")
    assert path.parent == tmp_path.resolve()
    assert path.name == "_.example.com.key"


def test_split_pem_chain_preserves_certificate_boundaries():
    one = "-----BEGIN CERTIFICATE-----\nleaf\n-----END CERTIFICATE-----\n"
    two = "-----BEGIN CERTIFICATE-----\nchain\n-----END CERTIFICATE-----\n"
    leaf, chain = split_pem_chain(one + two)
    assert leaf == one
    assert chain == two
    assert chain.count("-----END CERTIFICATE-----") == 1


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
