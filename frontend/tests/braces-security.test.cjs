const assert = require("node:assert/strict");
const test = require("node:test");
const braces = require("braces");
const vendorPkg = require("../vendor/braces/package.json");

test("resolves local security fork of braces from vendor directory", () => {
  const resolvedPath = require.resolve("braces");
  assert.match(resolvedPath, /vendor\/braces\/index\.js$/);
  assert.equal(vendorPkg.name, "@career-agent/braces");
  assert.equal(vendorPkg.version, "3.0.3-career.1");
});

test("handles regular brace patterns correctly", () => {
  assert.deepEqual(braces("{a,b,c}"), ["(a|b|c)"]);
  assert.deepEqual(braces("{a,b,c}", { expand: true }), ["a", "b", "c"]);
  assert.deepEqual(braces("file-{1..3}.txt", { expand: true }), [
    "file-1.txt",
    "file-2.txt",
    "file-3.txt",
  ]);
});

test("handles moderate safe nesting within allowed limits (depth <= 100)", () => {
  // 10 levels of nesting is legitimate and should parse fine
  const safeNested = "{a,".repeat(10) + "x" + "}".repeat(10);
  assert.doesNotThrow(() => {
    braces(safeNested);
  });
});

test("safely rejects deeply nested braces (>100 depth) without call stack overflow or ReDoS", () => {
  // Vulnerability trigger pattern (GHSA-vfj7-8cjw-p6xm): deeply nested braces
  const deepBraces = "{a,".repeat(105) + "vuln" + "}".repeat(105);

  assert.throws(
    () => {
      braces(deepBraces);
    },
    {
      name: "SyntaxError",
      message: /Brace pattern exceeds maximum nesting depth \(100\)/,
    }
  );
});

test("safely rejects deeply nested unclosed opening braces", () => {
  const unclosedDeep = "{".repeat(120);

  assert.throws(
    () => {
      braces(unclosedDeep);
    },
    {
      name: "SyntaxError",
      message: /Brace pattern exceeds maximum nesting depth \(100\)/,
    }
  );
});

test("safely rejects deeply nested parentheses", () => {
  const deepParens = "(".repeat(105) + "val" + ")".repeat(105);

  assert.throws(
    () => {
      braces(deepParens);
    },
    {
      name: "SyntaxError",
      message: /Brace pattern exceeds maximum nesting depth \(100\)/,
    }
  );
});

test("safely validates caller-supplied AST with assertSafeAst iteratively", () => {
  // Construct a nested AST deeper than MAX_DEPTH to verify compile/expand/stringify guards
  let deepAst = { type: "root", nodes: [] };
  let current = deepAst;
  for (let i = 0; i < 110; i++) {
    const child = { type: "brace", nodes: [] };
    current.nodes.push(child);
    current = child;
  }

  assert.throws(
    () => {
      braces.compile(deepAst);
    },
    {
      name: "SyntaxError",
      message: /Brace pattern exceeds maximum nesting depth \(100\)/,
    }
  );

  assert.throws(
    () => {
      braces.expand(deepAst);
    },
    {
      name: "SyntaxError",
      message: /Brace pattern exceeds maximum nesting depth \(100\)/,
    }
  );

  assert.throws(
    () => {
      braces.stringify(deepAst);
    },
    {
      name: "SyntaxError",
      message: /Brace pattern exceeds maximum nesting depth \(100\)/,
    }
  );
});
