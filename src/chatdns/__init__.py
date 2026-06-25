"""ChatDNS package."""

from .base import DNSClient
from .aliyun import AliyunDNSClient
from .tencent import TencentDNSClient
from .ip_updater import DynamicIPUpdater
from .utils import DNSClientType, create_dns_client
from .domain_utils import split_full_domain

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "DNSClient",
    "AliyunDNSClient",
    "TencentDNSClient",
    "DynamicIPUpdater",
    "DNSClientType",
    "create_dns_client",
    "split_full_domain",
]
