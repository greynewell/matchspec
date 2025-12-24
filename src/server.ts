import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { Configuration, DefaultApi } from '@supermodeltools/sdk';
import createSupermodelGraphTool from './tools/create-supermodel-graph';
import { ClientContext } from './types';
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js';

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
        instructions:
          'This MCP server provides tools for analyzing code repositories. Before using the graph generation tools, follow these instructions.\n\nPREPARING REPOSITORY ZIP FILES:\nAll graph generation tools require a ZIP archive of your repository.\n\nFor Git Repositories (Recommended):\nRun: cd /path/to/your/repo && git archive -o /tmp/repo.zip HEAD\nThis method automatically respects .gitignore, only includes tracked files, creates cleaner smaller archives, and produces reproducible results.\n\nFor Any Directory:\nRun: cd /path/to/your/repo && zip -r /tmp/repo.zip . -x "node_modules/*" -x ".git/*" -x "dist/*" -x "build/*" -x "target/*" -x "*.pyc" -x "__pycache__/*" -x "venv/*" -x ".venv/*" -x "vendor/*" -x ".idea/*" -x ".vscode/*"\n\nINCLUDE: Source code files (.py, .js, .ts, .tsx, .java, .go, .rs, .rb, .kt, .scala, .c, .cpp, .h, .hpp), configuration files (package.json, tsconfig.json, pyproject.toml, Cargo.toml, go.mod, pom.xml), and type definitions (.d.ts, .pyi).\n\nEXCLUDE: Dependencies (node_modules/, vendor/, venv/, .venv/, target/), build outputs (dist/, build/, out/, .next/, __pycache__/), version control (.git/), IDE files (.idea/, .vscode/), and large binaries/images/datasets.\n\nIf ZIP exceeds 50MB, ensure dependencies are excluded, consider analyzing a subdirectory, or check for accidentally committed binary files.\n\nGRAPH CACHING STRATEGY:\nGraph generation is expensive. NEVER re-upload the same repository state twice.\n\nIdempotency Keys: Every graph tool requires an Idempotency-Key parameter. Use format: {repo_identifier}:{graph_type}:{content_hash} Example: myproject:supermodel:abc123def\n\nGenerate content hash via: git rev-parse --short HEAD (for git repos) or shasum -a 256 /tmp/repo.zip | cut -d\' \' -f1 | head -c 12 (for ZIP hash).\n\nREGENERATE when: source code files changed, new files added affecting analysis scope, files deleted from graph, or dependencies changed (for dependency graph only).\n\nDO NOT regenerate when: only documentation/comments changed, only formatting changed, only non-code files changed, or switching between analysis tasks on same code state.\n\nSESSION MANAGEMENT:\nWithin a session: keep graph results in memory/context, reference previous results instead of re-calling APIs, use jq_filter to extract specific parts.\n\nAcross sessions: store the idempotency key used, store a summary of the graph (node count, key relationships), on resume check if code state matches before regenerating.\n\nGRAPH TYPE SELECTION:\ncreate_supermodel_graph_graphs - Best for comprehensive analysis, includes all graph types. Use jq_filter to extract specific data.\ncreate_call_graph_graphs - Function-level call relationships. Invalidate when function signatures change.\ncreate_dependency_graph_graphs - Module/package dependencies. Invalidate when imports or package manifests change.\ncreate_domain_graph_graphs - High-level domain model. Most stable, only invalidate for structural changes.\ncreate_parse_graph_graphs - AST-level relationships. Most sensitive, invalidate for any syntax changes.\n\nOPTIMIZATION: Call create_supermodel_graph_graphs ONCE (includes all types), use jq_filter to extract needed data, track last idempotency key, last commit/ZIP hash, generation timestamp, and summary stats.\n\nEXAMPLE WORKFLOW:\n1. Create ZIP: git archive -o /tmp/repo.zip HEAD\n2. Get hash: git rev-parse --short HEAD (e.g. abc123)\n3. Call create_supermodel_graph_graphs with file=/tmp/repo.zip and Idempotency-Key=myproject:supermodel:abc123\n4. Store result. Later queries use same key or extract from cached result.\n5. After code changes, check new hash. If different, regenerate with new key. If same, use cached result.',
      },
    );

    const config = new Configuration({
      basePath: process.env.SUPERMODEL_BASE_URL || 'https://api.supermodel.io',
      apiKey: process.env.SUPERMODEL_API_KEY,
      headers: {
         // Add any custom headers here
      },
      accessToken: process.env.SUPERMODEL_BEARER_TOKEN
    });

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
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    console.error('Supermodel MCP Server running on stdio');
  }
}

