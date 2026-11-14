import urllib.request, ssl, tarfile, io, os, sys, time, json

UA = {'User-Agent': 'dsh-contract-extractor'}
TAG = 'dsh-v0.2.2-rc.1'
URL = f'https://codeload.github.com/deepseek-ai/deepseek-harness/tar.gz/refs/tags/{TAG}'
OUT = r'S:\apps\llm\agentwork\.tmp\dsh-rc1.tar.gz'
DEST = r'S:\apps\llm\agentwork\.tmp\dsh-src'

# 1) download full tarball once
t0 = time.time()
req = urllib.request.Request(URL, headers=UA)
with urllib.request.urlopen(req, timeout=240, context=ssl.create_default_context()) as r, open(OUT, 'wb') as f:
    total = 0
    while True:
        chunk = r.read(1 << 20)
        if not chunk: break
        f.write(chunk); total += len(chunk)
print(f'downloaded {total} bytes to {OUT} in {time.time()-t0:.1f}s', flush=True)

# 2) extract only packages/**/src + vendor/**/src .ts/.tsx/.json + top-level manifests
KEEP_EXT = ('.ts', '.tsx', '.json', '.md')
def wanted(name):
    # strip the single top-level dir
    parts = name.split('/', 1)
    if len(parts) < 2: return False
    rel = parts[1]
    if not (rel.startswith('packages/') or rel.startswith('vendor/')): return False
    if '/node_modules/' in rel or '/dist/' in rel or '/lib/' in rel or '/build/' in rel: return False
    if not rel.endswith(KEEP_EXT): return False
    return True

os.makedirs(DEST, exist_ok=True)
n = 0; ts = 0
t1 = time.time()
with tarfile.open(OUT, 'r:gz') as tf:
    for m in tf:
        if not m.isfile(): continue
        if not wanted(m.name): continue
        rel = m.name.split('/', 1)[1]
        dst = os.path.join(DEST, rel.replace('/', os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        src = tf.extractfile(m)
        with open(dst, 'wb') as o:
            o.write(src.read())
        n += 1
        if rel.endswith(('.ts', '.tsx')): ts += 1
print(f'extracted {n} files ({ts} .ts/.tsx) into {DEST} in {time.time()-t1:.1f}s', flush=True)
