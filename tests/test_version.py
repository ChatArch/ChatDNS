import chatdns
from importlib.metadata import entry_points

from click.testing import CliRunner

from chatdns.cli import main


def test_version():
    assert chatdns.__version__ == "0.1.1"


def test_cli_version():
    result = CliRunner().invoke(main, ["--version"])
    assert result.exit_code == 0, result.output
    assert "ChatDNS, version 0.1.1" in result.output


def test_chatenv_config_entry_point_registered():
    entries = [ep for ep in entry_points(group="chatenv.configs") if ep.name == "chatdns"]
    assert len(entries) == 1
    assert entries[0].value == "chatdns.config"


def test_chatenv_config_classes():
    from chatdns.config import AliyunConfig, ChatDNSConfig, TencentConfig

    assert ChatDNSConfig._aliases == ["chatdns", "dns"]
    assert ChatDNSConfig._storage_dir == "ChatDNS"
    assert ChatDNSConfig.CHATDNS_PROVIDER.default == "aliyun"
    assert AliyunConfig._aliases == ["ali", "aliyun", "alidns"]
    assert TencentConfig._aliases == ["tencent", "tx", "tencent-dns"]
    assert AliyunConfig._storage_dir == "Aliyun"
    assert TencentConfig._storage_dir == "Tencent"
    assert AliyunConfig.ALIBABA_CLOUD_REGION_ID.value == "cn-hangzhou"
    assert TencentConfig.TENCENT_REGION_ID.value == "ap-guangzhou"
    assert AliyunConfig.ALIBABA_CLOUD_ACCESS_KEY_SECRET.is_sensitive is True
    assert TencentConfig.TENCENT_SECRET_KEY.is_sensitive is True


def test_public_api_exports_dns_helpers():
    assert chatdns.DNSClient is not None
    assert chatdns.AliyunDNSClient is not None
    assert chatdns.TencentDNSClient is not None
    assert chatdns.DynamicIPUpdater is not None
    assert chatdns.SSLCertUpdater is not None
    assert chatdns.create_dns_client is not None
    assert chatdns.split_full_domain("a.b.example.com") == ("example.com", "a.b")
