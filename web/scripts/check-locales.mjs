#!/usr/bin/env node
// CI check: pl/cs/en locales have identical keys (plural-aware), the same
// array lengths and the same {{interpolation}} variables. Exit 1 on mismatch.
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const dir = join(dirname(fileURLToPath(import.meta.url)), '../src/locales')
const LANGS = ['pl', 'cs', 'en']
const PLURAL = /_(zero|one|two|few|many|other)$/

function flatten(obj, prefix = '', out = {}) {
  for (const [k, v] of Object.entries(obj)) {
    const key = prefix ? `${prefix}.${k}` : k
    if (Array.isArray(v)) out[key] = { array: v.length, vars: varsOf(v.join(' ')) }
    else if (v && typeof v === 'object') flatten(v, key, out)
    else out[key] = { vars: varsOf(String(v)) }
  }
  return out
}
const varsOf = (s) => [...s.matchAll(/\{\{\s*(\w+)/g)].map((m) => m[1]).sort().join(',')

const errors = []
const bases = {} // lang -> Map(base -> {forms:Set, vars})
for (const lang of LANGS) {
  const flat = flatten(JSON.parse(readFileSync(join(dir, `${lang}.json`), 'utf8')))
  const m = new Map()
  const required = new Intl.PluralRules(lang).resolvedOptions().pluralCategories
  for (const [key, info] of Object.entries(flat)) {
    const pm = key.match(PLURAL)
    const base = pm ? key.slice(0, -pm[0].length) : key
    const entry = m.get(base) ?? { forms: new Set(), vars: new Set(), array: info.array, plural: !!pm }
    if (pm) entry.forms.add(pm[1])
    entry.vars.add(info.vars)
    m.set(base, entry)
  }
  for (const [base, e] of m) {
    if (e.plural) {
      const missing = required.filter((c) => !e.forms.has(c))
      if (missing.length) errors.push(`${lang}: ${base} missing plural forms: ${missing.join(', ')}`)
    }
    if (e.vars.size > 1) errors.push(`${lang}: ${base} plural forms use different variables`)
  }
  bases[lang] = m
}

const all = new Set(LANGS.flatMap((l) => [...bases[l].keys()]))
for (const base of [...all].sort()) {
  const present = LANGS.filter((l) => bases[l].has(base))
  if (present.length !== LANGS.length) {
    errors.push(`${base}: missing in ${LANGS.filter((l) => !present.includes(l)).join(', ')}`)
    continue
  }
  const [a, ...rest] = LANGS.map((l) => bases[l].get(base))
  for (const [i, b] of rest.entries()) {
    const l = LANGS[i + 1]
    if (a.array !== b.array) errors.push(`${base}: array length pl=${a.array} ${l}=${b.array}`)
    const va = [...a.vars].join('|'), vb = [...b.vars].join('|')
    if (va !== vb) errors.push(`${base}: variables differ pl={${va}} ${l}={${vb}}`)
  }
}

if (errors.length) {
  console.error(`✗ locale check failed (${errors.length}):\n  ` + errors.join('\n  '))
  process.exit(1)
}
console.log(`✓ locales ${LANGS.join('/')} match (${all.size} keys)`)
