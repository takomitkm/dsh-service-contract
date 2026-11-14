// Extract the DSH Host<->Client Typert Remote contract from generated artifacts.
// For every @deepseek-ai/*/lib/typert.remote-client.js we import the module and dump
// TYPERT_REMOTE.descriptors (method, params, jsonSchema, result, sourceLocation).
import fs from 'node:fs'
import path from 'node:path'
import { pathToFileURL } from 'node:url'

const base = process.argv[2]          // .../dsh/node_modules/@deepseek-ai
const outFile = process.argv[3]       // typert-contract.json

const dirs = fs.readdirSync(base, { withFileTypes: true })
  .filter(d => d.isDirectory())
  .map(d => d.name)

const packages = []
const errors = []
let endpointCount = 0

function tryGet(fn, fallback = null) { try { const v = fn(); return v ?? fallback } catch (e) { return { __error: String(e && e.message || e) } } }

for (const name of dirs.sort()) {
  const rel = path.join(name, 'lib', 'typert.remote-client.js')
  const abs = path.join(base, rel)
  if (!fs.existsSync(abs)) continue
  try {
    const mod = await import(pathToFileURL(abs).href)
    const T = mod.default
    if (!T || !Array.isArray(T.descriptors)) { errors.push({ package: name, error: 'no descriptors on default export' }); continue }
    const pkgName = tryGet(() => T.package, name)
    const endpoints = T.descriptors.map(d => {
      const params = (d.parameters || []).map(p => ({
        name: p.name,
        wire: p.wire ?? p.name,
        source: p.source ?? 'json',
        description: p.description ?? null,
        optional: p.optional ?? null,
        typeSymbol: p.codec?.typeSymbol ?? p.strictCodec?.typeSymbol ?? null,
        schema: p.codec?.jsonSchema ?? null,
        schemaError: (p.codec?.jsonSchema ?? null) ? null : (p.codec?.jsonSchemaError ?? p.strictCodec?.jsonSchemaError ?? null),
        strictSchema: p.strictCodec?.jsonSchema ?? null,
      }))
      return {
        id: d.id,
        namespace: d.namespace,
        method: d.method,
        service: d.service ?? null,
        description: d.description ?? null,
        invocation: tryGet(() => d.invocation, {}),
        parameters: params,
        // d.input is a factory function (no .jsonSchema). A single bundled 'request'
        // param carries the whole input-object schema; otherwise rely on per-param schemas.
        inputSchema: (params.length === 1 && params[0].name === 'request') ? params[0].schema : null,
        result: {
          mode: tryGet(() => d.result?.mode, null),
          typeSymbol: tryGet(() => d.result?.typeSymbol, null),
          description: tryGet(() => d.result?.description, null),
          schema: tryGet(() => d.result?.jsonSchema, null),
          schemaError: tryGet(() => d.result?.jsonSchemaError, null),
        },
        sourceLocation: d.sourceLocation ?? null,
      }
    })
    endpointCount += endpoints.length
    packages.push({ package: pkgName, serviceFamily: name, endpoints })
  } catch (e) {
    errors.push({ package: name, error: String(e && e.stack || e) })
  }
}

const result = {
  generatedAt: new Date().toISOString(),
  sourceBase: base,
  summary: { packages: packages.length, endpoints: endpointCount, errors: errors.length },
  packages,
  errors,
}
fs.writeFileSync(outFile, JSON.stringify(result, null, 2), 'utf8')
console.log(`packages=${packages.length} endpoints=${endpointCount} errors=${errors.length} -> ${outFile}`)
if (errors.length) console.log('ERRORS:', JSON.stringify(errors, null, 2))
