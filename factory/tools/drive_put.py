#!/usr/bin/env python3
"""Upload a large file (a finished film) to a Google Drive upload session (X-Goog-Upload protocol) in 32 MiB chunks,
resuming after errors. The session URI comes from a Drive resumable-upload start (one URI per file, valid 7 days).
usage: python3 factory/tools/drive_put.py FILE SESSION_URI_FILE      prints DONE <file id> at the end"""
import sys, os, time, json, urllib.request, urllib.error
path, uri = sys.argv[1], open(sys.argv[2]).read().strip()
total = os.path.getsize(path); CH = 32 * 1024 * 1024   # multiple of 256 KiB

def req(cmd, data=b'', off=None):
    h = {'X-Goog-Upload-Command': cmd, 'Content-Length': str(len(data))}
    if off is not None: h['X-Goog-Upload-Offset'] = str(off)
    r = urllib.request.Request(uri, data=data, method='POST' if cmd == 'query' else 'PUT', headers=h)
    try:
        x = urllib.request.urlopen(r, timeout=900); return x.status, x.read(), {k.lower(): v for k, v in x.headers.items()}
    except urllib.error.HTTPError as e:
        return e.code, e.read(), {k.lower(): v for k, v in e.headers.items()}

def query():
    st, body, h = req('query')
    return h.get('x-goog-upload-status'), int(h.get('x-goog-upload-size-received', 0)), body

status, off, _ = query(); tries = 0
print('start at', off, 'status', status, flush=True)
with open(path, 'rb') as f:
    while True:
        f.seek(off); data = f.read(CH); last = off + len(data) >= total
        try:
            st, body, h = req('upload, finalize' if last else 'upload', data, off)
        except Exception as e:
            st, body, h = -1, str(e).encode(), {}
        s = h.get('x-goog-upload-status')
        if s == 'final' and st in (200, 201):
            print('DONE', json.loads(body).get('id') if body else ''); sys.exit(0)
        if s == 'active' and st == 200 and not last:
            off += len(data); tries = 0; print(f'{off / total * 100:.0f}%', flush=True); continue
        tries += 1; print('retry', st, s, body[:200], flush=True)
        if tries > 8: print('FAILED'); sys.exit(1)
        time.sleep(5 * tries)
        status, off, body = query()
        if status == 'final': print('DONE (already final)'); sys.exit(0)
