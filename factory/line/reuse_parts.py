#!/usr/bin/env python3
"""Reuse of the render parts of an earlier film run, when only its assembly failed (film.yml input parts_from).
Refused unless: the run is a film.yml run whose render parts all succeeded; its stills job worked on this order with
the stills key approved now; and nothing that makes the parts changed since its commit - only the assembly and its
self-test, this script, the QA sheets, intake/tools, other orders, docs, and workflow lines outside the render job.
usage: reuse_parts.py RUN_ID ORDER_DIR        env: GH_TOKEN, GITHUB_REPOSITORY (checkout with full history)"""
import io, json, os, re, subprocess, sys, urllib.parse, urllib.request, zipfile

RUN, OD = sys.argv[1].strip(), sys.argv[2].rstrip("/")
ORDER = os.path.basename(OD)
REPO = os.environ.get("GITHUB_REPOSITORY", "vidlgtm/videomaps")
H = {"Authorization": f"Bearer {os.environ['GH_TOKEN']}", "Accept": "application/vnd.github+json"}
SAFE = ("factory/line/assemble.sh", "factory/line/selftest_assembly.sh", "factory/line/reuse_parts.py",
        "factory/line/qa_sheets.py", "factory/intake/", "factory/tools/", "README", "LICENSE", ".gitignore")


def die(m):
    print(f"::error::parts_from refused: {m}", flush=True); sys.exit(1)


class _Redirect(urllib.request.HTTPRedirectHandler):          # logs redirect to storage: no token to another host
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None and urllib.parse.urlparse(newurl).netloc != urllib.parse.urlparse(req.full_url).netloc:
            new.remove_header("Authorization")
        return new


OPENER = urllib.request.build_opener(_Redirect)


def api(p, raw=False):
    with OPENER.open(urllib.request.Request(f"https://api.github.com/repos/{REPO}/{p}", headers=H), timeout=120) as r:
        return r.read() if raw else json.load(r)


def git(*a):
    return subprocess.run(["git", *a], capture_output=True, text=True, check=True).stdout


def render_job(text):
    """the render job of film.yml without its run condition (the condition does not change how a part is made)"""
    m = re.search(r"\n  render:\n.*?(?=\n  [a-z_]+:\n)", text, re.S)
    return re.sub(r"(?m)^    if:.*\n", "", m.group(0)) if m else ""


if not RUN.isdigit(): die(f"'{RUN}' is not a run id")
run = api(f"actions/runs/{RUN}")
if not run.get("path", "").endswith("workflows/film.yml"): die(f"run {RUN} is not a film run")
jobs = api(f"actions/runs/{RUN}/jobs?per_page=100")["jobs"]
parts = [j for j in jobs if re.fullmatch(r"render \(\d+\)", j["name"])]
if not parts or any(j["conclusion"] != "success" for j in parts): die(f"run {RUN}: not every render part succeeded")
key = (json.load(open(f"{OD}/order.json", encoding="utf-8")).get("approved") or {}).get("stills", "")
if not key: die("this order has no approved stills key")
st = [j for j in jobs if j["name"] == "stills"]
if not st: die(f"run {RUN} has no stills job")
log = ""
try:
    log = api(f"actions/jobs/{st[0]['id']}/logs", raw=True).decode("utf-8", "replace")
except Exception:                                                 # logs of older runs come as a zip of the run
    z = zipfile.ZipFile(io.BytesIO(api(f"actions/runs/{RUN}/logs", raw=True)))
    log = "\n".join(z.read(n).decode("utf-8", "replace") for n in z.namelist() if "stills" in n)
if not re.search(rf"\bOD: factory/orders/{re.escape(ORDER)}\s*$", log, re.M): die(f"run {RUN} was not a run of the order {ORDER}")
if f"STILLS KEY: {key}" not in log: die(f"run {RUN} rendered other stills than the approved key {key}")
sha = run["head_sha"]
try: git("cat-file", "-e", sha + "^{commit}")
except subprocess.CalledProcessError: die(f"commit {sha[:7]} of run {RUN} is not in this checkout (full history needed)")
changed = [f for f in git("diff", "--name-only", sha, "HEAD").split() if f]
bad = []
for f in changed:
    if f.startswith(SAFE) or (f.startswith("factory/orders/") and not f.startswith(f"factory/orders/{ORDER}/")): continue
    if f == ".github/workflows/film.yml":
        if render_job(git("show", f"{sha}:{f}")) == render_job(open(f, encoding="utf-8").read()): continue
        bad.append(f + " (its render job)"); continue
    if f.startswith(".github/workflows/"): continue
    bad.append(f)
if bad: die(f"since run {RUN} ({sha[:7]}) these files that make the parts changed: " + ", ".join(bad))
print(f"parts of run {RUN} reused: {len(parts)} parts, order {ORDER}, stills {key}, commit {sha[:7]} -> "
      f"{git('rev-parse', '--short', 'HEAD').strip()} ({len(changed)} files changed, none that makes the parts)", flush=True)
