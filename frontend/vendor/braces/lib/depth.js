'use strict';

// A fixed ceiling, rather than a caller-controlled option, bounds all recursive walkers.
const MAX_DEPTH = 100;

const assertDepth = depth => {
  if (depth > MAX_DEPTH) {
    throw new SyntaxError(`Brace pattern exceeds maximum nesting depth (${MAX_DEPTH})`);
  }
};

// Public compile/expand/stringify also accept caller-supplied ASTs, bypassing parse().
// Validate iteratively: a recursive validator would itself be vulnerable.
const assertSafeAst = ast => {
  const pending = [{ node: ast, depth: 0 }];
  while (pending.length) {
    const { node, depth } = pending.pop();
    if (!node || !Array.isArray(node.nodes)) continue;
    assertDepth(depth);
    for (const child of node.nodes) pending.push({ node: child, depth: depth + 1 });
  }
};

module.exports = { MAX_DEPTH, assertDepth, assertSafeAst };
