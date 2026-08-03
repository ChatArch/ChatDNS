"""ChatEnv loading helpers for ChatDNS."""

from __future__ import annotations

import os
from pathlib import Path
from string import Template
from typing import Any

from chatenv.paths import get_paths
from chatenv.store import EnvStore

from .config import AliyunConfig, ChatDNSConfig, TencentConfig

PROVIDER_CONFIGS = {
    "aliyun": AliyunConfig,
    "ali": AliyunConfig,
    "alidns": AliyunConfig,
    "tencent": TencentConfig,
    "tx": TencentConfig,
    "tencent-dns": TencentConfig,
}
PROVIDER_NAMES = {
    AliyunConfig: "aliyun",
    TencentConfig: "tencent",
}
DEFAULT_PROVIDER = "aliyun"


def normalize_provider(provider: Any | None) -> str:
    """Return the canonical provider name accepted by ChatDNS."""
    if provider is None:
        return DEFAULT_PROVIDER
    value = getattr(provider, "value", provider)
    normalized = str(value).strip().lower()
    config_cls = PROVIDER_CONFIGS.get(normalized)
    if config_cls is None:
        choices = ", ".join(sorted({"aliyun", "tencent"}))
        raise ValueError(f"Unsupported DNS provider: {provider}. Expected one of: {choices}")
    return PROVIDER_NAMES[config_cls]


def _load_config(store: EnvStore, config_cls: type, profile: str | None = None) -> dict[str, str]:
    if profile is None:
        values = store.load_active(config_cls)
    else:
        path = store.profile_path(config_cls, profile)
        if not path.exists():
            raise FileNotFoundError(path)
        values = store.load_profile(config_cls, profile)
    config_cls.load_from_sources(env_values=values)
    return values


def _maybe_load_profile(store: EnvStore, config_cls: type, profile: str) -> dict[str, str]:
    path = store.profile_path(config_cls, profile)
    if not path.exists():
        return {}
    values = store.load_profile(config_cls, profile)
    config_cls.load_from_sources(env_values=values)
    return values


def load_chatdns_config(
    *,
    env_profile: str | None = None,
    home: str | Path | None = None,
) -> dict[str, str]:
    """Load ChatDNS defaults without requiring provider credentials."""
    paths = get_paths(home)
    store = EnvStore(paths.envs_dir)
    values = _load_config(store, ChatDNSConfig)
    if env_profile:
        values.update(_maybe_load_profile(store, ChatDNSConfig, env_profile))
    return values


def resolve_cert_dir(
    cert_dir: str | Path | None = None,
    *,
    home: str | Path | None = None,
) -> Path:
    """Resolve explicit, ChatEnv-managed, or ChatArch-default certificate storage."""
    selected = cert_dir if cert_dir is not None else ChatDNSConfig.CHATDNS_CERT_DIR.value
    if selected is not None and str(selected).strip():
        variables = dict(os.environ)
        variables["CHATARCH_HOME"] = str(get_paths(home).home_dir)
        try:
            expanded = Template(str(selected)).substitute(variables)
        except (KeyError, ValueError) as exc:
            raise ValueError(
                f"Unable to expand certificate directory {selected!r}: {exc}"
            ) from exc
        return Path(expanded).expanduser()
    return get_paths(home).home_dir / "certs"


def load_chatenv(
    provider: Any | None = None,
    *,
    env_profile: str | None = None,
    home: str | Path | None = None,
) -> str:
    """Load ChatDNS ChatEnv files and return the selected DNS provider.

    Active profiles are loaded by default. When ``env_profile`` is supplied,
    the named profile is applied to the selected provider credentials.
    """
    paths = get_paths(home)
    store = EnvStore(paths.envs_dir)

    load_chatdns_config(env_profile=env_profile, home=home)
    _load_config(store, AliyunConfig)
    _load_config(store, TencentConfig)

    selected_provider = normalize_provider(provider or ChatDNSConfig.CHATDNS_PROVIDER.value)

    if env_profile:
        provider_config = PROVIDER_CONFIGS[selected_provider]
        try:
            _load_config(store, provider_config, env_profile)
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                f"ChatEnv profile '{env_profile}' not found for {provider_config.get_storage_name()}"
            ) from exc

    return selected_provider
