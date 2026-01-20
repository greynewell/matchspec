/**
 * Simple logging utility with environment variable control
 *
 * Usage:
 *   DEBUG=true node dist/index.js  # Enable debug logging
 *   node dist/index.js             # Disable debug logging
 */

const DEBUG = process.env.DEBUG === 'true';

/**
 * Debug log - only shown when DEBUG=true
 * Uses stderr to keep separate from application output
 */
export function debug(msg: string, ...args: any[]) {
  if (DEBUG) {
    console.error('[DEBUG]', msg, ...args);
  }
}

/**
 * Info log - informational messages to stdout
 */
export function info(msg: string, ...args: any[]) {
  console.log('[INFO]', msg, ...args);
}

/**
 * Warning log - warnings to stderr
 */
export function warn(msg: string, ...args: any[]) {
  console.error('[WARN]', msg, ...args);
}

/**
 * Error log - errors to stderr
 */
export function error(msg: string, ...args: any[]) {
  console.error('[ERROR]', msg, ...args);
}
