import chatdns


def test_version():
    assert chatdns.__version__ == "0.1.0"


def test_public_api_exports_dns_helpers():
    assert chatdns.DNSClient is not None
    assert chatdns.AliyunDNSClient is not None
    assert chatdns.TencentDNSClient is not None
    assert chatdns.DynamicIPUpdater is not None
    assert chatdns.create_dns_client is not None
    assert chatdns.split_full_domain("a.b.example.com") == ("example.com", "a.b")
