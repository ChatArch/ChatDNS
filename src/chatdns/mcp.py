"""MCP tool registration for ChatDNS."""

from __future__ import annotations

from typing import Any

try:
    from fastmcp import FastMCP
except ImportError:  # pragma: no cover - optional MCP dependency
    FastMCP = Any  # type: ignore[misc,assignment]

from . import DynamicIPUpdater, create_dns_client
from .env import load_chatenv
from .logging_utils import setup_logger

logger = setup_logger("mcp_chatdns", log_level="INFO")


def _get_provider(provider: str | None = None) -> str:
    """Determine DNS provider from argument, environment, or ChatEnv."""
    return load_chatenv(provider)


def list_domains(provider: str | None = None) -> list[dict] | str:
    """List all domains under the DNS account."""
    try:
        client = create_dns_client(_get_provider(provider), logger=logger)
        return client.describe_domains()
    except ImportError as exc:
        logger.error("Dependency missing: %s", exc)
        return f"Error: {exc}"
    except Exception as exc:  # pragma: no cover - provider SDK/runtime errors
        logger.error("Error listing domains: %s", exc)
        return f"Error: {exc}"


def get_records(domain: str, rr: str | None = None, provider: str | None = None) -> list[dict] | str:
    """Get DNS records for a domain."""
    try:
        client = create_dns_client(_get_provider(provider), logger=logger)
        if rr:
            return client.describe_subdomain_records(domain, rr)
        return client.describe_domain_records(domain)
    except ImportError as exc:
        logger.error("Dependency missing: %s", exc)
        return f"Error: {exc}"
    except Exception as exc:  # pragma: no cover - provider SDK/runtime errors
        logger.error("Error getting records: %s", exc)
        return f"Error: {exc}"


def add_record(
    domain: str,
    rr: str,
    record_type: str,
    value: str,
    ttl: int = 600,
    provider: str | None = None,
) -> str:
    """Add a new DNS record and return its provider record ID."""
    try:
        client = create_dns_client(_get_provider(provider), logger=logger)
        record_id = client.add_domain_record(domain, rr, record_type, value, ttl)
        return str(record_id)
    except ImportError as exc:
        logger.error("Dependency missing: %s", exc)
        return f"Error: {exc}"
    except Exception as exc:  # pragma: no cover - provider SDK/runtime errors
        logger.error("Error adding record: %s", exc)
        return f"Error: {exc}"


def delete_record(
    domain: str,
    rr: str,
    record_type: str | None = None,
    provider: str | None = None,
) -> bool | str:
    """Delete DNS records for a host record, optionally filtered by type."""
    try:
        client = create_dns_client(_get_provider(provider), logger=logger)
        return client.delete_subdomain_records(domain, rr, type_=record_type)
    except ImportError as exc:
        logger.error("Dependency missing: %s", exc)
        return f"Error: {exc}"
    except Exception as exc:  # pragma: no cover - provider SDK/runtime errors
        logger.error("Error deleting record: %s", exc)
        return f"Error: {exc}"


async def ddns_update(
    domain: str,
    rr: str,
    ip_type: str = "public",
    provider: str | None = None,
) -> bool | str:
    """Perform one DDNS update using the current public or local IP."""
    try:
        updater = DynamicIPUpdater(
            domain_name=domain,
            rr=rr,
            dns_type=_get_provider(provider),
            ip_type=ip_type,
            logger=logger,
        )
        return await updater.run_once()
    except ImportError as exc:
        logger.error("Dependency missing: %s", exc)
        return f"Error: {exc}"
    except Exception as exc:  # pragma: no cover - provider SDK/runtime errors
        logger.error("Error in DDNS update: %s", exc)
        return f"Error: {exc}"


def register(mcp: FastMCP) -> None:
    """Register ChatDNS tools with an MCP server."""
    mcp.tool(name="dns_list_domains", tags=["dns", "read"])(list_domains)
    mcp.tool(name="dns_get_records", tags=["dns", "read"])(get_records)
    mcp.tool(name="dns_add_record", tags=["dns", "write"])(add_record)
    mcp.tool(name="dns_delete_record", tags=["dns", "write"])(delete_record)
    mcp.tool(name="dns_ddns_update", tags=["dns", "write"])(ddns_update)
