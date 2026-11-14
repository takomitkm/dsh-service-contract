import os, re, json, collections

ROOT = r'S:\apps\llm\agentwork\.tmp\dsh-src'
PKGS = os.path.join(ROOT, 'packages')

files = []
for dp, dn, fn in os.walk(PKGS):
    for f in fn:
        if f.endswith(('.ts', '.tsx')):
            files.append(os.path.join(dp, f))
print('package .ts files:', len(files))

pat_declmod = re.compile(r"declare\s+module\s+['\"]@deepseek-ai/cordis['\"]")
pat_ctxprovide = re.compile(r"ctx(?:\.reflect)?\.provide\s*\(\s*['\"]([^'\"]+)['\"]")
pat_service_call = re.compile(r"Context\.service\s*\(")
pat_static_inject = re.compile(r"static\s+inject\s*=\s*\[")
pat_const_inject = re.compile(r"(?:export\s+)?const\s+inject\s*=\s*\[")
pat_servicecls = re.compile(r"(?:export\s+)?class\s+(\w+)\s+extends\s+(\w*(?:Service|RemoteService)\w*)")

counts = collections.Counter()
decl_files = []
for p in files:
    s = open(p, encoding='utf-8', errors='replace').read()
    is_test = ('/tests/' in p.replace('\\','/')) or p.endswith(('.spec.ts','.test.ts'))
    for name, pat in [('declmod',pat_declmod),('ctxprovide',pat_ctxprovide),('Context.service',pat_service_call),('static.inject',pat_static_inject),('const.inject',pat_const_inject),('ServiceClass',pat_servicecls)]:
        n = len(pat.findall(s))
        if n:
            counts[name] += n
            if name == 'declmod': decl_files.append(p)
    if pat_declmod.search(s): counts['declmod.files'] += 1
    if is_test: counts['test.files'] += 1
print(json.dumps(counts, indent=2))
print('\nsample declmod files:')
for p in decl_files[:8]: print(' ', os.path.relpath(p, ROOT))
