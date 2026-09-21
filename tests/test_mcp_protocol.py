from __future__ import annotations

import unittest

from omnischolar.mcp.server import result_to_mcp, tool_to_mcp
from omnischolar.registry import ToolExecutionResult
from omnischolar.tools.catalogue import create_tool_definitions


class McpProtocolTests(unittest.TestCase):
    def test_paper_interpretation_is_skill_driven(self) -> None:
        names = {item.name for item in create_tool_definitions()}

        self.assertTrue({"omnischolar_parse", "omnischolar_sync"} <= names)
        self.assertTrue(
            names.isdisjoint(
                {
                    "omnischolar_read",
                    "omnischolar_focus",
                    "omnischolar_locate",
                    "omnischolar_context",
                    "omnischolar_analysis",
                }
            )
        )

    def test_tool_does_not_advertise_duplicate_structured_output(self) -> None:
        definition = next(item for item in create_tool_definitions() if item.name == "literature_search")
        self.assertIsNone(tool_to_mcp(definition).outputSchema)

    def test_result_keeps_bounded_json_in_text_only(self) -> None:
        result = result_to_mcp(
            ToolExecutionResult(
                is_error=False,
                structured_content={"ok": True, "data": {"value": "evidence"}},
                text='{"ok": true, "data": {"value": "evidence"}}',
            )
        )
        self.assertIsNone(result.structuredContent)
        self.assertEqual(result.content[0].text, '{"ok": true, "data": {"value": "evidence"}}')


if __name__ == "__main__":
    unittest.main()
