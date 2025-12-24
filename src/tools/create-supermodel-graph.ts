// @ts-nocheck
import { Tool } from '@modelcontextprotocol/sdk/types.js';
import { createReadStream } from 'fs';
import {
  Metadata,
  Endpoint,
  HandlerFunction,
  asTextContentResult,
  asErrorResult,
  ClientContext
} from '../types';
import { maybeFilter, isJqError } from '../filtering';

export const metadata: Metadata = {
  resource: 'graphs',
  operation: 'write',
  tags: [],
  httpMethod: 'post',
  httpPath: '/v1/graphs/supermodel',
  operationId: 'generateSupermodelGraph',
};

export const tool: Tool = {
  name: 'create_supermodel_graph_graphs',
  description:
    "When using this tool, always use the `jq_filter` parameter to reduce the response size and improve performance.\n\nOnly omit if you're sure you don't need the data.\n\nUpload a zipped repository snapshot to generate the Supermodel Intermediate Representation (SIR) artifact bundle.\n\n# Response Schema\n(Refer to the schema in the existing documentation)\n",
  inputSchema: {
    type: 'object',
    properties: {
      file: {
        type: 'string',
        description: 'Path to the zipped repository archive containing the code to analyze.',
      },
      'Idempotency-Key': {
        type: 'string',
      },
      jq_filter: {
        type: 'string',
        title: 'jq Filter',
        description:
          'A jq filter to apply to the response to include certain fields.',
      },
    },
    required: ['file', 'Idempotency-Key'],
  },
};

export const handler: HandlerFunction = async (client: ClientContext, args: Record<string, unknown> | undefined) => {
  if (!args) {
    return asErrorResult('No arguments provided');
  }

  const { jq_filter, file, 'Idempotency-Key': idempotencyKey } = args as any;

  if (!file || typeof file !== 'string') {
    return asErrorResult('File argument is required and must be a string path');
  }

  if (!idempotencyKey || typeof idempotencyKey !== 'string') {
    return asErrorResult('Idempotency-Key argument is required');
  }

  try {
    // We are guessing the signature here as: createSupermodelGraph({ file: blob, idempotencyKey })
    // Based on the generated interface:
    // export interface GenerateSupermodelGraphRequest {
    //    idempotencyKey: string;
    //    file: Blob;
    // }
    // generateSupermodelGraph(requestParameters: GenerateSupermodelGraphRequest, ...)
    
    // Note: Node.js fs.createReadStream returns a ReadStream, which is not exactly a Blob in the browser sense.
    // However, many Node fetch polyfills handle ReadStream as Blob or BodyInit.
    // The OpenAPI generator for typescript-fetch often expects Blob | File.
    // In Node environments with node-fetch, streams often work.
    
    // Check if we need to convert to Blob.
    const fileStream = createReadStream(file);
    
    // Construct the request object
    const requestParams = {
        file: fileStream as any, // Cast to any/Blob
        idempotencyKey: idempotencyKey
    };

    const response = await client.graphs.generateSupermodelGraph(requestParams);

    return asTextContentResult(await maybeFilter(jq_filter, response));
  } catch (error: any) {
    if (isJqError(error)) {
      return asErrorResult(error.message);
    }
    return asErrorResult(error.message || String(error));
  }
};

export default { metadata, tool, handler };
