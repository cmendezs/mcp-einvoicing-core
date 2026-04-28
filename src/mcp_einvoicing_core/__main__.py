from mcp_einvoicing_core.base_server import EInvoicingMCPServer

server = EInvoicingMCPServer(
    name="mcp-einvoicing-core",
    instructions=(
        "Base MCP server for European electronic invoicing. "
        "Register country adapter plugins to expose e-invoicing tools."
    ),
)
server.run()
