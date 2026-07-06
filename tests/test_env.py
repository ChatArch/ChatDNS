from pathlib import Path

import pytest

from chatdns.config import AliyunConfig, ChatDNSConfig, TencentConfig
from chatdns.env import load_chatenv


def _write_env(home: Path, storage: str, filename: str, content: str) -> None:
    path = home / "envs" / storage / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.fixture(autouse=True)
def clear_provider_env(monkeypatch):
    for key in (
        "CHATARCH_HOME",
        "CHATDNS_PROVIDER",
    ):
        monkeypatch.delenv(key, raising=False)


def test_load_chatenv_uses_chatdns_default_provider(tmp_path):
    _write_env(tmp_path, "ChatDNS", ".env", "CHATDNS_PROVIDER='tencent'\n")
    _write_env(
        tmp_path,
        "Tencent",
        ".env",
        "TENCENT_SECRET_ID='sid'\nTENCENT_SECRET_KEY='skey'\nTENCENT_REGION_ID='ap-shanghai'\n",
    )

    provider = load_chatenv(home=tmp_path)

    assert provider == "tencent"
    assert ChatDNSConfig.CHATDNS_PROVIDER.value == "tencent"
    assert TencentConfig.TENCENT_SECRET_ID.value == "sid"
    assert TencentConfig.TENCENT_SECRET_KEY.value == "skey"
    assert TencentConfig.TENCENT_REGION_ID.value == "ap-shanghai"


def test_load_chatenv_named_profile_overrides_selected_provider(tmp_path):
    _write_env(tmp_path, "ChatDNS", ".env", "CHATDNS_PROVIDER='aliyun'\n")
    _write_env(
        tmp_path,
        "Aliyun",
        ".env",
        "ALIBABA_CLOUD_ACCESS_KEY_ID='active-id'\nALIBABA_CLOUD_ACCESS_KEY_SECRET='active-secret'\n",
    )
    _write_env(
        tmp_path,
        "Aliyun",
        "work.env",
        "ALIBABA_CLOUD_ACCESS_KEY_ID='work-id'\nALIBABA_CLOUD_ACCESS_KEY_SECRET='work-secret'\nALIBABA_CLOUD_REGION_ID='cn-shanghai'\n",
    )

    provider = load_chatenv(provider="aliyun", env_profile="work", home=tmp_path)

    assert provider == "aliyun"
    assert AliyunConfig.ALIBABA_CLOUD_ACCESS_KEY_ID.value == "work-id"
    assert AliyunConfig.ALIBABA_CLOUD_ACCESS_KEY_SECRET.value == "work-secret"
    assert AliyunConfig.ALIBABA_CLOUD_REGION_ID.value == "cn-shanghai"


def test_load_chatenv_reports_missing_named_provider_profile(tmp_path):
    _write_env(tmp_path, "ChatDNS", ".env", "CHATDNS_PROVIDER='tencent'\n")

    with pytest.raises(FileNotFoundError, match="profile 'prod' not found for Tencent"):
        load_chatenv(env_profile="prod", home=tmp_path)


def test_load_chatenv_uses_chatenv_env_field(monkeypatch, tmp_path):
    monkeypatch.setenv("CHATDNS_PROVIDER", "tencent")

    assert load_chatenv(home=tmp_path) == "tencent"
