#!/usr/bin/env node

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  Tool,
} from "@modelcontextprotocol/sdk/types.js";
import { promises as fs } from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Supported platforms and detail levels
const PLATFORMS = ["android", "typescript", "java", "python", "react", "kotlin"] as const;
const DETAIL_LEVELS = ["short", "medium", "detailed"] as const;

type Platform = typeof PLATFORMS[number];
type DetailLevel = typeof DETAIL_LEVELS[number];

interface PromptMetadata {
  platform: Platform;
  detailLevel: DetailLevel;
  path: string;
  exists: boolean;
}

class CodeReviewPromptsServer {
  private server: Server;
  private promptsDir: string;
  private availablePrompts: Map<string, PromptMetadata>;

  constructor() {
    this.server = new Server(
      {
        name: "code-review-prompts",
        version: "1.0.0",
      },
      {
        capabilities: {
          tools: {},
        },
      }
    );

    // Prompts directory is relative to the compiled JS location
    this.promptsDir = path.join(__dirname, "..", "prompts");
    this.availablePrompts = new Map();

    this.setupHandlers();
  }

  private async scanPrompts(): Promise<void> {
    try {
      const files = await fs.readdir(this.promptsDir);

      for (const file of files) {
        if (!file.endsWith(".md")) continue;

        // Parse filename: platform-detailLevel.md
        const match = file.match(/^(.+)-(short|medium|detailed)\.md$/);
        if (!match) continue;

        const [, platform, detailLevel] = match;
        const key = `${platform}-${detailLevel}`;

        this.availablePrompts.set(key, {
          platform: platform as Platform,
          detailLevel: detailLevel as DetailLevel,
          path: path.join(this.promptsDir, file),
          exists: true,
        });
      }
    } catch (error) {
      console.error("Error scanning prompts directory:", error);
    }
  }

  private async getPromptContent(platform: string, detailLevel: string): Promise<string> {
    const key = `${platform}-${detailLevel}`;
    const metadata = this.availablePrompts.get(key);

    if (!metadata || !metadata.exists) {
      throw new Error(
        `Prompt not found for platform: ${platform}, detail level: ${detailLevel}`
      );
    }

    try {
      const content = await fs.readFile(metadata.path, "utf-8");
      return content;
    } catch (error) {
      throw new Error(`Failed to read prompt file: ${error}`);
    }
  }

  private setupHandlers(): void {
    // List available tools
    this.server.setRequestHandler(ListToolsRequestSchema, async () => {
      const tools: Tool[] = [
        {
          name: "get_code_review_prompt",
          description:
            "Retrieve a code review prompt by platform and detail level. " +
            `Supported platforms: ${PLATFORMS.join(", ")}. ` +
            `Detail levels: ${DETAIL_LEVELS.join(", ")} (short=brief/critical only, medium=comprehensive, detailed=in-depth with workflow).`,
          inputSchema: {
            type: "object",
            properties: {
              platform: {
                type: "string",
                enum: [...PLATFORMS],
                description: "Programming platform/language (e.g., android, typescript, java, python)",
              },
              detailLevel: {
                type: "string",
                enum: [...DETAIL_LEVELS],
                description: "Level of detail in the review prompt (short, medium, or detailed)",
              },
            },
            required: ["platform", "detailLevel"],
          },
        },
        {
          name: "list_available_prompts",
          description: "List all available code review prompts with their platforms and detail levels",
          inputSchema: {
            type: "object",
            properties: {},
          },
        },
      ];

      return { tools };
    });

    // Handle tool calls
    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      const { name, arguments: args } = request.params;

      try {
        if (name === "get_code_review_prompt") {
          const { platform, detailLevel } = args as {
            platform: string;
            detailLevel: string;
          };

          if (!PLATFORMS.includes(platform as Platform)) {
            throw new Error(
              `Unsupported platform: ${platform}. Supported: ${PLATFORMS.join(", ")}`
            );
          }

          if (!DETAIL_LEVELS.includes(detailLevel as DetailLevel)) {
            throw new Error(
              `Invalid detail level: ${detailLevel}. Supported: ${DETAIL_LEVELS.join(", ")}`
            );
          }

          const promptContent = await this.getPromptContent(platform, detailLevel);

          return {
            content: [
              {
                type: "text",
                text: `# Code Review Prompt\n\n**Platform:** ${platform}\n**Detail Level:** ${detailLevel}\n\n---\n\n${promptContent}`,
              },
            ],
          };
        } else if (name === "list_available_prompts") {
          const prompts = Array.from(this.availablePrompts.values()).map((meta) => ({
            platform: meta.platform,
            detailLevel: meta.detailLevel,
            key: `${meta.platform}-${meta.detailLevel}`,
          }));

          const promptList = prompts
            .map((p) => `- **${p.platform}** (${p.detailLevel})`)
            .join("\n");

          return {
            content: [
              {
                type: "text",
                text: `# Available Code Review Prompts\n\n${promptList}\n\n` +
                  `Total: ${prompts.length} prompts\n\n` +
                  `Use \`get_code_review_prompt\` with platform and detailLevel to retrieve a prompt.`,
              },
            ],
          };
        }

        throw new Error(`Unknown tool: ${name}`);
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        return {
          content: [
            {
              type: "text",
              text: `Error: ${errorMessage}`,
            },
          ],
          isError: true,
        };
      }
    });
  }

  async run(): Promise<void> {
    // Scan available prompts on startup
    await this.scanPrompts();

    const transport = new StdioServerTransport();
    await this.server.connect(transport);

    console.error("Code Review Prompts MCP Server running on stdio");
    console.error(`Available prompts: ${this.availablePrompts.size}`);
  }
}

// Start the server
const server = new CodeReviewPromptsServer();
server.run().catch((error) => {
  console.error("Server error:", error);
  process.exit(1);
});
