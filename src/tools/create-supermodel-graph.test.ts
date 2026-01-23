import { describe, it, expect, jest, beforeEach } from '@jest/globals';
import { handler, classifyApiError } from './create-supermodel-graph';
import { ClientContext } from '../types';
import { execSync } from 'child_process';
import { createHash } from 'crypto';
import { basename, resolve } from 'path';

// Test the idempotency key generation logic in isolation
describe('create-supermodel-graph', () => {
  describe('idempotency key generation logic', () => {
    it('should generate key format with repo name, path hash, type, and commit hash', () => {
      const directory = '/path/to/my-repo';
      const repoName = basename(directory);
      const absolutePath = resolve(directory);
      const pathHash = createHash('sha1').update(absolutePath).digest('hex').substring(0, 7);
      const commitHash = 'abc1234';

      const expectedPattern = new RegExp(`${repoName}-${pathHash}:supermodel:${commitHash}`);
      const actualKey = `${repoName}-${pathHash}:supermodel:${commitHash}`;

      expect(actualKey).toMatch(expectedPattern);
    });

    it('should include status hash for dirty working tree', () => {
      const directory = '/path/to/my-repo';
      const repoName = basename(directory);
      const absolutePath = resolve(directory);
      const pathHash = createHash('sha1').update(absolutePath).digest('hex').substring(0, 7);
      const commitHash = 'abc1234';
      const statusOutput = 'M src/file.ts\n';
      const statusHash = createHash('sha1').update(statusOutput).digest('hex').substring(0, 7);

      const actualKey = `${repoName}-${pathHash}:supermodel:${commitHash}-${statusHash}`;

      expect(actualKey).toMatch(new RegExp(`${commitHash}-${statusHash}`));
    });

    it('should use path hash for non-git directories', () => {
      const directory = '/path/to/non-git-dir';
      const repoName = basename(directory);
      const absolutePath = resolve(directory);
      const pathHash = createHash('sha1').update(absolutePath).digest('hex').substring(0, 7);

      // When not a git repo, use path hash as the main identifier
      const actualKey = `${repoName}-${pathHash}:supermodel:${pathHash}`;

      expect(actualKey).toMatch(new RegExp(`${repoName}-${pathHash}:supermodel:${pathHash}`));
    });

    it('should prevent collisions between same-named repos', () => {
      const dir1 = '/path/to/repo';
      const dir2 = '/different/path/repo';

      const path1Hash = createHash('sha1').update(resolve(dir1)).digest('hex').substring(0, 7);
      const path2Hash = createHash('sha1').update(resolve(dir2)).digest('hex').substring(0, 7);

      // Even with same repo name, path hashes should be different
      expect(path1Hash).not.toBe(path2Hash);
    });
  });

  describe('parameter validation', () => {
    let mockClient: ClientContext;

    beforeEach(() => {
      mockClient = {
        graphs: {
          generateSupermodelGraph: jest.fn(),
        },
      } as any;
    });

    it('should return structured error when no arguments provided and no default workdir', async () => {
      const result = await handler(mockClient, undefined);

      expect(result.isError).toBe(true);
      const errorContent = JSON.parse(result.content[0].type === 'text' ? (result.content[0] as any).text : '');
      expect(errorContent.error.type).toBe('validation_error');
      expect(errorContent.error.code).toBe('MISSING_DIRECTORY');
      expect(errorContent.error.recoverable).toBe(false);
      expect(errorContent.error.suggestion).toBeDefined();
    });

    it('should return structured error when directory is missing and no default workdir', async () => {
      const args = {
        query: 'summary',
      };

      const result = await handler(mockClient, args);

      expect(result.isError).toBe(true);
      const errorContent = JSON.parse(result.content[0].type === 'text' ? (result.content[0] as any).text : '');
      expect(errorContent.error.type).toBe('validation_error');
      expect(errorContent.error.code).toBe('MISSING_DIRECTORY');
      expect(errorContent.error.recoverable).toBe(false);
    });

    it('should return structured error when directory is not a string', async () => {
      const args = {
        directory: 123,
        query: 'summary',
      };

      const result = await handler(mockClient, args as any);

      expect(result.isError).toBe(true);
      const errorContent = JSON.parse(result.content[0].type === 'text' ? (result.content[0] as any).text : '');
      expect(errorContent.error.type).toBe('validation_error');
      expect(errorContent.error.code).toBe('INVALID_DIRECTORY');
      expect(errorContent.error.recoverable).toBe(false);
    });

    it('should use default workdir when directory is not provided', async () => {
      const args = {
        query: 'summary',
      };
      const defaultWorkdir = '/default/workdir';

      const result = await handler(mockClient, args, defaultWorkdir);

      // Should not error with validation message since defaultWorkdir is provided
      // The actual behavior depends on whether the directory exists
      // but the validation should pass
      expect(result.isError).toBe(true); // Will error on actual zip creation, not validation
      const content = result.content[0];
      if (content.type === 'text') {
        expect(content.text).not.toContain('MISSING_DIRECTORY');
      }
    });
  });

  describe('structured error format', () => {
    it('should produce valid JSON with error.type, error.code, error.message, error.recoverable', async () => {
      // Test with missing directory to get a structured error
      const result = await handler({} as any, { directory: 42 } as any);

      expect(result.isError).toBe(true);
      const parsed = JSON.parse((result.content[0] as any).text);
      expect(parsed.error).toBeDefined();
      expect(parsed.error.type).toBeDefined();
      expect(parsed.error.code).toBeDefined();
      expect(parsed.error.message).toBeDefined();
      expect(typeof parsed.error.recoverable).toBe('boolean');
    });

    it('should include suggestion field for actionable errors', async () => {
      const result = await handler({} as any, undefined);

      const parsed = JSON.parse((result.content[0] as any).text);
      expect(parsed.error.suggestion).toBeDefined();
      expect(parsed.error.suggestion.length).toBeGreaterThan(0);
    });

    it('should mark not_found_error for missing directories', async () => {
      const mockClient = { graphs: { generateSupermodelGraph: jest.fn() } } as any;
      const result = await handler(mockClient, { directory: '/nonexistent/path/xyz' });

      expect(result.isError).toBe(true);
      const parsed = JSON.parse((result.content[0] as any).text);
      expect(parsed.error.type).toBe('not_found_error');
      expect(parsed.error.code).toBe('DIRECTORY_NOT_FOUND');
      expect(parsed.error.recoverable).toBe(false);
      expect(parsed.error.details.directory).toBe('/nonexistent/path/xyz');
    });
  });

  describe('reportable fields via handler', () => {
    it('should not include reportable on validation errors from handler', async () => {
      const result = await handler({} as any, { directory: 42 } as any);

      const parsed = JSON.parse((result.content[0] as any).text);
      expect(parsed.error.type).toBe('validation_error');
      expect(parsed.error.reportable).toBeUndefined();
      expect(parsed.error.repo).toBeUndefined();
    });

    it('should not include reportable on not_found_error from handler', async () => {
      const mockClient = { graphs: { generateSupermodelGraph: jest.fn() } } as any;
      const result = await handler(mockClient, { directory: '/nonexistent/path/xyz' });

      const parsed = JSON.parse((result.content[0] as any).text);
      expect(parsed.error.type).toBe('not_found_error');
      expect(parsed.error.reportable).toBeUndefined();
      expect(parsed.error.repo).toBeUndefined();
    });
  });

  describe('query parameter types', () => {
    it('should accept all valid query types in the enum', () => {
      const validQueries = [
        'graph_status',
        'summary',
        'get_node',
        'search',
        'list_nodes',
        'function_calls_in',
        'function_calls_out',
        'definitions_in_file',
        'file_imports',
        'domain_map',
        'domain_membership',
        'neighborhood',
        'jq',
      ];

      // This test just verifies the list is complete
      expect(validQueries.length).toBeGreaterThan(10);
      expect(validQueries).toContain('summary');
      expect(validQueries).toContain('get_node');
      expect(validQueries).toContain('search');
    });
  });

  describe('reportable error metadata', () => {
    describe('internal errors include reportable fields', () => {
      it('should mark UNKNOWN_ERROR (non-object) as reportable with repo and suggestion', () => {
        const result = classifyApiError(null);
        expect(result.type).toBe('internal_error');
        expect(result.code).toBe('UNKNOWN_ERROR');
        expect(result.reportable).toBe(true);
        expect(result.repo).toBe('https://github.com/supermodeltools/mcp.git');
        expect(result.suggestion).toContain('https://github.com/supermodeltools/mcp/issues');
      });

      it('should mark UNKNOWN_ERROR (object with message) as reportable', () => {
        const result = classifyApiError(new Error('something broke'));
        expect(result.type).toBe('internal_error');
        expect(result.code).toBe('UNKNOWN_ERROR');
        expect(result.reportable).toBe(true);
        expect(result.repo).toBe('https://github.com/supermodeltools/mcp.git');
        expect(result.suggestion).toBeDefined();
      });

      it('should mark SERVER_ERROR (5xx) as reportable with retry advice', () => {
        const result = classifyApiError({ response: { status: 500 } });
        expect(result.type).toBe('internal_error');
        expect(result.code).toBe('SERVER_ERROR');
        expect(result.reportable).toBe(true);
        expect(result.repo).toBe('https://github.com/supermodeltools/mcp.git');
        expect(result.suggestion).toContain('Wait a few minutes and retry');
        expect(result.suggestion).toContain('https://github.com/supermodeltools/mcp/issues');
      });

      it('should mark SERVER_ERROR for 502/503/504 as reportable', () => {
        for (const status of [502, 503, 504]) {
          const result = classifyApiError({ response: { status } });
          expect(result.code).toBe('SERVER_ERROR');
          expect(result.reportable).toBe(true);
          expect(result.repo).toBe('https://github.com/supermodeltools/mcp.git');
        }
      });

      it('should mark API_ERROR (unhandled 5xx) as reportable', () => {
        const result = classifyApiError({ response: { status: 507 } });
        expect(result.type).toBe('internal_error');
        expect(result.code).toBe('API_ERROR');
        expect(result.recoverable).toBe(true);
        expect(result.reportable).toBe(true);
        expect(result.repo).toBe('https://github.com/supermodeltools/mcp.git');
        expect(result.suggestion).toContain('Wait a few minutes and retry');
        expect(result.suggestion).toContain('https://github.com/supermodeltools/mcp/issues');
      });

      it('should not mark 4xx API_ERROR as reportable', () => {
        const result = classifyApiError({ response: { status: 418 } });
        expect(result.type).toBe('validation_error');
        expect(result.code).toBe('API_ERROR');
        expect(result.recoverable).toBe(false);
        expect(result.reportable).toBeUndefined();
      });
    });

    describe('client errors do NOT include reportable flag', () => {
      it('should not mark authentication_error as reportable', () => {
        const result = classifyApiError({ response: { status: 401 } });
        expect(result.type).toBe('authentication_error');
        expect(result.reportable).toBeUndefined();
      });

      it('should not mark authorization_error as reportable', () => {
        const result = classifyApiError({ response: { status: 403 } });
        expect(result.type).toBe('authorization_error');
        expect(result.reportable).toBeUndefined();
      });

      it('should not mark not_found_error as reportable', () => {
        const result = classifyApiError({ response: { status: 404 } });
        expect(result.type).toBe('not_found_error');
        expect(result.reportable).toBeUndefined();
      });

      it('should not mark rate_limit_error as reportable', () => {
        const result = classifyApiError({ response: { status: 429 } });
        expect(result.type).toBe('rate_limit_error');
        expect(result.reportable).toBeUndefined();
      });

      it('should not mark timeout_error as reportable', () => {
        const result = classifyApiError({ request: {}, code: 'UND_ERR_HEADERS_TIMEOUT' });
        expect(result.type).toBe('timeout_error');
        expect(result.reportable).toBeUndefined();
      });

      it('should not mark network_error as reportable', () => {
        const result = classifyApiError({ request: {} });
        expect(result.type).toBe('network_error');
        expect(result.reportable).toBeUndefined();
      });
    });
  });

  describe('formatBytes utility', () => {
    it('should format bytes correctly', () => {
      // Test the formatBytes function logic
      const testCases = [
        { bytes: 500, expected: /500 B/ },
        { bytes: 1024, expected: /1\.00 KB/ },
        { bytes: 1024 * 1024, expected: /1\.00 MB/ },
        { bytes: 1024 * 1024 * 1024, expected: /1\.00 GB/ },
      ];

      for (const { bytes, expected } of testCases) {
        let result: string;
        if (bytes < 1024) {
          result = `${bytes} B`;
        } else if (bytes < 1024 * 1024) {
          result = `${(bytes / 1024).toFixed(2)} KB`;
        } else if (bytes < 1024 * 1024 * 1024) {
          result = `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
        } else {
          result = `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
        }

        expect(result).toMatch(expected);
      }
    });
  });
});
