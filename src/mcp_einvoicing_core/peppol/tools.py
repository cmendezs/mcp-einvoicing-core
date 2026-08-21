"""Shared Peppol tool plugin for mcp-einvoicing-core.

Mountable via ``EInvoicingMCPServer.register_plugin()``, matching the
``ToolRegistrationFn`` convention in ``mcp_einvoicing_core.base_server``.
Wraps the existing ``PeppolSMPClient`` / ``PeppolTransmitter`` primitives as
FastMCP-native tools so country packages stop reimplementing the same
lookup/send wrappers (see CORE-PEPPOL-TOOLS-1, which absorbs DE's
``peppol_check``/``peppol_send`` and BE's ``check_peppol_participant_be``).

Country packages mount this plugin and supply only a national identifier
adapter: a small callable that normalizes a bare national number (e.g. a
VAT number) into a Peppol ``"<scheme>:<value>"`` participant ID. This is the
only per-country Peppol code that remains.

Usage (country package)::

    from mcp_einvoicing_core.peppol.tools import register_peppol_tools

    def _be_id_adapter(identifier: str) -> str:
        if ":" in identifier:
            return identifier
        return f"0208:{normalize_vat_be(identifier)[2:]}"  # KBO/BCE scheme

    mcp.register_plugin(
        lambda m: register_peppol_tools(m, id_adapter=_be_id_adapter), "peppol"
    )

A country package with no national numbering scheme to adapt (e.g. one that
always works with full participant IDs) can mount the plugin without an
adapter and get `default_id_adapter`, which requires callers to already pass
a scheme-qualified identifier.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from mcp_einvoicing_core.peppol import (
    PEPPOL_BIS_BILLING_30,
    PeppolEnvironment,
    PeppolParticipantId,
    PeppolSMPClient,
    codelists,
    resolve_naptr,
)

logger = logging.getLogger(__name__)

IdentifierAdapter = Callable[[str], str]
"""Normalizes a bare national identifier into a Peppol '<scheme>:<value>' string.

Receives the raw identifier as supplied by the tool caller. Returns a string
already in "<scheme>:<value>" form (parseable by
`PeppolParticipantId.parse()`), or raises ValueError if the identifier
cannot be normalized. Adapters should pass already scheme-qualified
identifiers (those containing ":") straight through unchanged.
"""


def default_id_adapter(identifier: str) -> str:
    """Default identifier adapter: require a full '<scheme>:<value>' string.

    Used when a country package mounts the Peppol plugin without supplying
    its own adapter. Raises ValueError if *identifier* has no ':' separator,
    since there is no way to guess the ICD scheme without national context.
    """
    if ":" not in identifier:
        raise ValueError(
            f"Identifier {identifier!r} is not a Peppol participant ID "
            "('<scheme>:<value>', e.g. '0208:0123456789'). This server has "
            "no national identifier adapter configured to normalize bare "
            "numbers; pass a full scheme-qualified identifier instead."
        )
    return identifier


def _environment_from_str(environment: str) -> PeppolEnvironment:
    return (
        PeppolEnvironment.TEST
        if environment == "test"
        else PeppolEnvironment.PRODUCTION
    )


def register_peppol_tools(
    mcp: Any,
    *,
    id_adapter: Optional[IdentifierAdapter] = None,
) -> None:
    """Register the shared Peppol tool surface onto *mcp*.

    Args:
        mcp: A FastMCP instance (the `.mcp` attribute of an
            `EInvoicingMCPServer`, or a bare `FastMCP()`).
        id_adapter: Normalizes a bare national identifier into a Peppol
            "<scheme>:<value>" participant ID. Defaults to
            `default_id_adapter` (requires a scheme-qualified identifier).

    Registers:
        peppol_lookup_participant:        registration + supported document types
        peppol_get_service_endpoint:      AS4 endpoint for a specific doc type
        resolve_peppol_dns:               standalone DNS (SML) diagnostic
        peppol_send:                      transmit a UBL/CII invoice via AS4
        list_participant_id_schemes:      OpenPeppol eDEC ICD scheme codelist
        list_document_type_ids:           OpenPeppol eDEC document type codelist
        list_process_ids:                 OpenPeppol eDEC process codelist
        list_spis_use_case_ids:           OpenPeppol eDEC SPIS use case codelist
        check_document_type_id_in_codelist:      lookup by (scheme, value)
        check_process_id_in_codelist:            lookup by (scheme, value)
        check_participant_id_scheme_in_codelist: lookup by ICD code
        get_peppol_codelist_version:      configured eDEC release version(s)

    The five list/check tool families require EINVOICING_PEPPOL_CODELIST_DIR
    to be set (a local, deployer-supplied copy of the OpenPeppol eDEC code
    lists, not bundled with this package). See
    `mcp_einvoicing_core.peppol.codelists` for why.
    """
    adapter = id_adapter or default_id_adapter

    async def peppol_lookup_participant(
        identifier: str,
        environment: str = "production",
    ) -> dict[str, Any]:
        """Check whether a business is registered on the Peppol network.

        Performs a DNS-over-HTTPS U-NAPTR lookup followed by an SMP
        service-group request to determine registration status and the list
        of supported document type identifiers.

        Args:
            identifier: Peppol participant ID ("<scheme>:<value>") or a bare
                national identifier this server knows how to adapt (e.g. a
                VAT number, if a national identifier adapter is configured).
            environment: "production" or "test".
        """
        try:
            participant_id_str = adapter(identifier)
            participant_id = PeppolParticipantId.parse(participant_id_str)
        except ValueError as exc:
            return {
                "is_registered": False,
                "participant_id": identifier,
                "error": str(exc),
            }

        client = PeppolSMPClient(environment=_environment_from_str(environment))
        result = await client.lookup_participant(participant_id)
        return result.to_dict()

    async def peppol_get_service_endpoint(
        identifier: str,
        document_type_id: str = PEPPOL_BIS_BILLING_30,
        environment: str = "production",
    ) -> dict[str, Any]:
        """Fetch the AS4 endpoint for a Peppol participant's document type.

        Resolves the SMP hostname via DNS, then fetches service metadata for
        *document_type_id*. If the SMP returns a redirect, the result's
        `redirect_url` is set and `endpoint_url` is None; callers must not
        follow more than one redirect hop (SMP 1.4.0 §3.2).

        Args:
            identifier: Peppol participant ID or adaptable national identifier.
            document_type_id: Peppol document type identifier URN (default:
                BIS Billing 3.0 invoice).
            environment: "production" or "test".
        """
        try:
            participant_id_str = adapter(identifier)
            participant_id = PeppolParticipantId.parse(participant_id_str)
        except ValueError as exc:
            return {
                "document_type_id": document_type_id,
                "endpoint_url": None,
                "error": str(exc),
            }

        client = PeppolSMPClient(environment=_environment_from_str(environment))
        service = await client.get_service_endpoint(participant_id, document_type_id)
        return {
            "document_type_id": service.document_type_id,
            "endpoint_url": service.endpoint_url,
            "transport_profile": service.transport_profile,
            "process_id": service.process_id,
            "certificate": service.certificate,
            "redirect_url": service.redirect_url,
        }

    async def resolve_peppol_dns(
        identifier: str,
        environment: str = "production",
    ) -> dict[str, Any]:
        """Resolve the SMP hostname for a Peppol participant via DNS only.

        Performs the raw U-NAPTR (SML) lookup without fetching the SMP
        service group, useful for diagnosing whether a participant is
        registered in the SML independently of SMP reachability.

        Args:
            identifier: Peppol participant ID or adaptable national identifier.
            environment: "production" or "test".
        """
        try:
            participant_id_str = adapter(identifier)
            participant_id = PeppolParticipantId.parse(participant_id_str)
        except ValueError as exc:
            return {"participant_id": identifier, "smp_hostname": None, "error": str(exc)}

        env = _environment_from_str(environment)
        sml_domain = (
            "edelivery.tech.ec.europa.eu"
            if env == PeppolEnvironment.PRODUCTION
            else "acc.edelivery.tech.ec.europa.eu"
        )
        dns_name = participant_id.dns_name(sml_domain)
        try:
            hostname = await resolve_naptr(dns_name)
        except Exception as exc:
            return {
                "participant_id": str(participant_id),
                "dns_name": dns_name,
                "smp_hostname": None,
                "error": f"{type(exc).__name__}: {exc}",
            }
        return {
            "participant_id": str(participant_id),
            "dns_name": dns_name,
            "smp_hostname": hostname,
            "is_registered": hostname is not None,
        }

    async def peppol_send(
        invoice_xml_base64: str,
        recipient_identifier: str,
        sender_id: str,
        certificate_path: str,
        private_key_path: str,
        private_key_password: str = "",
        document_type_id: str = PEPPOL_BIS_BILLING_30,
        environment: str = "test",
    ) -> dict[str, Any]:
        """Send a UBL/CII invoice to a Peppol participant via AS4.

        Looks up the recipient's AS4 endpoint (SMP), builds the ebMS3/AS4
        envelope, and transmits it using the supplied signing credentials.

        Args:
            invoice_xml_base64: Base64-encoded UBL or CII invoice XML.
            recipient_identifier: Peppol participant ID or adaptable
                national identifier of the receiver.
            sender_id: Peppol AP identifier of the sender.
            certificate_path: Path to the PEM-encoded signing certificate.
            private_key_path: Path to the PEM-encoded private key.
            private_key_password: Optional password for the private key.
            document_type_id: Peppol document type identifier URN (default:
                BIS Billing 3.0 invoice).
            environment: "production" or "test".
        """
        import base64  # noqa: PLC0415

        from mcp_einvoicing_core.exceptions import EInvoicingError, PlatformError  # noqa: PLC0415
        from mcp_einvoicing_core.peppol.transport import (  # noqa: PLC0415
            AS4Credentials,
            PeppolTransmitter,
        )

        try:
            recipient_id_str = adapter(recipient_identifier)
            recipient = PeppolParticipantId.parse(recipient_id_str)
        except ValueError as exc:
            return {"status": "error", "error": str(exc)}

        try:
            invoice_xml = base64.b64decode(invoice_xml_base64)
        except (ValueError, TypeError) as exc:
            return {"status": "error", "error": f"Invalid base64 invoice XML: {exc}"}

        credentials = AS4Credentials(
            certificate_path=certificate_path,
            private_key_path=private_key_path,
            private_key_password=private_key_password or None,
        )

        transmitter = PeppolTransmitter(
            credentials=credentials,
            environment=_environment_from_str(environment),
            document_type_id=document_type_id,
        )

        try:
            receipt = await transmitter.transmit(
                invoice_xml=invoice_xml,
                recipient_id=recipient,
                sender_id=sender_id,
            )
        except (PlatformError, EInvoicingError) as exc:
            return {"status": "error", "error": str(exc)}

        return {
            "status": "delivered",
            "message_id": receipt.ref_to_message_id,
            "receipt_message_id": receipt.message_id,
            "recipient_id": str(recipient),
        }

    def list_participant_id_schemes(active_only: bool = True) -> dict[str, Any]:
        """List Peppol participant identifier (ICD) schemes from the OpenPeppol eDEC code list.

        Requires EINVOICING_PEPPOL_CODELIST_DIR to point at a local copy of
        the eDEC "Participant Identifier Schemes" GeneriCode export (not
        bundled with this package, no confirmed redistribution rights, see
        `mcp_einvoicing_core.peppol.codelists` module docstring).

        Args:
            active_only: When True (default), omit deprecated/removed entries.
        """
        try:
            rows = codelists.list_participant_id_schemes(active_only=active_only)
        except codelists.CodelistNotConfiguredError as exc:
            return {"configured": False, "error": str(exc), "schemes": []}
        return {"configured": True, "schemes": rows}

    def list_document_type_ids(active_only: bool = True) -> dict[str, Any]:
        """List Peppol document type identifiers from the OpenPeppol eDEC code list.

        Requires EINVOICING_PEPPOL_CODELIST_DIR (see `list_participant_id_schemes`).

        Args:
            active_only: When True (default), omit deprecated/removed entries.
        """
        try:
            rows = codelists.list_document_type_ids(active_only=active_only)
        except codelists.CodelistNotConfiguredError as exc:
            return {"configured": False, "error": str(exc), "document_types": []}
        return {"configured": True, "document_types": rows}

    def list_process_ids(active_only: bool = True) -> dict[str, Any]:
        """List Peppol process identifiers from the OpenPeppol eDEC code list.

        Requires EINVOICING_PEPPOL_CODELIST_DIR (see `list_participant_id_schemes`).

        Args:
            active_only: When True (default), omit deprecated/removed entries.
        """
        try:
            rows = codelists.list_process_ids(active_only=active_only)
        except codelists.CodelistNotConfiguredError as exc:
            return {"configured": False, "error": str(exc), "processes": []}
        return {"configured": True, "processes": rows}

    def list_spis_use_case_ids(active_only: bool = True) -> dict[str, Any]:
        """List Peppol SPIS use case identifiers from the OpenPeppol eDEC code list.

        Requires EINVOICING_PEPPOL_CODELIST_DIR (see `list_participant_id_schemes`).

        Args:
            active_only: When True (default), omit deprecated/removed entries.
        """
        try:
            rows = codelists.list_spis_use_case_ids(active_only=active_only)
        except codelists.CodelistNotConfiguredError as exc:
            return {"configured": False, "error": str(exc), "spis_use_cases": []}
        return {"configured": True, "spis_use_cases": rows}

    def check_document_type_id_in_codelist(scheme: str, value: str) -> dict[str, Any]:
        """Check whether a (scheme, value) pair is a recognized Peppol document type identifier.

        Requires EINVOICING_PEPPOL_CODELIST_DIR (see `list_participant_id_schemes`).
        Searches all entries regardless of state, so a historical (deprecated
        or removed) document type is still reported as found.
        """
        try:
            return {"configured": True, **codelists.check_document_type_id_in_codelist(scheme, value)}
        except codelists.CodelistNotConfiguredError as exc:
            return {"configured": False, "error": str(exc), "found": False}

    def check_process_id_in_codelist(scheme: str, value: str) -> dict[str, Any]:
        """Check whether a (scheme, value) pair is a recognized Peppol process identifier.

        Requires EINVOICING_PEPPOL_CODELIST_DIR (see `list_participant_id_schemes`).
        """
        try:
            return {"configured": True, **codelists.check_process_id_in_codelist(scheme, value)}
        except codelists.CodelistNotConfiguredError as exc:
            return {"configured": False, "error": str(exc), "found": False}

    def check_participant_id_scheme_in_codelist(icd: str) -> dict[str, Any]:
        """Check whether a 4-digit ISO 6523 ICD code (e.g. "0208") is a recognized Peppol scheme.

        Requires EINVOICING_PEPPOL_CODELIST_DIR (see `list_participant_id_schemes`).
        """
        try:
            return {"configured": True, **codelists.check_participant_id_scheme_in_codelist(icd)}
        except codelists.CodelistNotConfiguredError as exc:
            return {"configured": False, "error": str(exc), "found": False}

    def get_peppol_codelist_version() -> dict[str, Any]:
        """Report the OpenPeppol eDEC code list release version(s) currently configured locally."""
        return codelists.get_peppol_codelist_version()

    mcp.tool()(peppol_lookup_participant)
    mcp.tool()(peppol_get_service_endpoint)
    mcp.tool()(resolve_peppol_dns)
    mcp.tool()(peppol_send)
    mcp.tool()(list_participant_id_schemes)
    mcp.tool()(list_document_type_ids)
    mcp.tool()(list_process_ids)
    mcp.tool()(list_spis_use_case_ids)
    mcp.tool()(check_document_type_id_in_codelist)
    mcp.tool()(check_process_id_in_codelist)
    mcp.tool()(check_participant_id_scheme_in_codelist)
    mcp.tool()(get_peppol_codelist_version)
