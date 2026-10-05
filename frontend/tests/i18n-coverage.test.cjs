const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const ts = require("typescript");

const appRoot = path.join(__dirname, "../src/app");
const componentRoot = path.join(__dirname, "../src/components");
const i18nPath = path.join(__dirname, "../src/lib/i18n.tsx");
const turkishText = /[çğıöşüÇĞİÖŞÜ]/;

function collectPageFiles(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) return collectPageFiles(fullPath);
    return entry.name === "page.tsx" ? [fullPath] : [];
  });
}

function collectTranslationKeys(sourceFile) {
  const keys = new Set();
  function visit(node) {
    if (ts.isPropertyAssignment(node) && ts.isStringLiteral(node.name)) keys.add(node.name.text);
    ts.forEachChild(node, visit);
  }
  visit(sourceFile);
  return keys;
}

const pages = collectPageFiles(appRoot);
const sharedComponents = fs.readdirSync(componentRoot)
  .filter((name) => name.endsWith(".tsx"))
  .map((name) => path.join(componentRoot, name));
const localizedFiles = [...pages, ...sharedComponents];
const i18nSource = ts.createSourceFile(i18nPath, fs.readFileSync(i18nPath, "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
const translationKeys = collectTranslationKeys(i18nSource);
// The bulk of the dictionary lives next to i18n.tsx.
const dictionaryPath = path.join(__dirname, "../src/lib/i18n-translations.ts");
const dictionarySource = ts.createSourceFile(dictionaryPath, fs.readFileSync(dictionaryPath, "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
for (const key of collectTranslationKeys(dictionarySource)) translationKeys.add(key);

test("every application route participates in localization", () => {
  assert.ok(pages.length > 0, "No app routes were found");
  for (const pagePath of pages) {
    const source = fs.readFileSync(pagePath, "utf8");
    assert.match(source, /useLanguage/, `${path.relative(appRoot, pagePath)} is missing the language hook`);
    const page = ts.createSourceFile(pagePath, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
    assert.equal(page.parseDiagnostics.length, 0, `${path.relative(appRoot, pagePath)} has invalid TSX`);
  }
});

test("visible JSX copy is localized and every static translation key exists", () => {
  const untranslated = [];
  const missingKeys = [];

  for (const pagePath of localizedFiles) {
    const page = ts.createSourceFile(pagePath, fs.readFileSync(pagePath, "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
    function visit(node) {
      if (ts.isJsxText(node) && turkishText.test(node.text.trim())) {
        untranslated.push(`${path.relative(appRoot, pagePath)}: ${node.text.trim()}`);
      }
      if (ts.isJsxAttribute(node) && node.initializer && ts.isStringLiteral(node.initializer) && turkishText.test(node.initializer.text)) {
        untranslated.push(`${path.relative(appRoot, pagePath)}: ${node.initializer.text}`);
      }
      if (ts.isCallExpression(node) && node.expression.getText(page) === "t" && node.arguments[0] && ts.isStringLiteral(node.arguments[0]) && !translationKeys.has(node.arguments[0].text)) {
        missingKeys.push(`${path.relative(appRoot, pagePath)}: ${node.arguments[0].text}`);
      }
      ts.forEachChild(node, visit);
    }
    visit(page);
  }

  assert.deepEqual(untranslated, [], `Untranslated visible copy:\n${untranslated.join("\n")}`);
  assert.deepEqual(missingKeys, [], `Missing English dictionary entries:\n${missingKeys.join("\n")}`);
});
