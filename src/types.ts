import { DefaultApi } from '@supermodeltools/sdk';
import { Tool } from '@modelcontextprotocol/sdk/types.js';

export interface ClientContext {
  graphs: DefaultApi;
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
  args: Record<string, unknown> | undefined
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

export function asErrorResult(message: string): ToolCallResult {
  return {
    content: [
      {
        type: 'text',
        text: message,
      },
    ],
    isError: true,
  };
}

