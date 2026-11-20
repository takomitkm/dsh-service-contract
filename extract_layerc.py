"""Extract Layer C (in-process Cordis ctx.* service surface) from the official
deepseek-ai/deepseek-harness repo at exact tag dsh-v0.2.2-rc.1.

Source of truth: TypeScript declaration merging
    declare module '@deepseek-ai/cordis' { interface Context { ... } }
Cross-check: compiled .js in the installed app.asar extraction.

All file I/O uses encoding='utf-8' (host ACP=936).
"""
import os, re, json, collections, sys

def log(*a):
    print(*a, flush=True)

# Version selection: default rc.1 (original behavior); pass tag as argv[1] for others.
TAG = sys.argv[1] if len(sys.argv) > 1 else 'dsh-v0.2.2-rc.1'
_VER = TAG.removeprefix('dsh-v')
_SHA = {
    'dsh-v0.2.2-rc.1': '66491b05e3f05ad35bcdd4f6cd7ed26041d9e3db',
    'dsh-v0.2.2-rc.3': '38a6a5c965aa99ab525161efb7cc5cf1fe62fced',
    'dsh-v0.2.2-rc.5': '9c2670d3bce5275e0d1610272958121af87787bb',
}
SHA = _SHA[TAG]
ROOT = r'S:\apps\llm\agentwork\.tmp\dsh-src' if TAG == 'dsh-v0.2.2-rc.1' else rf'S:\apps\llm\agentwork\.tmp\dsh-src-{_VER}'
ASAR = (r'S:\apps\llm\agentwork\.tmp\dsh-asar-full' if TAG == 'dsh-v0.2.2-rc.1'
        else rf'S:\apps\llm\agentwork\.tmp\dsh-asar-{_VER}') + r'\dsh\node_modules\@deepseek-ai'
OUT = rf'S:\apps\llm\agentwork\.tmp\layerc-contract{_VER and "-" + _VER or ""}.json'

# ---------------------------------------------------------------- scanning utils

def match_brace(s, open_idx):
    """Index of the '}' matching the '{' at open_idx; skips strings/comments."""
    n = len(s); i = open_idx; depth = 0
    while i < n:
        c = s[i]
        if c in "'\"`":
            q = c; i += 1
            while i < n:
                if s[i] == '\\': i += 2; continue
                if s[i] == q: break
                i += 1
            i += 1; continue
        if c == '/' and i + 1 < n and s[i+1] == '/':
            j = s.find('\n', i); i = n if j < 0 else j + 1; continue
        if c == '/' and i + 1 < n and s[i+1] == '*':
            j = s.find('*/', i + 2); i = n if j < 0 else j + 2; continue
        if c == '{': depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0: return i
        i += 1
    return None

def bracket_delta(s):
    """Net depth of ()[]{} ignoring strings/comments."""
    n = len(s); i = 0; d = 0
    while i < n:
        c = s[i]
        if c in "'\"`":
            q = c; i += 1
            while i < n:
                if s[i] == '\\': i += 2; continue
                if s[i] == q: break
                i += 1
            i += 1; continue
        if c == '/' and i + 1 < n and s[i+1] == '/':
            j = s.find('\n', i); i = n if j < 0 else j + 1; continue
        if c == '/' and i + 1 < n and s[i+1] == '*':
            j = s.find('*/', i + 2); i = n if j < 0 else j + 2; continue
        if c in '([{': d += 1
        elif c in ')]}': d -= 1
        i += 1
    return d

def rel(p, base=ROOT):
    return os.path.relpath(p, base).replace('\\', '/')

def is_test(relpath):
    r = '/' + relpath
    return ('/tests/' in r or '/__tests__/' in r or '/fixtures/' in r
            or r.endswith(('.spec.ts', '.test.ts', '.spec.tsx', '.test.tsx'))
            or '/test/' in r)

def scope_of(relpath):
    if relpath.startswith('vendor/'): return 'runtime'
    if is_test(relpath): return 'test'
    return 'production'

# ---------------------------------------------------------------- package map
pkg_by_dir = {}
for top in ('packages', 'vendor'):
    base = os.path.join(ROOT, top)
    if not os.path.isdir(base): continue
    for dp, dn, fn in os.walk(base):
        if 'package.json' in fn:
            try:
                pj = json.load(open(os.path.join(dp, 'package.json'), encoding='utf-8'))
                pkg_by_dir[rel(dp)] = pj.get('name') or ''
            except Exception:
                pkg_by_dir[rel(dp)] = ''

def package_of(relpath):
    parts = relpath.split('/')
    for k in range(len(parts) - 1, 0, -1):
        d = '/'.join(parts[:k])
        if d in pkg_by_dir: return pkg_by_dir[d]
    return ''

# ---------------------------------------------------------------- collect files
ts_files = []
for top in ('packages', 'vendor'):
    base = os.path.join(ROOT, top)
    if not os.path.isdir(base): continue
    for dp, dn, fn in os.walk(base):
        for f in fn:
            if f.endswith(('.ts', '.tsx')) and not f.endswith('.d.ts'):
                ts_files.append(os.path.join(dp, f))
ts_files.sort()
log('ts files:', len(ts_files))

# ---------------------------------------------------------------- member parsing
doc_re = re.compile(r'^\s*(?:/\*\*|\*|//|/\*)')
prop_re = re.compile(r'^\s*(?:readonly\s+)?([A-Za-z_$][\w$]*)\s*(\?)?\s*:\s*([\s\S]+?)\s*;?\s*$')
meth_re = re.compile(r'^\s*(?:readonly\s+)?([A-Za-z_$][\w$]*)\s*(?:<[^>]*>)?\s*\(([\s\S]*)\)\s*:\s*([\s\S]+?)\s*;?\s*$')

def clean_doc(lines):
    out = []
    for l in lines:
        t = l.strip()
        if t.startswith('//'): t = t[2:]
        elif t.startswith('/**'): t = t[3:]
        elif t.startswith('/*'): t = t[2:]
        elif t.startswith('*/'): t = ''
        elif t.startswith('*'): t = t[1:]
        t = t.strip()
        if t and not t.startswith('@'): out.append(t)
    return ' '.join(out).strip()

def parse_members(body):
    """Split an interface body into top-level members with their JSDoc.

    This repo writes interface members newline-separated, usually WITHOUT a
    trailing ';'. A member ends when its ()[]{} depth returns to zero and the
    accumulated text does not end on a type-continuation operator.
    """
    members = []
    prop_start = re.compile(r'^\s*(?:readonly\s+)?([A-Za-z_$][\w$]*)\s*(\?)?\s*:\s*(.*)$')
    meth_start = re.compile(r'^\s*(?:readonly\s+)?([A-Za-z_$][\w$]*)\s*(?:<[^>]*>)?\s*\((.*)$')
    buf = ''; docs = []

    def emit(txt, doc):
        txt = txt.strip().rstrip(';').strip()
        if not txt: return
        m = prop_start.match(txt)
        if m:
            members.append((m.group(1), 'property', (m.group(3) or '').strip(),
                            bool(m.group(2)), clean_doc(doc), txt))
            return
        m2 = meth_re.match(txt)
        if m2:
            members.append((m2.group(1), 'method',
                            '(' + m2.group(2) + ') : ' + m2.group(3).strip(),
                            False, clean_doc(doc), txt))

    for line in body.split('\n'):
        st = line.strip()
        if not buf:
            if not st: continue
            if doc_re.match(line):
                docs.append(line); continue
            if st.startswith(('}', 'export', 'declare', 'namespace', '[')):
                docs = []; continue
            if not (prop_start.match(line) or meth_start.match(line)):
                docs = []; continue
            buf = st
        else:
            buf += ' ' + st
        if bracket_delta(buf) <= 0 and not buf.rstrip().endswith(('|', '&', '=>', ':', ',', '(', '.', '=', '<')):
            emit(buf, docs)
            buf = ''; docs = []
    if buf: emit(buf, docs)
    return members

def find_block(s, start_pat, inner_pat=None, from_idx=0):
    """Yield (outer_start, open_idx, close_idx) for `start_pat` then its '{' body."""
    for m in re.finditer(start_pat, s[from_idx:]):
        o = from_idx + m.start()
        brace = s.find('{', from_idx + m.end())
        if brace < 0: continue
        # ensure this brace belongs to the declaration (no ';' / '}' before it)
        if re.search(r'[;}]', s[from_idx + m.end():brace]): continue
        close = match_brace(s, brace)
        if close is None: continue
        yield o, brace, close

# ---------------------------------------------------------------- main extraction
declarations = []   # one per Context member occurrence
provide_calls = []  # one per ctx(.reflect)?.provide call
inject_arrays = []  # one per inject array
ctx_gets = []       # ctx.get('name')
service_classes = []
type_defs = collections.defaultdict(list)

pat_ctxprovide = re.compile(r"\bctx(?:\.reflect)?\.provide\s*\(\s*(['\"])([^'\"]+)\1")
pat_ctxprovide_var = re.compile(r"\bctx(?:\.reflect)?\.provide\s*\(\s*([A-Za-z_$][\w$]*)\s*,")
pat_inject = re.compile(r"(?:static\s+)?(?:export\s+)?(?:const|let|var)?\s*inject\s*=\s*\[([\s\S]*?)\]")
pat_ctxget = re.compile(r"\bctx\.get\s*\(\s*(['\"])([^'\"]+)\1")
pat_typedef = re.compile(r"^\s*(?:export\s+)?(?:declare\s+)?(interface|class|type|abstract\s+class)\s+([A-Za-z_$][\w$]*)", re.M)
pat_cls = re.compile(r"(?:export\s+)?(?:abstract\s+)?class\s+([A-Za-z_$][\w$]*)\s+extends\s+([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)")

str_re = re.compile(r"(['\"])([^'\"]+)\1")

for p in ts_files:
    r = rel(p)
    scope = scope_of(r)
    pkg = package_of(r)
    try: s = open(p, encoding='utf-8', errors='replace').read()
    except OSError: continue
    lines = s.split('\n')
    def lineno(idx): return s.count('\n', 0, idx) + 1

    # --- declaration merging blocks
    for m in re.finditer(r"declare\s+module\s+['\"]@deepseek-ai/cordis['\"]", s):
        brace = s.find('{', m.end())
        if brace < 0: continue
        if re.search(r'[;}]', s[m.end():brace]): continue
        close = match_brace(s, brace)
        if close is None: continue
        modbody = s[brace+1:close]
        for im in re.finditer(r"\binterface\s+Context\b", modbody):
            ib = modbody.find('{', im.end())
            if ib < 0: continue
            if re.search(r'[;}]', modbody[im.end():ib]): continue
            ic = match_brace(modbody, ib)
            if ic is None: continue
            body = modbody[ib+1:ic]
            abs_open = brace + 1 + ib
            for name, kind, typ, optional, doc, raw in parse_members(body):
                # locate this member's line inside the file
                pos = s.find(raw[:40], abs_open) if raw[:40] else -1
                declarations.append(dict(
                    key=name, kind=kind, type=typ, optional=optional, doc=doc,
                    file=r, line=(lineno(pos) if pos >= 0 else lineno(abs_open)),
                    package=pkg, scope=scope,
                    raw=re.sub(r'\s+', ' ', raw).strip()[:400],
                ))

    # --- provide / get / inject
    for m in pat_ctxprovide.finditer(s):
        provide_calls.append(dict(key=m.group(2), file=r, line=lineno(m.start()),
                                  package=pkg, scope=scope, reflect=('.reflect.provide' in m.group(0))))
    for m in pat_ctxprovide_var.finditer(s):
        provide_calls.append(dict(key=None, variable=m.group(1), file=r, line=lineno(m.start()),
                                  package=pkg, scope=scope, reflect=('.reflect.provide' in m.group(0))))
    for m in pat_ctxget.finditer(s):
        ctx_gets.append(dict(key=m.group(2), file=r, line=lineno(m.start()), package=pkg, scope=scope))
    for m in pat_inject.finditer(s):
        deps = [x.group(2) for x in str_re.finditer(m.group(1))]
        inject_arrays.append(dict(file=r, line=lineno(m.start()), package=pkg,
                                  scope=scope, deps=deps, raw=re.sub(r'\s+', ' ', m.group(0))[:300]))

    # --- service classes and type definitions (for method signatures)
    for m in pat_typedef.finditer(s):
        kind = m.group(1).replace('abstract class', 'class')
        name = m.group(2)
        b = s.find('{', m.end())
        if b < 0 or (b - m.end()) > 200: continue
        c = match_brace(s, b) if kind in ('interface', 'class') else None
        body = s[b+1:c] if c is not None else ''
        type_defs[name].append(dict(name=name, kind=kind, file=r, line=lineno(m.start()),
                                    package=pkg, scope=scope, body=body))
    for m in pat_cls.finditer(s):
        b = s.find('{', m.end())
        if b < 0: continue
        c = match_brace(s, b)
        if c is None: continue
        body = s[b+1:c]
        inj = None
        mi = re.search(r"static\s+inject\s*=\s*\[([\s\S]*?)\]", body)
        if mi: inj = [x.group(2) for x in str_re.finditer(mi.group(1))]
        service_classes.append(dict(name=m.group(1), extends=m.group(2), file=r,
                                    line=lineno(m.start()), package=pkg, scope=scope,
                                    inject=inj, body=body))

log('declarations:', len(declarations), 'unique keys:', len({d['key'] for d in declarations}))
log('provide calls:', len(provide_calls), 'ctx.get:', len(ctx_gets),
      'inject arrays:', len(inject_arrays), 'classes:', len(service_classes),
      'type defs:', sum(len(v) for v in type_defs.values()))

# ---------------------------------------------------------------- TypertRemoteService super(ctx,'key')
super_regs = []
pat_super = re.compile(r"super\s*\(\s*ctx\s*,\s*(['\"])([^'\"]+)\1")
for p in ts_files:
    r = rel(p); scope = scope_of(r); pkg = package_of(r)
    s = open(p, encoding='utf-8', errors='replace').read()
    for m in pat_super.finditer(s):
        super_regs.append(dict(key=m.group(2), file=r, line=s.count('\n', 0, m.start()) + 1,
                               package=pkg, scope=scope))
log('super(ctx,key) registrations:', len(super_regs))

# ---------------------------------------------------------------- method signatures from type bodies
def paren_balance(s):
    n = len(s); i = 0; d = 0
    while i < n:
        c = s[i]
        if c in "'\"`":
            q = c; i += 1
            while i < n:
                if s[i] == '\\': i += 2; continue
                if s[i] == q: break
                i += 1
            i += 1; continue
        if c == '(' : d += 1
        elif c == ')' : d -= 1
        i += 1
    return d

method_start = re.compile(
    r"^\s*(?:(?:public|private|protected|static|async|override|abstract|readonly|declare)\s+)*"
    r"([A-Za-z_$][\w$]*)\s*(?:<[^>]*>)?\s*\(")
skip_words = {'if', 'for', 'while', 'switch', 'catch', 'return', 'constructor',
              'function', 'typeof', 'new', 'await', 'throw', 'super', 'else', 'do'}

def parse_signatures(body):
    """Textual method signatures from an interface/class body (decorators + JSDoc kept)."""
    out = []
    lines = body.split('\n')
    i = 0; docs = []; decorators = []
    while i < len(lines):
        st = lines[i].strip()
        if not st:
            docs = []; decorators = []; i += 1; continue
        if st.startswith(('//', '/*', '*')) or st.startswith('*/'):
            docs.append(st); i += 1; continue
        if st.startswith('@'):
            decorators.append(st); i += 1; continue
        m = method_start.match(lines[i])
        if m and m.group(1) not in skip_words:
            name = m.group(1)
            buf = st
            d = paren_balance(buf)
            stop_line = i
            while d > 0 and stop_line + 1 < len(lines) and stop_line - i < 4000:
                stop_line += 1
                buf += ' ' + lines[stop_line].strip()
                d = paren_balance(buf)
            # find the ')' closing the parameter list, THEN the first ';' or body '{'
            paren_pos = buf.find('(')
            pdepth = 0; end_paren = None
            for k in range(max(paren_pos, 0), len(buf)):
                if buf[k] == '(': pdepth += 1
                elif buf[k] == ')':
                    pdepth -= 1
                    if pdepth == 0: end_paren = k; break
            cut_at = len(buf)
            if end_paren is not None:
                m2 = re.search(r'[;{]', buf[end_paren + 1:])
                if m2: cut_at = end_paren + 1 + m2.start()
            buf = re.sub(r'\s+', ' ', buf[:cut_at]).strip()
            doc = clean_doc(docs)
            out.append(dict(name=name, signature=buf[:600], doc=doc,
                            decorators=list(decorators)))
            docs = []; decorators = []
            i = stop_line + 1
            continue
        docs = []; decorators = []
        i += 1
    return out

# index type definitions by name, preferring production + same package
def resolve_type(typ, pkg, key):
    base = re.match(r'^([A-Za-z_$][\w$]*)', typ.strip())
    if not base: return None
    name = base.group(1)
    cands = type_defs.get(name, [])
    if not cands: return None
    def rank(c):
        return (0 if c['scope'] == 'production' else 1,
                0 if c['package'] == pkg else 1,
                0 if c['kind'] in ('interface', 'class') else 1)
    cands = sorted(cands, key=rank)
    return cands[0]

# ---------------------------------------------------------------- asar cross-check
asar_keys = collections.defaultdict(set)
asar_files = 0
pat_js_provide = re.compile(r"provide\s*\(\s*(['\"])([^'\"]+)\1")
pat_js_super = re.compile(r"super\s*\(\s*ctx\s*,\s*(['\"])([^'\"]+)\1")
pat_js_inject = re.compile(r"inject\s*=\s*\[([\s\S]*?)\]")
for dp, dn, fn in os.walk(ASAR):
    for f in fn:
        if not f.endswith('.js'): continue
        p = os.path.join(dp, f)
        asar_files += 1
        s = open(p, encoding='utf-8', errors='replace').read()
        for m in pat_js_provide.finditer(s): asar_keys[m.group(2)].add('provide')
        for m in pat_js_super.finditer(s): asar_keys[m.group(2)].add('super')
        for m in pat_js_inject.finditer(s):
            for x in str_re.finditer(m.group(1)): asar_keys[x.group(2)].add('inject')
log('asar js files scanned:', asar_files, 'distinct keys:', len(asar_keys))

# ---------------------------------------------------------------- assemble services
prod_decl = [d for d in declarations if d['scope'] == 'production']
test_decl = [d for d in declarations if d['scope'] == 'test']
by_key = collections.defaultdict(list)
for d in prod_decl: by_key[d['key']].append(d)

prov_by_key = collections.defaultdict(list)
for c in provide_calls:
    if c.get('key') and c['scope'] == 'production': prov_by_key[c['key']].append(c)
for c in super_regs:
    if c['scope'] == 'production': prov_by_key[c['key']].append(dict(c, kind='TypertRemoteService.super'))

cons_by_key = collections.defaultdict(list)
for a in inject_arrays:
    if a['scope'] != 'production': continue
    for k in a['deps']:
        cons_by_key[k].append(dict(file=a['file'], line=a['line'], package=a['package'],
                                   via='inject', all=a['deps']))
for g in ctx_gets:
    if g['scope'] == 'production':
        cons_by_key[g['key']].append(dict(file=g['file'], line=g['line'], package=g['package'],
                                          via='ctx.get', all=[g['key']]))

services = []
for key in sorted(by_key):
    ds = by_key[key]
    primary = ds[0]
    td = resolve_type(primary['type'], primary['package'], key)
    methods = parse_signatures(td['body']) if td else []
    # dedupe methods by name+signature
    seen = set(); uniq = []
    for m in methods:
        k = (m['name'], m['signature'])
        if k not in seen: seen.add(k); uniq.append(m)
    ak = sorted(asar_keys.get(key, []))
    services.append(dict(
        key=key,
        type=primary['type'],
        doc=primary['doc'],
        optional=primary['optional'],
        declarations=[dict(file=d['file'], line=d['line'], package=d['package'],
                           raw=d['raw']) for d in ds],
        providers=[dict(file=c['file'], line=c['line'], package=c['package'],
                        kind=c.get('kind', 'ctx.reflect.provide' if c.get('reflect') else 'ctx.provide'))
                   for c in prov_by_key.get(key, [])],
        consumers=cons_by_key.get(key, []),
        methods=uniq,
        methodSource=(dict(file=td['file'], line=td['line'], kind=td['kind'],
                           package=td['package']) if td else None),
        methodCoverage=('resolved' if td else 'unresolved'),
        asar=dict(seen=bool(ak), evidence=ak),
    ))

log('production keys:', len(services),
      'with providers:', sum(1 for x in services if x['providers']),
      'with consumers:', sum(1 for x in services if x['consumers']),
      'methods resolved:', sum(1 for x in services if x['methodCoverage'] == 'resolved'),
      'asar-confirmed:', sum(1 for x in services if x['asar']['seen']))
log('method total:', sum(len(x['methods']) for x in services))

result = dict(
    meta=dict(
        layer='C_cordis_ctx',
        source='deepseek-ai/deepseek-harness',
        tag=TAG, commit=SHA,
        sourceTree=ROOT,
        sourceTreeFileCount=len(ts_files),
        asarTree=ASAR,
        asarJsFiles=asar_files,
        extraction='typed declaration merging (declare module ... interface Context), NOT reverse-engineering',
    ),
    mechanism=dict(
        providerFramework='@deepseek-ai/cordis',
        declarationIdiom="declare module '@deepseek-ai/cordis' { interface Context { <key>: <Type> } }",
        registrationIdioms=['ctx.provide(name, value)', 'ctx.reflect.provide(name, self, check)',
                            'TypertRemoteService: super(ctx, key, { namespace })'],
        dependencyIdioms=['static inject = [...]', 'const inject = [...]', 'exports.inject = inject',
                          'ctx.get(name) for optional service reads'],
        note='ctx.<key> is a typed, declaration-merged property; strict inject reads the global service store, ctx.get reads optionally.',
    ),
    coverage=dict(
        productionKeys=len(services),
        testOnlyDeclarations=len(test_decl),
        testOnlyKeys=len({d['key'] for d in test_decl}),
        withProvider=sum(1 for x in services if x['providers']),
        withConsumers=sum(1 for x in services if x['consumers']),
        methodsResolved=sum(1 for x in services if x['methodCoverage'] == 'resolved'),
        methodSignatures=sum(len(x['methods']) for x in services),
        asarConfirmed=sum(1 for x in services if x['asar']['seen']),
        asarDistinctKeys=len(asar_keys),
    ),
    services=services,
    injectEdges=[dict(file=a['file'], line=a['line'], package=a['package'],
                      scope=a['scope'], deps=a['deps']) for a in inject_arrays],
    provideCalls=[dict(file=c['file'], line=c['line'], package=c['package'],
                       scope=c['scope'], key=c.get('key'), variable=c.get('variable'),
                       reflect=c.get('reflect', False)) for c in provide_calls],
    ctxGetCalls=ctx_gets,
    testFixtures=dict(count=len(test_decl), keys=sorted({d['key'] for d in test_decl})),
)
json.dump(result, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
log('wrote', OUT, os.path.getsize(OUT), 'bytes')

