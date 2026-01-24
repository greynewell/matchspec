import { SupermodelClient } from '@supermodeltools/sdk';
import { Tool } from '@modelcontextprotocol/sdk/types.js';

export interface ClientContext {
  graphs: SupermodelClient;
}

export type ContentBlock = 
  | { type: 'text'; text: string }
  | { type: 'image'; data: string; mimeType: string }
  | { type: 'audio'; data: string; mimeType: string }
  | { type: 'resource'; resource: any };

export type ToolCallResult = {
  content: ContentBlock[];
  isError?: boolean;
};

export type HandlerFunction = (
  client: ClientContext,
  args: Record<string, unknown> | undefined,
  defaultWorkdir?: string
) => Promise<ToolCallResult>;

export type Metadata = {
  resource: string;
  operation: 'read' | 'write';
  tags: string[];
  httpMethod?: string;
  httpPath?: string;
  operationId?: string;
};

export type Endpoint = {
  metadata: Metadata;
  tool: Tool;
  handler: HandlerFunction;
};

export function asTextContentResult(result: unknown): ToolCallResult {
  return {
    content: [
      {
        type: 'text',
        text: typeof result === 'string' ? result : JSON.stringify(result, null, 2),
      },
    ],
    isError: false
  };
}

/**
 * Structured error types for agent-parseable error responses.
 * Agents can use these to decide whether to retry, fallback, or report.
 */
export type ErrorType =
  | 'authentication_error'
  | 'authorization_error'
  | 'rate_limit_error'
  | 'timeout_error'
  | 'resource_error'
  | 'validation_error'
  | 'network_error'
  | 'internal_error'
  | 'not_found_error';

export interface StructuredError {
  type: ErrorType;
  message: string;
  code: string;
  recoverable: boolean;
  suggestion?: string;
  details?: Record<string, unknown>;
  reportable?: boolean;
  repo?: string;
}

export function asErrorResult(error: string | StructuredError): ToolCallResult {
  const text = typeof error === 'string'
    ? error
    : JSON.stringify({ error }, null, 2);

  return {
    content: [
      {
        type: 'text',
        text,
      },
    ],
    isError: true,
  };
}

