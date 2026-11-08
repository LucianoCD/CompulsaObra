import fs from 'node:fs';

const DESTRUCTIVE_PATTERNS = [
  { regex: /\balembic\s+downgrade\s+base\b/i, label: 'alembic downgrade base' },
  { regex: /\bprisma\s+migrate\s+reset\b/i, label: 'prisma migrate reset' },
  { regex: /\bDROP\s+(DATABASE|SCHEMA)\b/i, label: 'DROP DATABASE / DROP SCHEMA' },
  { regex: /\bgit\s+push\b.*(\s--force\b|\s-f\b)/i, label: 'git push --force' },
  { regex: /\bgit\s+reset\s+--hard\b/i, label: 'git reset --hard' },
  { regex: /\bgit\s+clean\s+-[a-z]*f/i, label: 'git clean -f' }
];

function evaluatePayload(raw) {
  if (!raw || !raw.trim()) {
    return { decision: 'ask' };
  }
  let payload;
  try {
    payload = JSON.parse(raw);
  } catch {
    return { decision: 'ask' };
  }

  const args = payload?.toolCall?.args ?? {};
  const candidateStrings = [
    typeof args.CommandLine === 'string' ? args.CommandLine : '',
    typeof args?.Arguments?.query === 'string' ? args.Arguments.query : ''
  ].filter(Boolean);

  for (const text of candidateStrings) {
    for (const rule of DESTRUCTIVE_PATTERNS) {
      if (rule.regex.test(text)) {
        return {
          decision: 'deny',
          reason: `[Safety Gate PreToolUse - CompulsaObra] Operación destructiva bloqueada (${rule.label}). Las migraciones Alembic, los catálogos SHA-256 y el historial Git están protegidos.`
        };
      }
    }
  }

  return { decision: 'ask' };
}

try {
  const input = fs.readFileSync(0, 'utf8');
  const result = evaluatePayload(input);
  process.stdout.write(JSON.stringify(result) + '\n');
} catch {
  process.stdout.write(JSON.stringify({ decision: 'ask' }) + '\n');
}
