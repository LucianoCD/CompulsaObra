import { execSync } from 'node:child_process';
import fs from 'node:fs';
import net from 'node:net';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, '..', '..');
const mode = process.argv.includes('--mode=session-start') ? 'session-start' : 'pre-invocation';
const PG_PORT = 5432;

function getGitInfo(cwd) {
  try {
    const branch = execSync('git branch --show-current', {
      cwd,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
      timeout: 1500
    }).trim();
    const statusRaw = execSync('git status --porcelain', {
      cwd,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
      timeout: 1500
    });
    const dirtyFiles = statusRaw
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => line.slice(3).trim());
    return { branch: branch || 'main', dirtyFiles };
  } catch {
    return { branch: 'n/a', dirtyFiles: [] };
  }
}

function checkPort(port, host = '127.0.0.1', timeoutMs = 250) {
  return new Promise((resolve) => {
    const socket = new net.Socket();
    let settled = false;
    const done = (online) => {
      if (!settled) {
        settled = true;
        socket.destroy();
        resolve(online);
      }
    };
    socket.setTimeout(timeoutMs);
    socket.once('connect', () => done(true));
    socket.once('timeout', () => done(false));
    socket.once('error', () => done(false));
    socket.connect(port, host);
  });
}

async function main() {
  try {
    try {
      fs.readFileSync(0, 'utf8');
    } catch {
      // Ignore empty stdin
    }

    const { branch, dirtyFiles } = getGitInfo(repoRoot);

    if (mode === 'session-start') {
      const pgOnline = await checkPort(PG_PORT);
      const pgBadge = pgOnline
        ? 'ONLINE (`:5432` + SQLite Híbrido)'
        : 'OFFLINE (`:5432` apagado — Modo SQLite Local Activo)';
      const dirtyBadge =
        dirtyFiles.length === 0
          ? 'Working tree limpio'
          : `${dirtyFiles.length} archivo(s) con cambios locales`;

      const markdown = `> **CompulsaObra Pulse (0-Token UI):** Rama \`${branch}\` | ${dirtyBadge} | Persistencia: **${pgBadge}**`;

      process.stdout.write(
        JSON.stringify({
          injectSteps: [
            {
              systemMessage: {
                systemMessage: '',
                metadata: {
                  user_markdown: markdown
                }
              }
            }
          ]
        }) + '\n'
      );
      return;
    }

    // mode === 'pre-invocation'
    const criticalPatterns = [
      /unit_normalizer/i,
      /matching_engine/i,
      /comparison_optimizer/i,
      /catalog_importer/i,
      /pdf_generator/i,
      /multimodal_extractor/i,
      /alembic[\\/]/i,
      /models[\\/]/i,
      /schemas[\\/]/i,
      /types[\\/]api\.ts/i
    ];

    const touchedCritical = dirtyFiles.filter((file) =>
      criticalPatterns.some((rx) => rx.test(file))
    );

    if (touchedCritical.length > 0) {
      const sample = touchedCritical.slice(0, 4).join(', ');
      const reminder = `[Pulso Efímero CompulsaObra] Archivos críticos modificados (${sample}). Recuerda: (1) preservar el Filtro Dimensional Duro SQL (Cero Sustitución Ciega) y deduplicación SHA-256, (2) aplicar ponytail-review sincronizando backend/app/schemas con frontend/src/types/api.ts, y (3) verificar con pytest -v y npx tsc --noEmit antes de cerrar.`;
      process.stdout.write(
        JSON.stringify({
          injectSteps: [
            {
              ephemeralMessage: reminder
            }
          ]
        }) + '\n'
      );
      return;
    }

    process.stdout.write(JSON.stringify({ injectSteps: [] }) + '\n');
  } catch {
    process.stdout.write(JSON.stringify({ injectSteps: [] }) + '\n');
  }
}

main();
