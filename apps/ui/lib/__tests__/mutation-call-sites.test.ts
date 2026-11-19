/**
 * Every mutating apiClient call is handled.
 *
 * post/put/patch/delete reject with ApiError on failure (see api.test.ts). A
 * call that isn't inside a `try` block or a `.catch()` chain would turn a
 * failed save into an unhandled rejection with no message to the user, and a
 * `.success` check on its result is dead code that hides that.
 *
 * Exempt: the thin wrappers in lib/api/*, which deliberately let the error
 * propagate to their callers (whose call sites are checked here too, if they
 * use apiClient directly).
 */
import fs from 'fs'
import path from 'path'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

const ROOT = path.resolve(__dirname, '../..')
const SCAN_DIRS = ['app', 'components', 'lib']
const MUTATIONS = new Set(['post', 'put', 'patch', 'delete'])
const EXEMPT_DIRS = [path.join('lib', 'api') + path.sep]

function sourceFiles(dir: string): string[] {
  const out: string[] = []
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      if (entry.name === 'node_modules' || entry.name === '__tests__') continue
      out.push(...sourceFiles(full))
    } else if (/\.(ts|tsx)$/.test(entry.name) && !entry.name.endsWith('.d.ts')) {
      out.push(full)
    }
  }
  return out
}

function isFunctionLike(node: ts.Node) {
  return ts.isFunctionDeclaration(node) || ts.isFunctionExpression(node)
    || ts.isArrowFunction(node) || ts.isMethodDeclaration(node)
}

/** True if the node is an element of the array passed to Promise.allSettled(). */
function isSettledElement(node: ts.Node): boolean {
  const array = node.parent
  if (!array || !ts.isArrayLiteralExpression(array)) return false
  const call = array.parent
  return !!call && ts.isCallExpression(call)
    && ts.isPropertyAccessExpression(call.expression)
    && ts.isIdentifier(call.expression.expression)
    && call.expression.expression.text === 'Promise'
    && call.expression.name.text === 'allSettled'
}

/** True if the call is inside a try block, its promise chain has .catch(),
 *  or it is passed straight to Promise.allSettled (which never rejects). */
/** True if `node` is what a `.map(cb)` callback returns, and that `.map(...)`
 *  is passed straight to Promise.allSettled(). */
function isSettledMapResult(node: ts.Node): boolean {
  const fn = node.parent
  if (!fn || !ts.isArrowFunction(fn) || fn.body !== node) return false
  const map = fn.parent
  if (!map || !ts.isCallExpression(map) || !ts.isPropertyAccessExpression(map.expression)
      || map.expression.name.text !== 'map') return false
  const settled = map.parent
  return !!settled && ts.isCallExpression(settled)
    && ts.isPropertyAccessExpression(settled.expression)
    && ts.isIdentifier(settled.expression.expression)
    && settled.expression.expression.text === 'Promise'
    && settled.expression.name.text === 'allSettled'
}

function isHandled(call: ts.CallExpression): boolean {
  if (isSettledElement(call)) return true
  // `.catch(...)` (possibly after `.then(...)`) chained on the call
  let outer: ts.Node = call
  while (ts.isPropertyAccessExpression(outer.parent) && ts.isCallExpression(outer.parent.parent)) {
    if (outer.parent.name.text === 'catch') return true
    outer = outer.parent.parent
  }
  if (isSettledMapResult(outer)) return true
  for (let node: ts.Node = call; node && !isFunctionLike(node); node = node.parent) {
    const parent = node.parent
    if (parent && ts.isTryStatement(parent) && parent.tryBlock === node) return true
  }
  return false
}

/** Name of the variable a call's awaited result is assigned to, if any. */
function resultName(call: ts.CallExpression): string | undefined {
  let node: ts.Node = call
  if (ts.isAwaitExpression(node.parent)) node = node.parent
  const parent = node.parent
  if (parent && ts.isVariableDeclaration(parent) && ts.isIdentifier(parent.name)) {
    return parent.name.text
  }
  return undefined
}

function enclosingFunction(node: ts.Node): ts.Node | undefined {
  for (let n: ts.Node | undefined = node.parent; n; n = n.parent) {
    if (isFunctionLike(n)) return n
  }
  return undefined
}

interface Finding { file: string; line: number; problem: string }

function scan(): Finding[] {
  const findings: Finding[] = []
  for (const dir of SCAN_DIRS) {
    for (const file of sourceFiles(path.join(ROOT, dir))) {
      const rel = path.relative(ROOT, file)
      if (EXEMPT_DIRS.some((d) => rel.startsWith(d))) continue
      const text = fs.readFileSync(file, 'utf8')
      const source = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true,
        file.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)

      const visit = (node: ts.Node) => {
        if (
          ts.isCallExpression(node)
          && ts.isPropertyAccessExpression(node.expression)
          && ts.isIdentifier(node.expression.expression)
          && node.expression.expression.text === 'apiClient'
          && MUTATIONS.has(node.expression.name.text)
        ) {
          const line = source.getLineAndCharacterOfPosition(node.getStart()).line + 1
          if (!isHandled(node)) {
            findings.push({ file: rel, line, problem: 'not in try/catch or .catch()' })
          }
          const name = resultName(node)
          const fn = enclosingFunction(node)
          if (name && fn && new RegExp(`\\b${name}\\??\\.success\\b`).test(fn.getText(source))) {
            findings.push({ file: rel, line, problem: `checks ${name}.success (dead: mutations throw)` })
          }
        }
        ts.forEachChild(node, visit)
      }
      visit(source)
    }
  }
  return findings
}

describe('mutating apiClient call sites', () => {
  it('every post/put/patch/delete is handled and none checks .success', () => {
    const findings = scan().map((f) => `${f.file}:${f.line} ${f.problem}`)
    expect(findings).toEqual([])
  })
})
