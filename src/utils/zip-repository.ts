/**
 * Automatic repository zipping with gitignore support
 * Creates temporary ZIP files for codebase analysis
 */

import { createWriteStream, promises as fs } from 'fs';
import { join, relative, sep } from 'path';
import { tmpdir } from 'os';
import archiver from 'archiver';
import ignore, { Ignore } from 'ignore';
import { randomBytes } from 'crypto';

/**
 * Standard exclusions for security and size optimization
 * These patterns are applied in addition to .gitignore
 */
const STANDARD_EXCLUSIONS = [
  // Version control
  '.git',
  '.svn',
  '.hg',

  // Dependencies
  'node_modules',
  'vendor',
  'venv',
  '.venv',
  'env',
  'virtualenv',
  'target', // Rust/Java

  // Build outputs
  'dist',
  'build',
  'out',
  '.next',
  '__pycache__',
  '*.pyc',
  '*.pyo',
  '*.so',
  '*.dylib',
  '*.dll',
  '*.class',

  // IDE files
  '.idea',
  '.vscode',
  '.vs',
  '*.swp',
  '*.swo',
  '*~',
  '.DS_Store',

  // Sensitive files (CRITICAL - prevent credential leaks)
  '.env',
  '.env.local',
  '.env.*.local',
  '*.pem',
  '*.key',
  '*.p12',
  '*.pfx',
  '*.jks',
  'secrets.yml',
  'secrets.yaml',
  'secrets.json',
  'credentials.json',
  'serviceaccount.json',
  '.aws/credentials',
  '.ssh/id_rsa',
  '.ssh/id_ed25519',

  // Large binary files
  '*.mp4',
  '*.avi',
  '*.mov',
  '*.zip',
  '*.tar',
  '*.gz',
  '*.rar',
  '*.7z',
  '*.iso',
  '*.dmg',
];

export interface ZipResult {
  /** Path to the created ZIP file */
  path: string;

  /** Cleanup function to delete the ZIP file */
  cleanup: () => Promise<void>;

  /** Number of files included in the ZIP */
  fileCount: number;

  /** Total size in bytes */
  sizeBytes: number;
}

export interface ZipOptions {
  /** Maximum ZIP size in bytes (default: 500MB) */
  maxSizeBytes?: number;

  /** Custom patterns to exclude (in addition to standard exclusions) */
  additionalExclusions?: string[];
}

/**
 * Create a ZIP archive of a directory with gitignore support
 */
export async function zipRepository(
  directoryPath: string,
  options: ZipOptions = {}
): Promise<ZipResult> {
  const maxSizeBytes = options.maxSizeBytes || 500 * 1024 * 1024; // 500MB default

  // Validate directory exists
  try {
    const stats = await fs.stat(directoryPath);
    if (!stats.isDirectory()) {
      throw new Error(`Path is not a directory: ${directoryPath}`);
    }
  } catch (error: any) {
    if (error.code === 'ENOENT') {
      throw new Error(`Directory does not exist: ${directoryPath}`);
    }
    if (error.code === 'EACCES') {
      throw new Error(`Permission denied accessing directory: ${directoryPath}`);
    }
    throw error;
  }

  // Parse gitignore files
  const ignoreFilter = await buildIgnoreFilter(directoryPath, options.additionalExclusions);

  // Create temp file path
  const tempDir = tmpdir();
  const zipFileName = `supermodel-${randomBytes(8).toString('hex')}.zip`;
  const zipPath = join(tempDir, zipFileName);

  console.error('[DEBUG] Creating ZIP:', zipPath);
  console.error('[DEBUG] Source directory:', directoryPath);

  // Create ZIP archive
  let fileCount = 0;
  let totalSize = 0;

  const output = createWriteStream(zipPath);
  const archive = archiver('zip', {
    zlib: { level: 6 } // Balanced compression
  });

  // Track errors
  let archiveError: Error | null = null;

  archive.on('error', (err) => {
    archiveError = err;
  });

  archive.on('warning', (err) => {
    if (err.code === 'ENOENT') {
      console.error('[WARN] File not found (skipping):', err.message);
    } else {
      console.error('[WARN] Archive warning:', err.message);
    }
  });

  // Track progress
  archive.on('entry', (entry) => {
    fileCount++;
    totalSize += entry.stats?.size || 0;

    // Check size limit
    if (totalSize > maxSizeBytes) {
      archive.abort();
      archiveError = new Error(
        `ZIP size exceeds limit (${formatBytes(maxSizeBytes)}). ` +
        `Current size: ${formatBytes(totalSize)}. ` +
        `Consider excluding more directories or analyzing a subdirectory.`
      );
    }
  });

  // Pipe to file
  archive.pipe(output);

  // Add files recursively with filtering
  await addFilesRecursively(archive, directoryPath, directoryPath, ignoreFilter);

  // Finalize archive
  await archive.finalize();

  // Wait for output stream to finish
  await new Promise<void>((resolve, reject) => {
    output.on('close', () => {
      if (archiveError) {
        reject(archiveError);
      } else {
        resolve();
      }
    });
    output.on('error', reject);
  });

  // Check for errors during archiving
  if (archiveError) {
    // Clean up partial ZIP
    await fs.unlink(zipPath).catch(() => {});
    throw archiveError;
  }

  // Get final file size
  const zipStats = await fs.stat(zipPath);
  const zipSizeBytes = zipStats.size;

  console.error('[DEBUG] ZIP created successfully');
  console.error('[DEBUG] Files included:', fileCount);
  console.error('[DEBUG] ZIP size:', formatBytes(zipSizeBytes));

  // Create cleanup function
  const cleanup = async () => {
    try {
      await fs.unlink(zipPath);
      console.error('[DEBUG] Cleaned up ZIP:', zipPath);
    } catch (error: any) {
      if (error.code !== 'ENOENT') {
        console.error('[WARN] Failed to cleanup ZIP:', error.message);
      }
    }
  };

  return {
    path: zipPath,
    cleanup,
    fileCount,
    sizeBytes: zipSizeBytes,
  };
}

/**
 * Build ignore filter from .gitignore files and standard exclusions
 */
async function buildIgnoreFilter(
  rootDir: string,
  additionalExclusions: string[] = []
): Promise<Ignore> {
  const ig = ignore();

  // Add standard exclusions
  ig.add(STANDARD_EXCLUSIONS);

  // Add custom exclusions
  if (additionalExclusions.length > 0) {
    ig.add(additionalExclusions);
  }

  // Parse .gitignore in root
  const gitignorePath = join(rootDir, '.gitignore');
  try {
    const gitignoreContent = await fs.readFile(gitignorePath, 'utf-8');
    const patterns = gitignoreContent
      .split('\n')
      .map(line => line.trim())
      .filter(line => line && !line.startsWith('#'));

    if (patterns.length > 0) {
      ig.add(patterns);
      console.error('[DEBUG] Loaded .gitignore with', patterns.length, 'patterns');
    }
  } catch (error: any) {
    if (error.code !== 'ENOENT') {
      console.error('[WARN] Failed to read .gitignore:', error.message);
    }
  }

  return ig;
}

/**
 * Recursively add files to archive with filtering
 */
async function addFilesRecursively(
  archive: archiver.Archiver,
  rootDir: string,
  currentDir: string,
  ignoreFilter: Ignore
): Promise<void> {
  let entries: string[];

  try {
    entries = await fs.readdir(currentDir);
  } catch (error: any) {
    if (error.code === 'EACCES') {
      console.error('[WARN] Permission denied:', currentDir);
      return;
    }
    throw error;
  }

  for (const entry of entries) {
    const fullPath = join(currentDir, entry);
    const relativePath = relative(rootDir, fullPath);

    // Normalize path for ignore matching (use forward slashes)
    const normalizedRelativePath = relativePath.split(sep).join('/');

    // Check if ignored
    if (ignoreFilter.ignores(normalizedRelativePath)) {
      continue;
    }

    let stats;
    try {
      stats = await fs.stat(fullPath);
    } catch (error: any) {
      if (error.code === 'ENOENT') {
        // Symlink pointing to non-existent file, skip
        continue;
      }
      console.error('[WARN] Failed to stat:', fullPath, error.message);
      continue;
    }

    if (stats.isDirectory()) {
      // Check if directory itself should be ignored
      const dirPath = normalizedRelativePath + '/';
      if (ignoreFilter.ignores(dirPath)) {
        continue;
      }

      // Recurse into directory
      await addFilesRecursively(archive, rootDir, fullPath, ignoreFilter);
    } else if (stats.isFile()) {
      // Add file to archive
      try {
        archive.file(fullPath, { name: normalizedRelativePath });
      } catch (error: any) {
        console.error('[WARN] Failed to add file:', fullPath, error.message);
      }
    }
    // Skip symlinks, sockets, etc.
  }
}

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
 * Clean up old ZIP files from temp directory
 * Removes ZIPs older than the specified age
 */
export async function cleanupOldZips(maxAgeMs: number = 24 * 60 * 60 * 1000): Promise<void> {
  const tempDir = tmpdir();
  const now = Date.now();

  try {
    const entries = await fs.readdir(tempDir);
    let removedCount = 0;

    for (const entry of entries) {
      // Only process our ZIP files
      if (!entry.startsWith('supermodel-') || !entry.endsWith('.zip')) {
        continue;
      }

      const fullPath = join(tempDir, entry);

      try {
        const stats = await fs.stat(fullPath);
        const ageMs = now - stats.mtimeMs;

        if (ageMs > maxAgeMs) {
          await fs.unlink(fullPath);
          removedCount++;
        }
      } catch (error: any) {
        // File might have been deleted already, ignore
        if (error.code !== 'ENOENT') {
          console.error('[WARN] Failed to cleanup:', fullPath, error.message);
        }
      }
    }

    if (removedCount > 0) {
      console.error('[DEBUG] Cleaned up', removedCount, 'old ZIP files');
    }
  } catch (error: any) {
    console.error('[WARN] Failed to cleanup temp directory:', error.message);
  }
}
