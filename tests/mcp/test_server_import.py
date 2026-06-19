from lightrag_mcp.server import mcp


def test_server_declares_expected_name():
    assert mcp.name == "lightrag-hermes"
