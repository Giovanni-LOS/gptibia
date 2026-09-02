import { timingSafeEqual } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { DatabaseSync, constants as sqliteConstants } from 'node:sqlite';
import { resolve } from 'node:path';

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { SSEServerTransport } from '@modelcontextprotocol/sdk/server/sse.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import express from 'express';


const HOST = process.env.TIBIAWIKI_MCP_HOST || '127.0.0.1';
const PORT = Number(process.env.TIBIAWIKI_MCP_PORT || '3000');
const DATABASE_PATH = resolve(
  process.env.TIBIAWIKI_DATABASE || new URL('../data/tibiawiki.db', import.meta.url).pathname,
);
const TOKEN_FILE = resolve(
  process.env.TIBIAWIKI_MCP_TOKEN_FILE || new URL('../.runtime/tibiawiki_mcp_token', import.meta.url).pathname,
);
const API_TOKEN = readFileSync(TOKEN_FILE, 'utf8').trim();
const MAX_ROWS = 20;
const MAX_QUERY_BYTES = 4096;
const sessions = new Map();
const deniedFunctions = new Set(['load_extension', 'readfile', 'writefile', 'fts3_tokenizer']);
const allowedActions = new Set([
  sqliteConstants.SQLITE_FUNCTION,
  sqliteConstants.SQLITE_READ,
  sqliteConstants.SQLITE_RECURSIVE,
  sqliteConstants.SQLITE_SELECT,
]);

if (API_TOKEN.length < 32) {
  throw new Error('The MCP Bearer token must contain at least 32 characters.');
}

function secureEquals(left, right) {
  const leftBuffer = Buffer.from(left);
  const rightBuffer = Buffer.from(right);
  return leftBuffer.length === rightBuffer.length && timingSafeEqual(leftBuffer, rightBuffer);
}

function requireBearerToken(request, response, next) {
  const expected = `Bearer ${API_TOKEN}`;
  if (!secureEquals(request.get('authorization') || '', expected)) {
    response.status(401).json({ error: 'Unauthorized.' });
    return;
  }
  next();
}

function normalizeQuery(rawQuery) {
  if (typeof rawQuery !== 'string' || !rawQuery.trim()) {
    throw new Error('The query field must be a non-empty string.');
  }
  let query = rawQuery.trim().replace(/;\s*$/, '').trim();
  if (Buffer.byteLength(query, 'utf8') > MAX_QUERY_BYTES) {
    throw new Error(`The query exceeds ${MAX_QUERY_BYTES} bytes.`);
  }
  if (query.includes(';')) {
    throw new Error('Only one SQL statement is allowed.');
  }
  if (!/^select\b/i.test(query)) {
    throw new Error('Only SELECT statements are allowed.');
  }
  return query;
}

function withReadOnlyDatabase(callback) {
  const database = new DatabaseSync(DATABASE_PATH, {
    open: true,
    readOnly: true,
    allowExtension: false,
  });
  try {
    database.exec('PRAGMA query_only = ON');
    database.enableDefensive(true);
    database.setAuthorizer((action, _arg1, arg2) => {
      if (!allowedActions.has(action)) return sqliteConstants.SQLITE_DENY;
      if (
        action === sqliteConstants.SQLITE_FUNCTION &&
        deniedFunctions.has(String(arg2 || '').toLowerCase())
      ) {
        return sqliteConstants.SQLITE_DENY;
      }
      return sqliteConstants.SQLITE_OK;
    });
    return callback(database);
  } finally {
    database.close();
  }
}

function executeQuery(rawQuery) {
  const query = normalizeQuery(rawQuery);
  return withReadOnlyDatabase((database) => {
    const statement = database.prepare(
      `SELECT * FROM (${query}) AS result LIMIT ${MAX_ROWS + 1}`,
    );
    statement.setReturnArrays(false);
    const rows = statement.all();
    return {
      rows: rows.slice(0, MAX_ROWS),
      count: Math.min(rows.length, MAX_ROWS),
      truncated: rows.length > MAX_ROWS,
      max_rows: MAX_ROWS,
    };
  });
}

function listTables() {
  return executeQuery(
    "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name LIMIT 20",
  );
}

function createMcpServer() {
  const server = new Server(
    { name: 'gptibia-tibiawiki-sse', version: '1.0.0' },
    { capabilities: { tools: {} } },
  );

  server.setRequestHandler(ListToolsRequestSchema, async () => ({
    tools: [
      {
        name: 'sqlite_read_query',
        description:
          'Execute one read-only SELECT against TibiaWiki SQLite. Results are limited to 20 rows.',
        inputSchema: {
          type: 'object',
          properties: { query: { type: 'string' } },
          required: ['query'],
          additionalProperties: false,
        },
      },
      {
        name: 'sqlite_list_tables',
        description: 'List the first 20 tables in the TibiaWiki SQLite database.',
        inputSchema: { type: 'object', properties: {}, additionalProperties: false },
      },
    ],
  }));

  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    try {
      let result;
      if (request.params.name === 'sqlite_read_query') {
        result = executeQuery(request.params.arguments?.query);
      } else if (request.params.name === 'sqlite_list_tables') {
        result = listTables();
      } else {
        throw new Error(`Unknown tool: ${request.params.name}`);
      }
      return { content: [{ type: 'text', text: JSON.stringify(result) }] };
    } catch (error) {
      return {
        content: [{ type: 'text', text: String(error.message || error) }],
        isError: true,
      };
    }
  });

  return server;
}

const app = express();
app.disable('x-powered-by');
app.use(express.json({ limit: '16kb' }));

app.get('/health', (_request, response) => {
  response.json({ status: 'healthy', service: 'tibiawiki-mcp-sse' });
});

app.get('/sse', requireBearerToken, async (_request, response) => {
  response.setHeader('X-Accel-Buffering', 'no');
  const transport = new SSEServerTransport('/messages', response);
  const server = createMcpServer();
  const heartbeat = setInterval(() => response.write(': keepalive\n\n'), 15_000);
  const sessionId = transport.sessionId;
  sessions.set(sessionId, { server, transport });

  transport.onclose = () => {
    clearInterval(heartbeat);
    sessions.delete(sessionId);
  };

  try {
    await server.connect(transport);
    response.flushHeaders();
    response.write(`: ${' '.repeat(2048)}\n\n`);
  } catch (error) {
    clearInterval(heartbeat);
    sessions.delete(sessionId);
    if (!response.headersSent) response.status(500).json({ error: String(error) });
  }
});

app.post('/messages', requireBearerToken, async (request, response) => {
  const session = sessions.get(String(request.query.sessionId || ''));
  if (!session) {
    response.status(404).json({ error: 'Unknown or expired SSE session.' });
    return;
  }
  await session.transport.handlePostMessage(request, response, request.body);
});

const httpServer = app.listen(PORT, HOST, () => {
  console.log(`TibiaWiki MCP SSE: http://${HOST}:${PORT}/sse`);
  console.log(`Health check:      http://${HOST}:${PORT}/health`);
});

function shutdown() {
  for (const { transport } of sessions.values()) transport.close();
  httpServer.close(() => process.exit(0));
}

process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
