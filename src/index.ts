#!/usr/bin/env node
import { Server } from './server';
import * as logger from './utils/logger';

async function main() {
  const server = new Server();
  await server.start();
}

main().catch((error) => {
  logger.error('Fatal error:', error);
  process.exit(1);
});

