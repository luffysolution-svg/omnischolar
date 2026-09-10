import assert from "node:assert/strict";
import test from "node:test";

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import type { Client } from "@modelcontextprotocol/sdk/client/index.js";

import { registerMcpTool, resultText } from "../src/index.js";

test("resultText preserves text and serializes non-text MCP content", () => {
  const text = resultText({
    content: [
      { type: "text", text: "first" },
      { type: "image", data: "AA==", mimeType: "image/png" },
    ],
  });
  assert.equal(text, 'first\n{"type":"image","data":"AA==","mimeType":"image/png"}');
});

test("registerMcpTool forwards arguments and structured content", async () => {
  let definition: Record<string, unknown> | undefined;
  const pi = {
    registerTool(value: Record<string, unknown>) {
      definition = value;
    },
  } as unknown as ExtensionAPI;
  const client = {
    async callTool(request: unknown) {
      assert.deepEqual(request, { name: "omnischolar_status", arguments: { verbose: true } });
      return {
        content: [{ type: "text", text: "ready" }],
        structuredContent: { status: "success" },
      };
    },
  } as unknown as Client;

  registerMcpTool(pi, client, {
    name: "omnischolar_status",
    description: "Show status",
    inputSchema: { type: "object", properties: { verbose: { type: "boolean" } } },
  });
  assert.ok(definition);
  const execute = definition.execute as (
    id: string,
    params: Record<string, unknown>,
    signal: AbortSignal,
  ) => Promise<Record<string, unknown>>;
  const result = await execute("call-1", { verbose: true }, new AbortController().signal);
  assert.deepEqual(result, {
    content: [{ type: "text", text: "ready" }],
    details: { status: "success" },
  });
});

test("registerMcpTool throws when MCP returns isError", async () => {
  let definition: Record<string, unknown> | undefined;
  const pi = {
    registerTool(value: Record<string, unknown>) {
      definition = value;
    },
  } as unknown as ExtensionAPI;
  const client = {
    async callTool() {
      return { content: [{ type: "text", text: "denied" }], isError: true };
    },
  } as unknown as Client;
  registerMcpTool(pi, client, {
    name: "test_tool",
    inputSchema: { type: "object", properties: {} },
  });
  const execute = definition?.execute as (
    id: string,
    params: Record<string, unknown>,
    signal: AbortSignal,
  ) => Promise<Record<string, unknown>>;
  await assert.rejects(
    execute("call-2", {}, new AbortController().signal),
    /denied/,
  );
});
