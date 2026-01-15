import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { Configuration, DefaultApi } from '@supermodeltools/sdk';
import createSupermodelGraphTool from './tools/create-supermodel-graph';
import { ClientContext } from './types';
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import { cleanupOldZips } from './utils/zip-repository';

export class Server {
  private server: McpServer;
  private client: ClientContext;

  constructor() {
    this.server = new McpServer(
      {
        name: 'supermodel_api',
        version: '0.0.1',
      },
      {
        capabilities: { tools: {}, logging: {} },
        instructions: `# Server Instructions: Supermodel Codebase Explorer

## Graph Rules
- This API produces graphs of the code contained within a target directory.
- STRATEGY: Before debugging, planning, or analyzing a change to a code repository, generate a code graph. Use it to localize changes and find what files to search more efficiently than grep.

## Debugging Strategy
1. Generate a code graph of the given repository or a subset.
2. Analyze the nodes and relationships which appear to be related to your issue.
3. Analyze the broader context of these nodes in relationships within their domain and subdomain.
4. Use the graph like a diagram to navigate the codebase more efficiently than raw grep and to analyze the potential blast radius of any change.
  
## Planning Strategy
1. Generate a code graph of the given repository or a subset.
2. Analyze relationships like dependencies, calls, and inheritance to identify the potential blast radius of a proposed change.
3. Examine other elements of the same Domain and Subdomain to look for patterns including best practices or anti-patterns.
4. Look at the nodes you plan to change and find their physical locations, allowing you to analyze more efficiently than blind grepping.

## Analysis Strategy
1. Generate a code graph of the given repository or a subset.
2. Analyze the system domains to understand the high-level system architecture.
3. Examine leaf nodes to see the structure of the broader tree.
4. Use the graph like a map to navigate the codebase more efficiently than blind grepping.

## Performance Optimization

For localized bugs:
1. Identify the affected subsystem from the issue description
2. Analyze only that subdirectory (e.g., \`django/db\` instead of full repo)
3. This is faster, uses less memory, and avoids ZIP size limits

Example:
- Full repo: directory="/repo" → 180MB, 50k nodes
- Subsystem: directory="/repo/django/db" → 15MB, 3k nodes`,
      },
    );

    const config = new Configuration({
      basePath: process.env.SUPERMODEL_BASE_URL || 'https://api.supermodeltools.com',
      apiKey: process.env.SUPERMODEL_API_KEY,
    });

    console.error('[DEBUG] Server configuration:');
    console.error('[DEBUG] Base URL:', config.basePath);
    console.error('[DEBUG] API Key set:', !!process.env.SUPERMODEL_API_KEY);

    this.client = {
      graphs: new DefaultApi(config),
    };

    this.setupHandlers();
  }

  private setupHandlers() {
    this.server.server.setRequestHandler(ListToolsRequestSchema, async () => {
      return {
        tools: [createSupermodelGraphTool.tool],
      };
    });

    this.server.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      const { name, arguments: args } = request.params;
      
      if (name === createSupermodelGraphTool.tool.name) {
        return createSupermodelGraphTool.handler(this.client, args);
      }
      
      throw new Error(`Unknown tool: ${name}`);
    });
  }

  async start() {
    // Clean up any stale ZIP files from previous sessions
    // (older than 24 hours)
    await cleanupOldZips(24 * 60 * 60 * 1000);

    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    console.error('Supermodel MCP Server running on stdio');
  }
}

