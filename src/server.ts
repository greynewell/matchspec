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
          'This MCP server provides tools for deep codebase analysis using static analysis and graph generation.\n\n# WHEN TO USE CODEBASE ANALYSIS\n\nProactively use the analyze_codebase tool in these scenarios:\n\n1. EXPLORING NEW CODE: When the user asks about an unfamiliar codebase, analyze it first to understand structure, dependencies, and architecture before answering questions or making changes.\n\n2. PLANNING REFACTORS: Before refactoring code, analyze dependency and call graphs to assess impact across the codebase. Identify all affected files and relationships.\n\n3. ASSESSING CHANGE IMPACT: When asked to modify existing functionality, analyze call graphs to understand what depends on the code being changed.\n\n4. UNDERSTANDING ARCHITECTURE: When questions arise about "how does X work" or "where is Y implemented", analyze the codebase to map out the actual structure and relationships.\n\n5. FINDING DEPENDENCIES: When investigating bugs or adding features, analyze dependency graphs to understand module relationships and potential side effects.\n\n6. MAPPING DOMAIN MODELS: When working with complex business logic, analyze domain classifications to understand system boundaries and architectural patterns.\n\n# QUICK START\n\nBasic workflow:\n1. Create repository ZIP: git archive -o /tmp/repo.zip HEAD\n2. Generate cache key: git rev-parse --short HEAD\n3. Call analyze_codebase with file=/tmp/repo.zip, Idempotency-Key=projectname:supermodel:{hash}, and jq_filter to extract needed data\n4. Use the graph data to inform your work\n5. Keep results in context - reuse for multiple queries about the same code state\n\n# TECHNICAL DETAILS\n\nPREPARING REPOSITORY ZIP FILES:\n\nFor Git Repositories (Recommended):\nRun: cd /path/to/your/repo && git archive -o /tmp/repo.zip HEAD\n\nThis method automatically:\n- Respects .gitignore\n- Includes only tracked files\n- Creates cleaner, smaller archives\n- Produces reproducible results\n\nFor Any Directory:\nRun: cd /path/to/your/repo && zip -r /tmp/repo.zip . -x "node_modules/*" -x ".git/*" -x "dist/*" -x "build/*" -x "target/*" -x "*.pyc" -x "__pycache__/*" -x "venv/*" -x ".venv/*" -x "vendor/*" -x ".idea/*" -x ".vscode/*"\n\nINCLUDE: Source code files (.py, .js, .ts, .tsx, .java, .go, .rs, .rb, .kt, .scala, .c, .cpp, .h, .hpp), configuration files (package.json, tsconfig.json, pyproject.toml, Cargo.toml, go.mod, pom.xml), and type definitions (.d.ts, .pyi).\n\nEXCLUDE: Dependencies (node_modules/, vendor/, venv/, .venv/, target/), build outputs (dist/, build/, out/, .next/, __pycache__/), version control (.git/), IDE files (.idea/, .vscode/), and large binaries/images/datasets.\n\nIf ZIP exceeds 50MB: Ensure dependencies are excluded, consider analyzing a subdirectory, or check for accidentally committed binary files.\n\nCACHING STRATEGY:\n\nGraph generation is computationally expensive. NEVER regenerate for the same code state.\n\nIdempotency Keys: Use format {repo_identifier}:{graph_type}:{content_hash}\nExample: myproject:supermodel:abc123def\n\nGenerate content hash:\n- For git repos: git rev-parse --short HEAD\n- For ZIP files: shasum -a 256 /tmp/repo.zip | cut -d\' \' -f1 | head -c 12\n\nREGENERATE when:\n- Source code files changed\n- New files added affecting analysis scope\n- Files deleted from the analyzed set\n- Dependencies changed (affects dependency graph)\n\nDO NOT regenerate when:\n- Only documentation/comments changed\n- Only formatting changed\n- Only non-code files changed\n- Switching between different analysis questions on the same code state\n\nSESSION MANAGEMENT:\n\nWithin a session:\n- Keep graph results in context memory\n- Reference previous results instead of re-calling the API\n- Use jq_filter to extract specific subsets from cached results\n- Store summary statistics for quick reference\n\nAcross sessions:\n- Store the idempotency key used\n- Store a summary of the graph (node counts, key relationships)\n- On resume, check if code state matches before regenerating\n\nOPTIMIZATION:\n\nThe analyze_codebase tool returns comprehensive results including all graph types (dependencies, calls, domain model, AST). Call it ONCE and use jq_filter to extract specific data as needed.\n\nExample filters:\n- \'.summary\' - Get overview statistics\n- \'.graph.nodes[] | select(.type=="function")\' - Extract function nodes\n- \'.graph.relationships[] | select(.type=="calls")\' - Extract call relationships\n- \'.graph.nodes[] | select(.file | contains("auth"))\' - Find nodes in auth-related files\n\nTrack: idempotency key, commit/ZIP hash, generation timestamp, summary stats (file count, node count, relationship count).\n\nCOMPLETE EXAMPLE:\n\n# Initial analysis\n$ cd /path/to/project\n$ git archive -o /tmp/project.zip HEAD\n$ HASH=$(git rev-parse --short HEAD)\n# Call analyze_codebase with:\n#   file: /tmp/project.zip\n#   Idempotency-Key: myproject:supermodel:${HASH}\n#   jq_filter: \'.summary\'\n\n# Later queries on same code\n# Reuse cached results or filter differently:\n#   jq_filter: \'.graph.nodes[] | select(.type=="class")\'',
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
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    console.error('Supermodel MCP Server running on stdio');
  }
}

