import pytest
from click.testing import CliRunner
from unittest.mock import AsyncMock, patch

from chatdns.cli import main


def test_dns_help_commands():
    runner = CliRunner()
    for args in [
        ["--help"],
        ["list", "--help"],
        ["records", "--help"],
        ["delete", "--help"],
        ["ip", "--help"],
        ["ddns", "--help"],
        ["set", "--help"],
    ]:
        result = runner.invoke(main, args)
        assert result.exit_code == 0, result.output


def test_ddns_full_domain_argument_parsing():
    runner = CliRunner()
    with patch("chatdns.cli.DynamicIPUpdater") as mock_updater:
        instance = mock_updater.return_value
        instance.run_once = AsyncMock(return_value=True)

        result = runner.invoke(main, ["ddns", "test.example.com"])

    assert result.exit_code == 0, result.output
    call_args = mock_updater.call_args.kwargs
    assert call_args["domain_name"] == "example.com"
    assert call_args["rr"] == "test"


def test_set_prompts_when_required_args_missing(monkeypatch):
    runner = CliRunner()
    answers = {"domain": "example.com", "rr": "test", "value": "1.2.3.4"}

    monkeypatch.setattr("chatstyle.core.interactive.is_interactive_available", lambda: True)
    monkeypatch.setattr(
        "chatstyle.tui.prompt.ask_text",
        lambda label, default="", password=False, style=None: answers[label],
    )

    with patch("chatdns.cli.create_dns_client") as mock_factory:
        client = mock_factory.return_value
        client.set_record_value.return_value = True
        result = runner.invoke(main, ["set"], catch_exceptions=False)

    assert result.exit_code == 0
    client.set_record_value.assert_called_once_with("example.com", "test", "A", "1.2.3.4", 600)


def test_records_full_domain_parsing():
    runner = CliRunner()
    with patch("chatdns.cli.create_dns_client") as mock_factory:
        client = mock_factory.return_value
        client.describe_domain_records.return_value = []
        result = runner.invoke(main, ["records", "test.example.com"])

    assert result.exit_code == 0, result.output
    client.describe_domain_records.assert_called_once_with(
        "example.com", subdomain="test", record_type=None
    )


def test_delete_requires_yes_when_interaction_disabled():
    runner = CliRunner()
    with patch("chatdns.cli.create_dns_client") as mock_factory:
        client = mock_factory.return_value
        client.describe_domain_records.return_value = [
            {"RecordId": "1", "RR": "test", "Type": "A", "Value": "1.2.3.4", "TTL": 600}
        ]
        result = runner.invoke(main, ["delete", "test.example.com", "-t", "A", "-I"])

    assert result.exit_code != 0
    assert "非交互环境请传入 --yes" in result.output
    client.delete_domain_record.assert_not_called()


def test_delete_with_yes_deletes_matching_record():
    runner = CliRunner()
    with patch("chatdns.cli.create_dns_client") as mock_factory:
        client = mock_factory.return_value
        client.describe_domain_records.return_value = [
            {"RecordId": "1", "RR": "test", "Type": "A", "Value": "1.2.3.4", "TTL": 600},
            {"RecordId": "2", "RR": "test", "Type": "A", "Value": "5.6.7.8", "TTL": 600},
        ]
        client.delete_domain_record.return_value = True
        result = runner.invoke(
            main,
            ["delete", "test.example.com", "-t", "A", "-v", "1.2.3.4", "--yes", "-I"],
        )

    assert result.exit_code == 0, result.output
    client.delete_domain_record.assert_called_once_with("1", domain_name="example.com")
    assert "删除成功: 1 条记录" in result.output


def test_ip_public(monkeypatch):
    runner = CliRunner()

    async def fake_public_ip():
        return "203.0.113.10"

    monkeypatch.setattr("chatdns.cli._get_public_ip", fake_public_ip)
    result = runner.invoke(main, ["ip"])

    assert result.exit_code == 0
    assert "203.0.113.10" in result.output
