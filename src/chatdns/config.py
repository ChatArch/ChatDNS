"""ChatDNS provider configuration helpers."""

from __future__ import annotations

from typing import Any

from chatenv.fields import BaseEnvConfig as _BaseEnvConfig, EnvField as _EnvField


BaseEnvConfig: Any = _BaseEnvConfig
EnvField: Any = _EnvField


class AliyunConfig(BaseEnvConfig):
    """Alibaba Cloud DNS configuration."""

    _title = "Alibaba Cloud (Aliyun) DNS Configuration"
    _aliases = ["ali", "aliyun", "alidns"]
    _storage_dir = "Aliyun"


setattr(
    AliyunConfig,
    "ALIBABA_CLOUD_ACCESS_KEY_ID",
    EnvField("ALIBABA_CLOUD_ACCESS_KEY_ID", desc="Access Key ID", is_sensitive=True),
)
setattr(
    AliyunConfig,
    "ALIBABA_CLOUD_ACCESS_KEY_SECRET",
    EnvField("ALIBABA_CLOUD_ACCESS_KEY_SECRET", desc="Access Key Secret", is_sensitive=True),
)
setattr(
    AliyunConfig,
    "ALIBABA_CLOUD_REGION_ID",
    EnvField("ALIBABA_CLOUD_REGION_ID", default="cn-hangzhou", desc="Region ID"),
)


class TencentConfig(BaseEnvConfig):
    """Tencent Cloud DNSPod configuration."""

    _title = "Tencent Cloud DNS Configuration"
    _aliases = ["tencent", "tx", "tencent-dns"]
    _storage_dir = "Tencent"


setattr(
    TencentConfig,
    "TENCENT_SECRET_ID",
    EnvField("TENCENT_SECRET_ID", desc="Secret ID", is_sensitive=True),
)
setattr(
    TencentConfig,
    "TENCENT_SECRET_KEY",
    EnvField("TENCENT_SECRET_KEY", desc="Secret Key", is_sensitive=True),
)
setattr(
    TencentConfig,
    "TENCENT_REGION_ID",
    EnvField("TENCENT_REGION_ID", default="ap-guangzhou", desc="Region ID"),
)


__all__ = ["AliyunConfig", "TencentConfig"]
