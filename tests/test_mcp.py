import pytest

from chatdns import mcp


@pytest.fixture(autouse=True)
def isolated_chatenv_home(monkeypatch, tmp_path):
    monkeypatch.setenv("CHATARCH_HOME", str(tmp_path))
    for key in ("CHATDNS_DNS_PROVIDER", "DNS_PROVIDER", "DEFAULT_DNS_PROVIDER", "CHATTOOL_DNS_PROVIDER"):
        monkeypatch.delenv(key, raising=False)


def test_mcp_registers_dns_tools():
    registered = []

    class FakeMCP:
        def tool(self, name, tags=None):
            def decorator(func):
                registered.append((name, tuple(tags or ()), func.__name__))
                return func
            return decorator

    mcp.register(FakeMCP())

    names = {item[0] for item in registered}
    assert names == {
        "dns_list_domains",
        "dns_get_records",
        "dns_add_record",
        "dns_delete_record",
        "dns_ddns_update",
    }
    assert ("dns_list_domains", ("dns", "read"), "list_domains") in registered


def test_get_provider_prefers_argument(monkeypatch):
    monkeypatch.setenv("DNS_PROVIDER", "aliyun")
    assert mcp._get_provider("tencent") == "tencent"


def test_get_provider_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("DNS_PROVIDER", "tencent")
    assert mcp._get_provider() == "tencent"
