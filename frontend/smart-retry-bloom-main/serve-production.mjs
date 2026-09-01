import { createServer } from 'node:http';
import { readFile, readdir } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, relative } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const serverEntry = join(__dirname, '.output', 'server', 'index.mjs');
const publicDir = join(__dirname, '.output', 'public');
const port = Number(process.env.PORT || 3001);

const serverModule = await import('file://' + serverEntry);
const handler = serverModule.default || serverModule;

async function findMatchingPublicAsset(requestedPath) {
  const requestedFile = requestedPath.split('/').pop() || '';
  if (!requestedFile || !requestedFile.includes('.')) {
    return null;
  }

  const extension = requestedFile.slice(requestedFile.lastIndexOf('.') + 1).toLowerCase();
  const stem = requestedFile.slice(0, requestedFile.lastIndexOf('.'));
  const prefix = stem.split('-')[0] || stem;

  if (!prefix) {
    return null;
  }

  const candidates = [];
  for (const entry of await readdir(publicDir, { recursive: true })) {
    if (!entry.includes('.') || !entry.endsWith(`.${extension}`)) {
      continue;
    }
    const fileName = entry.split(/\\|\//).pop() || '';
    if (fileName.startsWith(`${prefix}-`) && fileName.endsWith(`.${extension}`)) {
      candidates.push(join(publicDir, entry));
    }
  }

  if (!candidates.length) {
    return null;
  }

  return candidates[0] || null;
}

const assetHandler = {
  async fetch(request) {
    const url = new URL(request.url);
    const relativePath = url.pathname === '/' ? '/index.html' : url.pathname;
    const filePath = join(publicDir, relativePath.replace(/^\//, ''));
    if (!filePath.startsWith(publicDir)) {
      return new Response('Forbidden', { status: 403 });
    }
    try {
      const content = await readFile(filePath);
      const extension = filePath.split('.').pop()?.toLowerCase();
      const typeMap = {
        js: 'application/javascript; charset=utf-8',
        css: 'text/css; charset=utf-8',
        html: 'text/html; charset=utf-8',
        svg: 'image/svg+xml',
        ico: 'image/x-icon',
        txt: 'text/plain; charset=utf-8',
      };
      return new Response(content, {
        headers: { 'content-type': typeMap[extension] || 'application/octet-stream' },
      });
    } catch {
      const fallbackPath = await findMatchingPublicAsset(relativePath);
      if (!fallbackPath || !existsSync(fallbackPath)) {
        return new Response('Not found', { status: 404 });
      }
      const content = await readFile(fallbackPath);
      const extension = fallbackPath.split('.').pop()?.toLowerCase();
      const typeMap = {
        js: 'application/javascript; charset=utf-8',
        css: 'text/css; charset=utf-8',
        html: 'text/html; charset=utf-8',
        svg: 'image/svg+xml',
        ico: 'image/x-icon',
        txt: 'text/plain; charset=utf-8',
      };
      return new Response(content, {
        headers: { 'content-type': typeMap[extension] || 'application/octet-stream' },
      });
    }
  },
};

const httpServer = createServer(async (req, res) => {
  const request = new Request(`http://${req.headers.host || '127.0.0.1'}${req.url || '/'}`, {
    method: req.method,
    headers: req.headers,
    body:
      req.method !== 'GET' && req.method !== 'HEAD'
        ? await new Promise((resolve, reject) => {
            const chunks = [];
            req.on('data', (chunk) => chunks.push(chunk));
            req.on('end', () => resolve(Buffer.concat(chunks)));
            req.on('error', reject);
          })
        : undefined,
  });

  try {
    const response = await handler.fetch(request, { ASSETS: assetHandler }, {
      waitUntil: () => {},
      passThroughOnException: () => {},
    });
    res.statusCode = response.status;
    response.headers.forEach((value, key) => {
      if (key.toLowerCase() !== 'transfer-encoding') {
        res.setHeader(key, value);
      }
    });
    const buffer = Buffer.from(await response.arrayBuffer());
    res.end(buffer);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    res.statusCode = 500;
    res.setHeader('content-type', 'text/plain; charset=utf-8');
    res.end(message);
  }
});

httpServer.listen(port, '0.0.0.0', () => {
  console.log(`TanStack Start production server listening on http://0.0.0.0:${port}`);
});
