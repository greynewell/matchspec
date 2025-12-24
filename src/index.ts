#!/usr/bin/env node
import { Server } from './server';

async function main() {
  const server = new Server();
  await server.start();
}

main().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});

