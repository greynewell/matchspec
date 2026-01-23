import { Tool } from '@modelcontextprotocol/sdk/types.js';
import { readFile } from 'fs/promises';
import { execSync } from 'child_process';
import { createHash } from 'crypto';
import { basename, resolve } from 'path';
import {
  Metadata,
  Endpoint,
  HandlerFunction,
  asTextContentResult,
  asErrorResult,
  ClientContext,
  StructuredError
} from '../types';
import { maybeFilter, isJqError } from '../filtering';
import { executeQuery, getAvailableQueries, isQueryError, QueryType, graphCache } from '../queries';
import { IndexedGraph } from '../cache/graph-cache';
import { zipRepository } from '../utils/zip-repository';
import * as logger from '../utils/logger';

const REPORT_REPO = 'https://github.com/supermodeltools/mcp.git';
const REPORT_SUGGESTION = 'This may be a bug in the MCP server. You can help by opening an issue at https://github.com/supermodeltools/mcp/issues with the error details, or fork the repo and open a PR with a fix.';

export const metadata: Metadata = {
  resource: 'graphs',
  operation: 'write',
  tags: [],
  httpMethod: 'post',
  httpPath: '/v1/graphs/supermodel',
  operationId: 'generateSupermodelGraph',
};

export const tool: Tool = {
  name: 'explore_codebase',
  description: `Comprehensive codebase analysis using Supermodel API. ⚠️ This operation takes 5-15 minutes for large repositories. Ensure your Claude CLI timeout is configured (MCP_TOOL_TIMEOUT=900000). Analyzes code structure, dependencies, and patterns while respecting .gitignore.

Analyzes code within the target directory to produce a graph that can be used to navigate the codebase when solving bugs, planning or analyzing code changes.

## Example Output

This is actual output from running explore_codebase on its own repository (19 TypeScript files, ~60KB).

The graph structure shows 163 nodes (Functions, Classes, Types, Files, Domains) and 254 relationships between them. Below is an excerpt showing the data structure:

\`\`\`json
{
  "repo": "1c740c9c4f5c9528e244ab144488214341f959231f73009a46a74a1f11350c3c",
  "version": "sir-2026-01-15",
  "schemaVersion": "1.2.0",
  "generatedAt": "2026-01-15T18:17:10.067Z",
  "summary": {
    "filesProcessed": 19,
    "types": 28,
    "functions": 52,
    "repoSizeBytes": 61058,
    "classes": 2,
    "domains": 6,
    "primaryLanguage": "json"
  },
  "graph": {
    "nodeCount": 163,
    "relationshipCount": 254,
    "sampleNodes": [
      {
        "id": "0965aff4:42ff:df74:ae01:0d17d0886720",
        "labels": ["ExternalModule"],
        "properties": {
          "name": "mcp.js"
        }
      },
      {
        "id": "ab32efae:3825:dada:a4b5:95e95dbb71cc",
        "labels": ["Function"],
        "properties": {
          "name": "getNode",
          "filePath": "src/queries/discovery.ts",
          "language": "typescript",
          "startLine": 25,
          "endLine": 57,
          "kind": "function"
        }
      },
      {
        "id": "8648e520:0be3:b754:77ce:c19dcebf6d6f",
        "labels": ["File"],
        "properties": {
          "name": "test-full-graph.js",
          "filePath": "test-full-graph.js",
          "path": "test-full-graph.js",
          "language": "javascript"
        }
      }
    ],
    "sampleRelationships": [
      {
        "id": "b161d717:5ee5:b827:cc26:f071f7a9648d->ff2a17f0:c2b6:f518:dcb8:91584b241c0f:CHILD_DIRECTORY",
        "type": "CHILD_DIRECTORY",
        "startNode": "b161d717:5ee5:b827:cc26:f071f7a9648d",
        "endNode": "ff2a17f0:c2b6:f518:dcb8:91584b241c0f",
        "properties": {}
      },
      {
        "id": "ff2a17f0:c2b6:f518:dcb8:91584b241c0f->7f19b034:9fee:67c7:7b42:c7ba738d9ceb:CONTAINS_FILE",
        "type": "CONTAINS_FILE",
        "startNode": "ff2a17f0:c2b6:f518:dcb8:91584b241c0f",
        "endNode": "7f19b034:9fee:67c7:7b42:c7ba738d9ceb",
        "properties": {}
      }
    ]
  }
}
\`\`\`

The graph contains nodes with properties like filePath, startLine, endLine for functions, and relationships like CHILD_DIRECTORY, CONTAINS_FILE, calls, IMPORTS that connect code entities.

Query types available: graph_status, summary, get_node, search, list_nodes, function_calls_in, function_calls_out, definitions_in_file, file_imports, domain_map, domain_membership, neighborhood, jq
`,
  inputSchema: {
    type: 'object',
    properties: {
      directory: {
        type: 'string',
        description: 'Path to the repository directory to analyze. Can be a subdirectory for faster analysis and smaller graph size (e.g., "/repo/src/core" instead of "/repo").',
      },
      query: {
        type: 'string',
        enum: [
          'graph_status', 'summary', 'get_node', 'search', 'list_nodes',
          'function_calls_in', 'function_calls_out', 'definitions_in_file',
          'file_imports', 'domain_map', 'domain_membership', 'neighborhood', 'jq'
        ],
        description: 'Query type to execute. Use graph_status first to check cache, then summary to load.',
      },
      targetId: {
        type: 'string',
        description: 'Node ID for queries that operate on a specific node (get_node, function_calls_*, etc.)',
      },
      searchText: {
        type: 'string',
        description: 'Search text for name substring matching (search, domain_membership)',
      },
      namePattern: {
        type: 'string',
        description: 'Regex pattern for name matching (list_nodes)',
      },
      filePathPrefix: {
        type: 'string',
        description: 'Filter by file path prefix (list_nodes, definitions_in_file, search)',
      },
      labels: {
        type: 'array',
        items: { type: 'string' },
        description: 'Filter by node labels: Function, Class, Type, File, Domain, etc. (list_nodes, search)',
      },
      depth: {
        type: 'number',
        description: 'Traversal depth for neighborhood query (default 1, max 3)',
      },
      relationshipTypes: {
        type: 'array',
        items: { type: 'string' },
        description: 'Relationship types to traverse (neighborhood). Options: calls, IMPORTS',
      },
      limit: {
        type: 'number',
        description: 'Max results to return (default 200)',
      },
      includeRaw: {
        type: 'boolean',
        description: 'Include full raw node data in get_node response (default false)',
      },
      jq_filter: {
        type: 'string',
        title: 'jq Filter',
        description: 'Raw jq filter for escape hatch queries or legacy mode (when query param not specified)',
      },
    },
    required: [],
  },
};

/**
 * Generate an idempotency key in format {repo}-{pathHash}:supermodel:{hash}
 * Includes path hash to prevent collisions between same-named repos
 */
function generateIdempotencyKey(directory: string): string {
  const repoName = basename(directory);
  const absolutePath = resolve(directory);

  // Always include path hash to prevent collisions
  const pathHash = createHash('sha1').update(absolutePath).digest('hex').substring(0, 7);

  let hash: string;
  let statusHash = '';

  try {
    // Get git commit hash
    hash = execSync('git rev-parse --short HEAD', {
      cwd: directory,
      encoding: 'utf-8',
    }).trim();

    // Include working tree status in hash to detect uncommitted changes
    const statusOutput = execSync('git status --porcelain', {
      cwd: directory,
      encoding: 'utf-8',
    }).toString();

    if (statusOutput) {
      // Create hash of status output
      statusHash = '-' + createHash('sha1')
        .update(statusOutput)
        .digest('hex')
        .substring(0, 7);
    }
  } catch {
    // Fallback for non-git directories: use path hash as main identifier
    hash = pathHash;
  }

  return `${repoName}-${pathHash}:supermodel:${hash}${statusHash}`;
}

export const handler: HandlerFunction = async (client: ClientContext, args: Record<string, unknown> | undefined, defaultWorkdir?: string) => {
  if (!args) {
    args = {};
  }

  const {
    jq_filter,
    directory: providedDirectory,
    query,
    targetId,
    searchText,
    namePattern,
    filePathPrefix,
    labels,
    depth,
    relationshipTypes,
    limit,
    includeRaw,
  } = args as any;

  // Use provided directory or fall back to default workdir
  const directory = providedDirectory || defaultWorkdir;

  // Validate directory - check if explicitly invalid first
  if (providedDirectory !== undefined && typeof providedDirectory !== 'string') {
    logger.error('Invalid directory parameter:', providedDirectory);
    return asErrorResult({
      type: 'validation_error',
      message: 'Invalid "directory" parameter. Provide a valid directory path as a string.',
      code: 'INVALID_DIRECTORY',
      recoverable: false,
      suggestion: 'Pass directory as a string path, e.g. directory="/workspace/my-repo"',
    });
  }

  // Check if we have any directory at all
  if (!directory || typeof directory !== 'string') {
    logger.error('Invalid directory parameter:', directory);
    return asErrorResult({
      type: 'validation_error',
      message: 'No "directory" parameter provided and no default workdir configured.',
      code: 'MISSING_DIRECTORY',
      recoverable: false,
      suggestion: 'Provide a directory path or start the MCP server with a workdir argument (e.g. npx @anthropic-ai/supermodel-mcp /path/to/repo).',
    });
  }

  if (providedDirectory) {
    logger.debug('Using provided directory:', directory);
  } else {
    logger.debug('Using default workdir:', directory);
  }

  // Generate idempotency key for API request
  const idempotencyKey = generateIdempotencyKey(directory);
  logger.debug('Auto-generated idempotency key:', idempotencyKey);

  // Check if we can skip zipping (graph already cached)
  // Use get() atomically to avoid TOCTOU race condition
  const cachedGraph = graphCache.get(idempotencyKey);
  if (cachedGraph && query) {
    logger.debug('Graph cached, skipping ZIP creation');

    // Execute query directly from cache using the cached graph
    // We pass the cached graph to executeQuery so it doesn't need to look it up again
    const result = await handleQueryModeWithCache(client, {
      query: query as QueryType,
      idempotencyKey,
      cachedGraph,
      targetId,
      searchText,
      namePattern,
      filePathPrefix,
      labels,
      depth,
      relationshipTypes,
      limit,
      includeRaw,
      jq_filter,
    });

    return result;
  }

  logger.debug('Auto-zipping directory:', directory);

  // Handle auto-zipping
  let zipPath: string;
  let cleanup: (() => Promise<void>) | null = null;

  try {
    const zipResult = await zipRepository(directory);
    zipPath = zipResult.path;
    cleanup = zipResult.cleanup;

    logger.debug('Auto-zip complete:', zipResult.fileCount, 'files,', formatBytes(zipResult.sizeBytes));
  } catch (error: any) {
    // Log full error details for debugging
    logger.error('Auto-zip failed');
    logger.error('Error type:', error.name || 'Error');
    logger.error('Error message:', error.message);
    if (error.stack) {
      logger.error('Stack trace:', error.stack);
    }

    // Normalize: guard against non-Error throws (string, object, undefined)
    const message = typeof error?.message === 'string' ? error.message : String(error);

    // Return structured, actionable error messages
    if (message.includes('does not exist')) {
      return asErrorResult({
        type: 'not_found_error',
        message: `Directory not found: ${directory}`,
        code: 'DIRECTORY_NOT_FOUND',
        recoverable: false,
        suggestion: 'Verify the path exists. Use an absolute path to the repository root or subdirectory.',
        details: { directory },
      });
    }
    if (message.includes('Permission denied')) {
      return asErrorResult({
        type: 'resource_error',
        message: `Permission denied accessing directory: ${directory}`,
        code: 'PERMISSION_DENIED',
        recoverable: false,
        suggestion: 'Check that the MCP server process has read access to this directory.',
        details: { directory },
      });
    }
    if (message.includes('exceeds limit')) {
      return asErrorResult({
        type: 'resource_error',
        message,
        code: 'ZIP_TOO_LARGE',
        recoverable: true,
        suggestion: 'Analyze a subdirectory instead of the full repository (e.g. directory="/repo/src/core"). This reduces ZIP size and processing time.',
        details: { directory },
      });
    }
    if (message.includes('ENOSPC')) {
      return asErrorResult({
        type: 'resource_error',
        message: 'Insufficient disk space to create ZIP archive.',
        code: 'DISK_FULL',
        recoverable: false,
        suggestion: 'Free up disk space or analyze a smaller subdirectory.',
      });
    }

    return asErrorResult({
      type: 'internal_error',
      message: `Failed to create ZIP archive: ${message}`,
      code: 'ZIP_CREATION_FAILED',
      recoverable: false,
      reportable: true,
      repo: REPORT_REPO,
      suggestion: REPORT_SUGGESTION,
      details: { directory: basename(directory), errorType: error.name || 'Error' },
    });
  }

  // Execute query with cleanup handling
  try {
    let result;

    // If query param is specified, use the new query engine
    if (query) {
      result = await handleQueryMode(client, {
        query: query as QueryType,
        file: zipPath,
        idempotencyKey,
        targetId,
        searchText,
        namePattern,
        filePathPrefix,
        labels,
        depth,
        relationshipTypes,
        limit,
        includeRaw,
        jq_filter,
      });
    } else {
      // Legacy mode: use jq_filter directly on API response
      result = await handleLegacyMode(client, zipPath, idempotencyKey, jq_filter);
    }

    return result;
  } finally {
    // Always cleanup temp ZIP files
    if (cleanup) {
      await cleanup();
    }
  }
};

/**
 * Format bytes as human-readable string
 */
function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

/**
 * Handle query-based requests when graph is already cached
 * Uses the cached graph directly to avoid TOCTOU issues
 */
async function handleQueryModeWithCache(
  client: ClientContext,
  params: {
    query: QueryType;
    idempotencyKey: string;
    cachedGraph: IndexedGraph;
    targetId?: string;
    searchText?: string;
    namePattern?: string;
    filePathPrefix?: string;
    labels?: string[];
    depth?: number;
    relationshipTypes?: string[];
    limit?: number;
    includeRaw?: boolean;
    jq_filter?: string;
  }
): Promise<ReturnType<typeof asTextContentResult>> {
  const queryParams = {
    query: params.query,
    file: '', // Not used when we have cached graph
    idempotencyKey: params.idempotencyKey,
    targetId: params.targetId,
    searchText: params.searchText,
    namePattern: params.namePattern,
    filePathPrefix: params.filePathPrefix,
    labels: params.labels,
    depth: params.depth,
    relationshipTypes: params.relationshipTypes,
    limit: params.limit,
    includeRaw: params.includeRaw,
    jq_filter: params.jq_filter,
  };

  // Execute query with the cached graph's raw data
  // This handles the edge case where cache is evicted between our check and query execution
  // by passing the raw API response so executeQuery can rebuild indexes if needed
  let result = await executeQuery(queryParams, params.cachedGraph.raw);

  // Handle query errors
  if (isQueryError(result)) {
    const errorWithHints = {
      ...result,
      hints: getErrorHints(result.error.code, params.query),
    };
    return asTextContentResult(errorWithHints);
  }

  // Add breadcrumb hints to successful results
  const resultWithHints = addBreadcrumbHints(result, params.query);

  return asTextContentResult(resultWithHints);
}

/**
 * Handle query-based requests using the query engine
 */
async function handleQueryMode(
  client: ClientContext,
  params: {
    query: QueryType;
    file: string;
    idempotencyKey: string;
    targetId?: string;
    searchText?: string;
    namePattern?: string;
    filePathPrefix?: string;
    labels?: string[];
    depth?: number;
    relationshipTypes?: string[];
    limit?: number;
    includeRaw?: boolean;
    jq_filter?: string;
  }
): Promise<ReturnType<typeof asTextContentResult>> {
  const queryParams = {
    query: params.query,
    file: params.file,
    idempotencyKey: params.idempotencyKey,
    targetId: params.targetId,
    searchText: params.searchText,
    namePattern: params.namePattern,
    filePathPrefix: params.filePathPrefix,
    labels: params.labels,
    depth: params.depth,
    relationshipTypes: params.relationshipTypes,
    limit: params.limit,
    includeRaw: params.includeRaw,
    jq_filter: params.jq_filter,
  };

  // First, try to execute query from cache
  let result = await executeQuery(queryParams);

  // If cache miss, fetch from API and retry
  if (isQueryError(result) && result.error.code === 'CACHE_MISS') {
    logger.debug('Cache miss, fetching from API...');

    try {
      const apiResponse = await fetchFromApi(client, params.file, params.idempotencyKey);
      result = await executeQuery(queryParams, apiResponse);
    } catch (error: any) {
      // Error details are already logged by fetchFromApi and logErrorResponse
      return asErrorResult(classifyApiError(error));
    }
  }

  // Handle query errors
  if (isQueryError(result)) {
    // Include hints for common errors
    const errorWithHints = {
      ...result,
      hints: getErrorHints(result.error.code, params.query),
    };
    return asTextContentResult(errorWithHints);
  }

  // Add breadcrumb hints to successful results
  const resultWithHints = addBreadcrumbHints(result, params.query);

  return asTextContentResult(resultWithHints);
}

/**
 * Add breadcrumb hints to query results for agent navigation
 */
function addBreadcrumbHints(result: any, queryType: QueryType): any {
  const hints: string[] = [];

  switch (queryType) {
    case 'summary':
      hints.push(
        'NEXT: Use search with searchText to find specific functions/classes',
        'NEXT: Use list_nodes with labels=["Function"] to browse all functions',
        'NEXT: Use domain_map to see architectural domains'
      );
      break;

    case 'search':
    case 'list_nodes':
      if (result.result?.nodes?.length > 0) {
        hints.push(
          'NEXT: Use get_node with targetId to get full details for any node',
          'NEXT: Use function_calls_in with targetId to see who calls a function',
          'NEXT: Use function_calls_out with targetId to see what a function calls'
        );
      }
      break;

    case 'get_node':
      if (result.result?.node) {
        const label = result.result.node.labels?.[0];
        if (label === 'Function') {
          hints.push(
            'NEXT: Use function_calls_in to see callers of this function',
            'NEXT: Use function_calls_out to see functions this calls',
            'NEXT: Use neighborhood with depth=2 to see call graph around this function'
          );
        } else if (label === 'File') {
          hints.push(
            'NEXT: Use definitions_in_file to see all definitions in this file',
            'NEXT: Use file_imports to see import relationships'
          );
        } else if (label === 'Domain') {
          hints.push(
            'NEXT: Use domain_membership to see all members of this domain'
          );
        }
      }
      break;

    case 'function_calls_in':
    case 'function_calls_out':
      if (result.result?.nodes?.length > 0) {
        hints.push(
          'NEXT: Use get_node with any caller/callee ID for full details',
          'NEXT: Chain function_calls_in/out to trace deeper call paths',
          'NEXT: Use neighborhood for broader call graph exploration'
        );
      }
      break;

    case 'definitions_in_file':
      hints.push(
        'NEXT: Use function_calls_in/out on any function ID to trace calls',
        'NEXT: Use get_node for full details on any definition'
      );
      break;

    case 'domain_map':
      hints.push(
        'NEXT: Use domain_membership with domain name to see members',
        'NEXT: Use search to find specific functions within a domain'
      );
      break;
  }

  if (hints.length > 0) {
    return { ...result, hints };
  }

  return result;
}

/**
 * Get hints for specific error conditions
 */
function getErrorHints(errorCode: string, queryType: QueryType): string[] {
  switch (errorCode) {
    case 'NOT_FOUND':
      return [
        'Use search with searchText to find nodes by name',
        'Use list_nodes with labels filter to browse available nodes',
        'Check the targetId format - it should be the full node ID from a previous query'
      ];
    case 'INVALID_PARAMS':
      return [
        `Query '${queryType}' may require specific parameters`,
        'Use graph_status to see available query types and their requirements'
      ];
    default:
      return [];
  }
}

/**
 * Get current timestamp in ISO format
 */
function getTimestamp(): string {
  return new Date().toISOString();
}

/**
 * Log HTTP request details
 */
function logRequest(url: string, method: string, bodySize: number, idempotencyKey: string): void {
  logger.debug(`[${getTimestamp()}] [API REQUEST]`);
  logger.debug(`  Method: ${method}`);
  logger.debug(`  URL: ${url}`);
  logger.debug(`  Idempotency-Key: ${idempotencyKey}`);
  logger.debug(`  Body size: ${formatBytes(bodySize)}`);
  logger.debug(`  Content-Type: multipart/form-data`);
}

/**
 * Log HTTP response details
 */
function logResponse(status: number, statusText: string, responseSize: number, duration: number): void {
  logger.debug(`[${getTimestamp()}] [API RESPONSE]`);
  logger.debug(`  Status: ${status} ${statusText}`);
  logger.debug(`  Response size: ${formatBytes(responseSize)}`);
  logger.debug(`  Duration: ${duration}ms`);
}

/**
 * Log HTTP error with full details
 */
async function logErrorResponse(error: any): Promise<void> {
  logger.error(`[${getTimestamp()}] [API ERROR]`);
  logger.error(`  Error type: ${error.name || 'Unknown'}`);
  logger.error(`  Error message: ${error.message || 'No message'}`);

  if (error.response) {
    const status = error.response.status;
    const statusText = error.response.statusText || '';
    logger.error(`  HTTP Status: ${status} ${statusText}`);

    // Log specific error messages for common status codes
    switch (status) {
      case 401:
        logger.error(`  Unauthorized: Invalid or missing API key`);
        logger.error(`  Check SUPERMODEL_API_KEY environment variable`);
        break;
      case 403:
        logger.error(`  Forbidden: API key valid but lacks permission`);
        break;
      case 404:
        logger.error(`  Not Found: API endpoint does not exist`);
        break;
      case 429:
        logger.error(`  Rate Limited: Too many requests`);
        break;
      case 500:
      case 502:
      case 503:
      case 504:
        logger.error(`  Server Error: Supermodel API is experiencing issues`);
        break;
    }

    // Try to read and log the full error response body
    try {
      const responseText = await error.response.text();
      logger.error(`  Response body: ${responseText}`);
    } catch (e) {
      logger.warn(`  Could not read response body: ${e}`);
    }
  } else if (error.request) {
    logger.error(`  No response received from server`);
    logger.error(`  Possible network issue or timeout`);
  } else {
    logger.error(`  Request setup failed`);
  }

  if (error.stack) {
    logger.error(`  Stack trace: ${error.stack}`);
  }
}

/**
 * Fetch graph from API with comprehensive logging and progress updates
 */
async function fetchFromApi(client: ClientContext, file: string, idempotencyKey: string): Promise<any> {
  const startTime = Date.now();

  logger.debug('Reading file:', file);
  const fileBuffer = await readFile(file);
  const fileBlob = new Blob([fileBuffer], { type: 'application/zip' });
  const fileSize = fileBuffer.length;

  logger.debug('File size:', formatBytes(fileSize));

  // Get the base URL from environment or use default
  const baseUrl = process.env.SUPERMODEL_BASE_URL || 'https://api.supermodeltools.com';
  const apiUrl = `${baseUrl}/v1/graphs/supermodel`;

  // Log the request details
  logRequest(apiUrl, 'POST', fileSize, idempotencyKey);

  const requestParams = {
    file: fileBlob as any,
    idempotencyKey: idempotencyKey,
  };

  // Start progress logging
  console.error('[Supermodel] Starting codebase analysis...');

  // Set up periodic progress updates every 15 seconds
  let progressInterval: NodeJS.Timeout | null = null;
  let elapsedSeconds = 0;

  progressInterval = setInterval(() => {
    elapsedSeconds += 15;
    console.error(`[Supermodel] Analysis in progress... (${elapsedSeconds}s elapsed)`);
  }, 15000);

  try {
    const response = await client.graphs.generateSupermodelGraph(requestParams);
    const duration = Date.now() - startTime;

    // Clear progress interval
    if (progressInterval) {
      clearInterval(progressInterval);
      progressInterval = null;
    }

    // Calculate approximate response size
    const responseSize = JSON.stringify(response).length;
    logResponse(200, 'OK', responseSize, duration);

    // Log completion with summary
    const summary = response.summary;
    if (summary) {
      console.error(`[Supermodel] Analysis complete, retrieving results... (${summary.filesProcessed || 0} files processed)`);
    } else {
      console.error('[Supermodel] Analysis complete, retrieving results...');
    }

    logger.debug(`[${getTimestamp()}] [API SUCCESS] Request completed successfully`);

    return response;
  } catch (error: any) {
    const duration = Date.now() - startTime;

    // Clear progress interval on error
    if (progressInterval) {
      clearInterval(progressInterval);
      progressInterval = null;
    }

    logger.error(`[${getTimestamp()}] [API FAILURE] Request failed after ${duration}ms`);

    // Log detailed error information
    await logErrorResponse(error);

    // Preserve error.response so classifyApiError can read the status code (#75)
    if (error.response?.status === 401) {
      error.message = 'API authentication failed (401 Unauthorized). Please check your SUPERMODEL_API_KEY environment variable.';
    } else if (error.response?.status === 403) {
      error.message = 'API access forbidden (403 Forbidden). Your API key may not have permission to access this resource.';
    } else if (error.response?.status >= 500) {
      error.message = `Supermodel API server error (${error.response.status}). The service may be temporarily unavailable.`;
    }

    throw error;
  }
}

/**
 * Classify an API error into a structured error response.
 * Extracts HTTP status, network conditions, and timeout signals
 * to produce an agent-actionable error with recovery guidance.
 */
export function classifyApiError(error: any): StructuredError {
  // Guard against non-Error throws (strings, nulls, plain objects)
  if (!error || typeof error !== 'object') {
    return {
      type: 'internal_error',
      message: typeof error === 'string' ? error : 'An unexpected error occurred.',
      code: 'UNKNOWN_ERROR',
      recoverable: false,
      reportable: true,
      repo: REPORT_REPO,
      suggestion: REPORT_SUGGESTION,
      details: { errorType: typeof error },
    };
  }

  if (error.response) {
    const status = error.response.status;

    switch (status) {
      case 401:
        return {
          type: 'authentication_error',
          message: 'Invalid or missing API key.',
          code: 'INVALID_API_KEY',
          recoverable: false,
          suggestion: 'Set the SUPERMODEL_API_KEY environment variable and restart the MCP server.',
          details: { apiKeySet: !!process.env.SUPERMODEL_API_KEY, httpStatus: 401 },
        };
      case 403:
        return {
          type: 'authorization_error',
          message: 'API key does not have permission for this operation.',
          code: 'FORBIDDEN',
          recoverable: false,
          suggestion: 'Verify your API key has the correct permissions. Contact support if unexpected.',
          details: { httpStatus: 403 },
        };
      case 404:
        return {
          type: 'not_found_error',
          message: 'API endpoint not found.',
          code: 'ENDPOINT_NOT_FOUND',
          recoverable: false,
          suggestion: 'Check SUPERMODEL_BASE_URL environment variable. Default: https://api.supermodeltools.com',
          details: { baseUrl: process.env.SUPERMODEL_BASE_URL || 'https://api.supermodeltools.com', httpStatus: 404 },
        };
      case 429:
        return {
          type: 'rate_limit_error',
          message: 'API rate limit exceeded.',
          code: 'RATE_LIMITED',
          recoverable: true,
          suggestion: 'Wait 30-60 seconds and retry. Consider analyzing smaller subdirectories to reduce API calls.',
          details: { httpStatus: 429 },
        };
      case 500:
      case 502:
      case 503:
      case 504:
        return {
          type: 'internal_error',
          message: `Supermodel API server error (HTTP ${status}).`,
          code: 'SERVER_ERROR',
          recoverable: true,
          reportable: true,
          repo: REPORT_REPO,
          suggestion: 'The API may be temporarily unavailable. Wait a few minutes and retry. If persistent, open an issue at https://github.com/supermodeltools/mcp/issues with the error details, or fork the repo and open a PR with a fix.',
          details: { httpStatus: status },
        };
      default: {
        const isServerError = status >= 500;
        return {
          type: isServerError ? 'internal_error' : 'validation_error',
          message: `API request failed with HTTP ${status}.`,
          code: 'API_ERROR',
          recoverable: isServerError,
          ...(isServerError && {
            reportable: true,
            repo: REPORT_REPO,
            suggestion: 'The API may be temporarily unavailable. Wait a few minutes and retry. If persistent, open an issue at https://github.com/supermodeltools/mcp/issues with the error details, or fork the repo and open a PR with a fix.',
          }),
          ...(!isServerError && { suggestion: 'Check the request parameters and base URL configuration.' }),
          details: { httpStatus: status },
        };
      }
    }
  }

  if (error.request) {
    // Distinguish timeout from general network failure
    if (error.code === 'UND_ERR_HEADERS_TIMEOUT' || error.code === 'UND_ERR_BODY_TIMEOUT' || error.message?.includes('timeout')) {
      return {
        type: 'timeout_error',
        message: 'API request timed out. The codebase may be too large for a single analysis.',
        code: 'REQUEST_TIMEOUT',
        recoverable: true,
        suggestion: 'Analyze a smaller subdirectory (e.g. directory="/repo/src/core") or increase SUPERMODEL_TIMEOUT_MS.',
      };
    }

    return {
      type: 'network_error',
      message: 'No response from Supermodel API server.',
      code: 'NO_RESPONSE',
      recoverable: true,
      suggestion: 'Check network connectivity. Verify the API is reachable at the configured base URL.',
      details: { baseUrl: process.env.SUPERMODEL_BASE_URL || 'https://api.supermodeltools.com' },
    };
  }

  // Catch-all for unexpected errors - include the actual message
  return {
    type: 'internal_error',
    message: error.message || 'An unexpected error occurred.',
    code: 'UNKNOWN_ERROR',
    recoverable: false,
    reportable: true,
    repo: REPORT_REPO,
    suggestion: REPORT_SUGGESTION,
    details: { errorType: error.name || 'Error' },
  };
}

/**
 * Legacy mode: direct jq filtering on API response
 */
async function handleLegacyMode(
  client: ClientContext,
  file: string,
  idempotencyKey: string,
  jq_filter?: string
): Promise<ReturnType<typeof asTextContentResult>> {
  try {
    const response = await fetchFromApi(client, file, idempotencyKey);
    return asTextContentResult(await maybeFilter(jq_filter, response));
  } catch (error: any) {
    if (isJqError(error)) {
      logger.error('jq filter error:', error.message);
      return asErrorResult({
        type: 'validation_error',
        message: `Invalid jq filter syntax: ${error.message}`,
        code: 'INVALID_JQ_FILTER',
        recoverable: false,
        suggestion: 'Check jq filter syntax. Use the query parameter instead for structured queries (e.g. query="summary").',
      });
    }

    // Error details are already logged by fetchFromApi and logErrorResponse
    return asErrorResult(classifyApiError(error));
  }
}

export default { metadata, tool, handler };
