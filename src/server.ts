import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { Configuration, DefaultApi, SupermodelClient } from '@supermodeltools/sdk';
import createSupermodelGraphTool from './tools/create-supermodel-graph';
import { ClientContext } from './types';
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import { cleanupOldZips } from './utils/zip-repository';
import { Agent } from 'undici';
import { DEFAULT_API_TIMEOUT_MS, CONNECTION_TIMEOUT_MS, ZIP_CLEANUP_AGE_MS } from './constants';
import * as logger from './utils/logger';

// Configure HTTP timeout for API requests (default from constants)
// Some complex repos can take 10+ minutes to process
const parsedTimeout = parseInt(process.env.SUPERMODEL_TIMEOUT_MS || '', 10);
const TIMEOUT_MS = Number.isFinite(parsedTimeout) && parsedTimeout > 0
  ? parsedTimeout
  : DEFAULT_API_TIMEOUT_MS;

const agent = new Agent({
  headersTimeout: TIMEOUT_MS,
  bodyTimeout: TIMEOUT_MS,
  connectTimeout: CONNECTION_TIMEOUT_MS,
});

const fetchWithTimeout: typeof fetch = (url, init) => {
  return fetch(url, {
    ...init,
    // @ts-ignore - 'dispatcher' is a valid undici option that TypeScript's
    // built-in fetch types don't recognize. This routes requests through our
    // custom Agent with extended timeouts.
    dispatcher: agent,
  });
};

export class Server {
  private server: McpServer;
  private client: ClientContext;
  private defaultWorkdir?: string;

  constructor(defaultWorkdir?: string) {
    this.defaultWorkdir = defaultWorkdir;
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
- Subsystem: directory="/repo/django/db" → 15MB, 3k nodes

## Error Handling

When a tool call returns an error, check the structured error fields:
- \`error.recoverable: true\` → wait briefly and retry the request
- \`error.reportable: true\` → this is a server-side bug, not your fault

If you receive a reportable error and have GitHub access:
1. Search the \`error.repo\` issues for the \`error.code\` to avoid duplicates
2. If no existing issue, open one with the error code, message, and any reproduction context
3. If you can identify and fix the root cause, fork the repo and open a PR

This helps the maintainers fix bugs faster and avoids wasting your iteration budget on issues you cannot work around locally.`,
      },
    );

    const config = new Configuration({
      basePath: process.env.SUPERMODEL_BASE_URL || 'https://api.supermodeltools.com',
      apiKey: process.env.SUPERMODEL_API_KEY,
      fetchApi: fetchWithTimeout,
    });

    logger.debug('Server configuration:');
    logger.debug('Base URL:', config.basePath);
    logger.debug('API Key set:', !!process.env.SUPERMODEL_API_KEY);
    if (this.defaultWorkdir) {
      logger.debug('Default workdir:', this.defaultWorkdir);
    }

    const api = new DefaultApi(config);
    this.client = {
      graphs: new SupermodelClient(api),
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
        return createSupermodelGraphTool.handler(this.client, args, this.defaultWorkdir);
      }
      
      throw new Error(`Unknown tool: ${name}`);
    });
  }

  async start() {
    // Clean up any stale ZIP files from previous sessions
    await cleanupOldZips(ZIP_CLEANUP_AGE_MS);

    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    logger.info('Supermodel MCP Server running on stdio');
  }
}

