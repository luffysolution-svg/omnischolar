import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import type { CallToolResult, Tool } from "@modelcontextprotocol/sdk/types.js";
import { Type } from "typebox";

const CLIENT_INFO = { name: "omnischolar-pi", version: "0.1.1" };

export function resultText(result: CallToolResult): string {
  return result.content
    .map((item) => {
      if (item.type === "text") return item.text;
      return JSON.stringify(item);
    })
    .join("\n");
}

export function registerMcpTool(pi: ExtensionAPI, client: Client, tool: Tool): void {
  pi.registerTool({
    name: tool.name,
    label: tool.title ?? tool.name.replaceAll("_", " "),
    description: tool.description ?? `Call the OmniScholar ${tool.name} tool.`,
    parameters: Type.Unsafe(tool.inputSchema),
    async execute(_toolCallId, params, signal) {
      const result = (await client.callTool(
        { name: tool.name, arguments: params as Record<string, unknown> },
        undefined,
        { signal },
      )) as CallToolResult;
      const text = resultText(result);
      if (result.isError) throw new Error(text || `${tool.name} failed`);
      return {
        content: [{ type: "text", text }],
        details: result.structuredContent ?? {},
      };
    },
  });
}

export default function omnischolarExtension(pi: ExtensionAPI): void {
  let client: Client | undefined;
  let transport: StdioClientTransport | undefined;
  let connection: Promise<void> | undefined;

  const connect = (): Promise<void> => {
    if (connection) return connection;
    connection = (async () => {
      transport = new StdioClientTransport({
        command: "omnischolar",
        args: ["mcp"],
        stderr: "pipe",
      });
      client = new Client(CLIENT_INFO);
      await client.connect(transport);
      const { tools } = await client.listTools();
      for (const tool of tools) registerMcpTool(pi, client, tool);
    })();
    return connection;
  };

  pi.on("session_start", async (_event, ctx) => {
    try {
      await connect();
    } catch (error) {
      connection = undefined;
      await client?.close().catch(() => undefined);
      client = undefined;
      transport = undefined;
      const message = error instanceof Error ? error.message : String(error);
      ctx.ui.notify(`OmniScholar MCP did not start: ${message}`, "error");
    }
  });

  pi.on("session_shutdown", async () => {
    await client?.close().catch(() => undefined);
    client = undefined;
    transport = undefined;
    connection = undefined;
  });
}
