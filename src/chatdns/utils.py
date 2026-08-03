from enum import Enum
from pathlib import Path
from typing import Union, Optional

from .aliyun import AliyunDNSClient
from .env import load_chatenv
from .tencent import TencentDNSClient

class DNSClientType(Enum):
    ALIYUN = 'aliyun'
    TENCENT = 'tencent'

def create_dns_client(
    dns_type: Optional[Union[DNSClientType, str]] = None,
    *,
    env_profile: str | None = None,
    chatarch_home: str | Path | None = None,
    **kwargs,
):
    """
    创建DNS客户端工厂方法

    Args:
        dns_type: DNS服务商类型 ('aliyun', 'tencent')。未提供时读取 ChatEnv 默认渠道。
        env_profile: 可选 ChatEnv profile 名称，用于切换对应服务商凭据。
        chatarch_home: 可选 CHATARCH_HOME 覆盖路径。
        **kwargs: 传递给客户端的参数
    """
    dns_type = load_chatenv(dns_type, env_profile=env_profile, home=chatarch_home)

    if dns_type == 'aliyun':
        return AliyunDNSClient(**kwargs)
    elif dns_type == 'tencent':
        return TencentDNSClient(**kwargs)
    else:
        raise ValueError(f"Unsupported DNS type: {dns_type}")
