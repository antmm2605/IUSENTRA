import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../src", import.meta.url));
const forbidden = [
  /\bmock[A-Z_]/,
  /from ["']@\/lib\/api\/mock["']/,
  /Fascicolo demo/i,
  /Risposta demo/i,
  /Cliente demo/i,
  /Controparte demo/i,
  /Atto generato da workspace React/i,
  /€\s*18\.420/,
  /€\s*42\.800/,
];

function walk(dir) {
  const out = [];
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    const stat = statSync(path);
    if (stat.isDirectory()) out.push(...walk(path));
    else if (/\.(ts|tsx|js|jsx)$/.test(path)) out.push(path);
  }
  return out;
}

const violations = [];
for (const file of walk(root)) {
  const text = readFileSync(file, "utf8");
  for (const pattern of forbidden) {
    if (pattern.test(text)) {
      violations.push(`${relative(process.cwd(), file)} contiene ${pattern}`);
    }
  }
}

if (violations.length) {
  console.error("La shell React non deve contenere dati demo o mock operativi.");
  for (const violation of violations) console.error(`- ${violation}`);
  process.exit(1);
}

console.log("OK: nessun dato demo operativo nella shell React.");
