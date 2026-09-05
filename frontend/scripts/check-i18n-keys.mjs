import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const srcRoot = path.join(__dirname, '..', 'src');
const localesDir = path.join(srcRoot, 'i18n', 'locales');

function walk(dir, acc = []) {
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, ent.name);
    if (ent.isDirectory()) walk(p, acc);
    else if (/\.(tsx?|jsx?)$/.test(ent.name)) acc.push(p);
  }
  return acc;
}

function extractObject(source, exportName) {
  const marker = `export const ${exportName}`;
  const start = source.indexOf(marker);
  if (start < 0) throw new Error(`Missing export ${exportName}`);
  const braceStart = source.indexOf('{', start);
  let depth = 0;
  for (let i = braceStart; i < source.length; i++) {
    if (source[i] === '{') depth++;
    else if (source[i] === '}') {
      depth--;
      if (depth === 0) {
        return Function(`"use strict"; return (${source.slice(braceStart, i + 1)})`)();
      }
    }
  }
  throw new Error(`Unbalanced braces in ${exportName}`);
}

function mergeTrees(...trees) {
  const result = {};
  for (const tree of trees) {
    for (const [key, value] of Object.entries(tree)) {
      if (value && typeof value === 'object' && !Array.isArray(value)) {
        result[key] = mergeTrees(result[key] || {}, value);
      } else {
        result[key] = value;
      }
    }
  }
  return result;
}

function flattenKeys(tree, prefix = '') {
  const keys = [];
  for (const [key, value] of Object.entries(tree)) {
    const full = prefix ? `${prefix}.${key}` : key;
    if (value && typeof value === 'object' && !Array.isArray(value)) keys.push(...flattenKeys(value, full));
    else keys.push(full);
  }
  return keys;
}

function resolveKey(tree, key) {
  const value = key.split('.').reduce((node, part) => {
    if (node && typeof node === 'object' && part in node) return node[part];
    return undefined;
  }, tree);
  return typeof value === 'string' ? value : undefined;
}

const sharedEn = extractObject(fs.readFileSync(path.join(localesDir, 'shared.ts'), 'utf8'), 'sharedEn');
const pagesEn = extractObject(fs.readFileSync(path.join(localesDir, 'pages.ts'), 'utf8'), 'pagesEn');
const baseEn = extractObject(fs.readFileSync(path.join(localesDir, 'en.base.ts'), 'utf8'), 'en');
const placeholdersEn = extractObject(fs.readFileSync(path.join(localesDir, 'placeholders.ts'), 'utf8'), 'placeholdersEn');
const guidesEn = extractObject(fs.readFileSync(path.join(localesDir, 'guides.ts'), 'utf8'), 'guidesEn');
const sharedZh = extractObject(fs.readFileSync(path.join(localesDir, 'shared.ts'), 'utf8'), 'sharedZh');
const pagesZh = extractObject(fs.readFileSync(path.join(localesDir, 'pages.ts'), 'utf8'), 'pagesZh');
const baseZh = extractObject(fs.readFileSync(path.join(localesDir, 'zh.base.ts'), 'utf8'), 'zh');
const placeholdersZh = extractObject(fs.readFileSync(path.join(localesDir, 'placeholders.ts'), 'utf8'), 'placeholdersZh');
const guidesZh = extractObject(fs.readFileSync(path.join(localesDir, 'guides.ts'), 'utf8'), 'guidesZh');

const en = mergeTrees(baseEn, sharedEn, pagesEn, placeholdersEn, guidesEn);
const zh = mergeTrees(baseZh, sharedZh, pagesZh, placeholdersZh, guidesZh);

const staticKeyRe = /\bt\(\s*['"]([^'"]+)['"]/g;
const indirectKeyRe = /(?:labelKey|titleKey|descKey|key|messageKey|headingKey|navKey):\s*['"]([^'"]+)['"]/g;
const keys = new Map();

for (const file of walk(srcRoot)) {
  const rel = path.relative(srcRoot, file);
  if (rel.startsWith('i18n' + path.sep)) continue;
  const text = fs.readFileSync(file, 'utf8');
  for (const re of [staticKeyRe, indirectKeyRe]) {
    let m;
    while ((m = re.exec(text))) {
      const key = m[1];
      if (!keys.has(key)) keys.set(key, []);
      keys.get(key).push(rel);
    }
  }
}

const missingEn = [];
const missingZh = [];
for (const [key, files] of keys.entries()) {
  if (!resolveKey(en, key)) missingEn.push({ key, files: [...new Set(files)] });
  if (!resolveKey(zh, key)) missingZh.push({ key, files: [...new Set(files)] });
}

const enOnly = flattenKeys(en).filter((k) => !resolveKey(zh, k));
const zhOnly = flattenKeys(zh).filter((k) => !resolveKey(en, k));

console.log('Keys referenced in UI:', keys.size);
console.log('\nMissing in EN:', missingEn.length);
for (const item of missingEn.sort((a, b) => a.key.localeCompare(b.key))) {
  console.log('  -', item.key);
}
console.log('\nMissing in ZH:', missingZh.length);
for (const item of missingZh.sort((a, b) => a.key.localeCompare(b.key))) {
  console.log('  -', item.key);
}
console.log('\nDefined in EN but not ZH:', enOnly.length);
for (const key of enOnly.sort().slice(0, 20)) console.log('  -', key);
if (enOnly.length > 20) console.log(`  ... and ${enOnly.length - 20} more`);
console.log('\nDefined in ZH but not EN:', zhOnly.length);
for (const key of zhOnly.sort().slice(0, 20)) console.log('  -', key);
if (zhOnly.length > 20) console.log(`  ... and ${zhOnly.length - 20} more`);
