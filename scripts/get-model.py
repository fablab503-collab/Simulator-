"""Downloads Gimmich's AI models from Hugging Face and checks for updates.

Usage:
  python3 get-model.py list                  every model, its size and what it's for
  python3 get-model.py pick <system>         the model to use for a system (e.g. android)
  python3 get-model.py get <model> [--full] [--dest DIR]
                                             download it (compressed by default;
                                             --full = the original, for GPUs/training)
  python3 get-model.py get all [--full]      download every model
  python3 get-model.py check                 is a newer version out?

Downloads resume where they stopped. Set HF_TOKEN (e.g. from a GitHub or
Google Cloud secret, never in this repo) if Hugging Face asks you to log in.
Needs only Python 3.11+.
"""
import json
import os
import sys
import tomllib
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.join(HERE, "..", "models", "models.toml")
HF = "https://huggingface.co"


def catalog():
    with open(CATALOG, "rb") as f:
        data = tomllib.load(f)
    defaults = data.pop("default")
    return data, defaults


def request(url):
    req = urllib.request.Request(url)
    if os.environ.get("HF_TOKEN"):
        req.add_header("Authorization", "Bearer " + os.environ["HF_TOKEN"])
    return req


def repo_info(repo, rev="main"):
    with urllib.request.urlopen(request("%s/api/models/%s/revision/%s?blobs=true" % (HF, repo, rev)), timeout=60) as r:
        return json.load(r)


def files_to_get(model, full):
    """Returns (repo, revision, [(file, size)]) for the full or compressed copy."""
    if full or "small" not in model:
        repo, rev = model["full"], model["rev"]
        files = [(s["rfilename"], s.get("size") or 0) for s in repo_info(repo, rev)["siblings"]]
        return repo, rev, files
    repo, rev = model["small"], model["small_rev"]
    ggufs = [(s["rfilename"], s.get("size") or 0) for s in repo_info(repo, rev)["siblings"]
             if s["rfilename"].endswith(".gguf")]
    brain = [f for f in ggufs if "q4_k_m" in f[0].lower() and "mmproj" not in f[0].lower()][:1]
    eyes = []
    for kind in ("q8_0", "f16", "bf16"):  # smallest good "eyes" file first
        eyes = [f for f in ggufs if "mmproj" in f[0].lower() and kind in f[0].lower()
                and not (kind == "f16" and "bf16" in f[0].lower())][:1]
        if eyes:
            break
    return repo, rev, brain + eyes


def download(repo, rev, name, size, dest):
    path = os.path.join(dest, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    have = os.path.getsize(path) if os.path.exists(path) else 0
    if size and have == size:
        print("  have %s" % name)
        return path
    req = request("%s/%s/resolve/%s/%s" % (HF, repo, rev, name))
    if have:
        req.add_header("Range", "bytes=%d-" % have)  # carry on where it stopped
    with urllib.request.urlopen(req, timeout=120) as r, open(path, "ab" if have else "wb") as out:
        if have and r.status != 206:  # server ignored the resume: start again
            out.seek(0)
            out.truncate()
            have = 0
        done, step = have, 0
        while chunk := r.read(1 << 20):
            out.write(chunk)
            done += len(chunk)
            if size and done * 10 // size > step:
                step = done * 10 // size
                print("  %s: %d%%" % (name, step * 10), flush=True)
    print("  got %s (%.2f GB)" % (name, os.path.getsize(path) / 1e9))
    return path


def main():
    models, defaults = catalog()
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return
    cmd = args[0]
    if cmd == "list":
        for key, m in models.items():
            where = "small + full" if "small" in m else "full only"
            print("%-18s %-22s %-12s %s · %s" % (key, m["name"], where, ", ".join(m["for"]), m["good_at"]))
    elif cmd == "pick":
        system = args[1] if len(args) > 1 else "any"
        print(defaults.get(system, defaults["any"]))
    elif cmd == "get":
        full = "--full" in args
        dest = args[args.index("--dest") + 1] if "--dest" in args else os.path.join(os.getcwd(), "gimmich-models")
        keys = list(models) if args[1] == "all" else [args[1]]
        for key in keys:
            if key not in models:
                sys.exit("Unknown model %r. Try: python3 get-model.py list" % key)
            repo, rev, files = files_to_get(models[key], full)
            total = sum(s for _, s in files)
            print("%s: %d file(s), %.1f GB from %s" % (key, len(files), total / 1e9, repo))
            for name, size in files:
                download(repo, rev, name, size, os.path.join(dest, key))
    elif cmd == "check":
        # One line per model and copy: up to date, or a newer version is out.
        print("| Model | Copy | Ours | Newest | |\n|---|---|---|---|---|")
        for key, m in models.items():
            for copy, repo, rev in (("full", m["full"], m["rev"]), ("small", m.get("small"), m.get("small_rev"))):
                if not repo:
                    continue
                try:
                    newest = repo_info(repo)["sha"]
                    state = "✅ up to date" if newest == rev else "🆕 update available"
                except Exception as e:  # e.g. the model was removed or renamed
                    newest, state = "?", "⚠️ %s" % e
                print("| %s | %s | %s | %s | %s |" % (key, copy, rev[:10], newest[:10], state))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
