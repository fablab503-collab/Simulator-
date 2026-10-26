"""Reads a downloaded project (e.g. a GitHub repository) and works out what it
is: which languages it is written in, how to build, test and run it, and
which Gimmich systems it can go on. It only reads files; it never runs any.

Usage: python3 detect-project.py <folder> [--name NAME]
Prints a JSON plan. On GitHub Actions it also writes one step output per
system (linux, windows, mac, android, ios, web): the JSON list of projects
that system should build, or [].
"""
import json
import os
import re
import sys

SKIP_DIRS = {".git", "node_modules", "vendor", "target", "build", "dist", ".venv", "venv",
             "__pycache__", "third_party", "external", "deps", ".gradle", "Pods"}

# File extension -> language, for the "what is it written in" share.
LANGUAGES = {
    ".rs": "Rust", ".py": "Python", ".js": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".jsx": "JavaScript", ".go": "Go", ".java": "Java",
    ".kt": "Kotlin", ".kts": "Kotlin", ".c": "C", ".h": "C", ".cc": "C++", ".cpp": "C++", ".cxx": "C++",
    ".hpp": "C++", ".hh": "C++", ".cs": "C#", ".swift": "Swift", ".m": "Objective-C", ".mm": "Objective-C",
    ".rb": "Ruby", ".php": "PHP", ".dart": "Dart", ".lua": "Lua", ".zig": "Zig", ".scala": "Scala",
    ".hs": "Haskell", ".ex": "Elixir", ".exs": "Elixir", ".sh": "Shell", ".bash": "Shell", ".ps1": "PowerShell",
    ".html": "HTML", ".htm": "HTML", ".css": "CSS", ".scss": "CSS", ".vue": "Vue", ".svelte": "Svelte",
    ".r": "R", ".jl": "Julia", ".nim": "Nim", ".asm": "Assembly", ".s": "Assembly", ".f90": "Fortran",
}

DESKTOP = ["linux", "windows", "mac"]


def walk(root, max_depth=6):
    for here, dirs, files in os.walk(root):
        depth = os.path.relpath(here, root).count(os.sep)
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".") and depth < max_depth
                   and not d.endswith((".xcodeproj", ".xcworkspace"))]
        yield here, files


def languages(root):
    sizes = {}
    for here, files in walk(root):
        for f in files:
            lang = LANGUAGES.get(os.path.splitext(f)[1].lower())
            if lang:
                try:
                    sizes[lang] = sizes.get(lang, 0) + os.path.getsize(os.path.join(here, f))
                except OSError:
                    pass
    total = sum(sizes.values()) or 1
    return [{"name": k, "share": round(100 * v / total, 1)}
            for k, v in sorted(sizes.items(), key=lambda kv: -kv[1]) if 100 * v / total >= 0.5]


def read(path, limit=200_000):
    try:
        with open(path, errors="replace") as f:
            return f.read(limit)
    except OSError:
        return ""


def project_at(folder, files):
    """Returns the build plan for the project whose root is this folder, or None."""
    has = set(files)
    p = lambda name: os.path.join(folder, name)

    if "Cargo.toml" in has:
        return {"kind": "Rust (Cargo)", "build": "cargo build --release", "test": "cargo test",
                "systems": DESKTOP}
    if "go.mod" in has:
        return {"kind": "Go", "build": "go build ./...", "test": "go test ./...", "systems": DESKTOP}
    if "pubspec.yaml" in has:
        return {"kind": "Flutter / Dart", "build": "flutter pub get && flutter build linux",
                "test": "flutter test", "systems": ["linux", "android"], "needs": "flutter"}
    gradle = next((f for f in ("build.gradle.kts", "build.gradle") if f in has), None)
    if gradle or "settings.gradle" in has or "settings.gradle.kts" in has:
        text = read(p(gradle)) if gradle else ""
        for sub in ("app/build.gradle.kts", "app/build.gradle"):
            text += read(p(sub))
        gradlew = "./gradlew" if "gradlew" in has else "gradle"
        if re.search(r"com\.android\.application|android\s*\{", text):
            return {"kind": "Android app (Gradle)", "build": gradlew + " assembleDebug",
                    "test": gradlew + " testDebugUnitTest", "systems": ["android"],
                    "output": "**/build/outputs/apk/**/*.apk"}
        return {"kind": "Java/Kotlin (Gradle)", "build": gradlew + " build -x test",
                "test": gradlew + " test", "systems": DESKTOP}
    if "pom.xml" in has:
        return {"kind": "Java (Maven)", "build": "mvn -B -q package -DskipTests", "test": "mvn -B -q test",
                "systems": DESKTOP}
    if any(f.endswith((".sln", ".csproj", ".fsproj")) for f in has):
        return {"kind": ".NET", "build": "dotnet build -c Release", "test": "dotnet test",
                "systems": DESKTOP}
    if "Package.swift" in has:
        return {"kind": "Swift package", "build": "swift build -c release", "test": "swift test",
                "systems": ["mac", "linux"]}
    xcode = [f for f in os.listdir(folder) if f.endswith((".xcodeproj", ".xcworkspace"))]
    if xcode:
        return {"kind": "Apple app (Xcode)", "build": "xcodebuild-auto " + xcode[0], "test": "",
                "systems": ["ios", "mac"]}
    if "package.json" in has:
        try:
            pkg = json.loads(read(p("package.json")))
        except ValueError:
            pkg = {}
        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        tool = "pnpm" if "pnpm-lock.yaml" in has else ("yarn" if "yarn.lock" in has else "npm")
        install = {"npm": "npm ci" if "package-lock.json" in has else "npm install",
                   "yarn": "yarn install", "pnpm": "pnpm install"}[tool]
        scripts = pkg.get("scripts", {})
        build = install + (" && %s run build" % tool if "build" in scripts else "")
        kind, systems = "JavaScript/TypeScript (npm)", DESKTOP
        if "electron" in deps:
            kind = "Desktop app (Electron)"
        elif "react-native" in deps or "expo" in deps:
            kind, systems = "Phone app (React Native)", ["android", "ios"]
        elif any(d in deps for d in ("react", "vue", "svelte", "vite", "next", "@angular/core")):
            kind, systems = "Website (" + next(d for d in ("next", "vite", "react", "vue", "svelte", "@angular/core") if d in deps) + ")", ["web"]
        return {"kind": kind, "build": build, "test": tool + " test" if "test" in scripts else "",
                "start": tool + " start" if "start" in scripts else "", "systems": systems}
    if has & {"pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"}:
        install = "python -m pip install ." if has & {"pyproject.toml", "setup.py"} else "python -m pip install -r requirements.txt"
        tests = os.path.isdir(p("tests")) or os.path.isdir(p("test"))
        return {"kind": "Python", "build": install, "test": "python -m pip install pytest && python -m pytest -q" if tests else "",
                "systems": DESKTOP}
    if "CMakeLists.txt" in has:
        return {"kind": "C/C++ (CMake)", "build": "cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build --config Release",
                "test": "ctest --test-dir build -C Release", "systems": DESKTOP}
    if "meson.build" in has:
        return {"kind": "C/C++ (Meson)", "build": "meson setup build && meson compile -C build",
                "test": "meson test -C build", "systems": ["linux", "mac"]}
    if "Makefile" in has or "makefile" in has:
        return {"kind": "Make", "build": "make", "test": "make -q test 2>/dev/null; make test || true",
                "systems": ["linux", "mac"]}
    if "Dockerfile" in has:
        return {"kind": "Docker container", "build": "docker build -t gimmich-app .", "test": "",
                "systems": ["linux"]}
    if "index.html" in has:
        return {"kind": "Website (static)", "build": "", "test": "", "systems": ["web"], "open": "index.html"}
    return None


# Folders full of test copies, not real sub-projects.
NOT_PROJECTS = re.compile(r"(^|/)(tests?|fixtures?|playground|benchmarks?|docs?|e2e|__tests__)(/|$)")


def detect(root):
    """The main project, plus one sub-project of each other kind (for example
    the Android and iPhone example apps inside a C++ library)."""
    projects, kinds = [], set()
    for here, files in walk(root, max_depth=3):
        rel = os.path.relpath(here, root).replace(os.sep, "/")
        if rel != "." and NOT_PROJECTS.search(rel):
            continue
        plan = project_at(here, files)
        if plan and plan["kind"] not in kinds:
            kinds.add(plan["kind"])
            projects.append({"path": rel, **plan})
    return projects


def first_sentence(text):
    """The first line of a README that is a sentence, not a badge or heading."""
    for line in text.splitlines():
        for _ in range(3):  # badges are often images inside links
            line = re.sub(r"!\[[^\]]*\]\([^)]*\)|<[^>]+>", "", line)
            line = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", line)
        line = line.strip(" #*>`|-=_")
        if len(line) > 30 and " " in line and not line.lower().startswith(("warning", "note", "show your", "sponsor")):
            return line[:200]
    return ""


def main():
    root = sys.argv[1]
    name = sys.argv[sys.argv.index("--name") + 1] if "--name" in sys.argv else os.path.basename(os.path.abspath(root))
    readme = next((f for f in os.listdir(root) if f.lower().startswith("readme")), None)
    summary = first_sentence(read(os.path.join(root, readme), 20_000)) if readme else ""
    plan = {"name": name, "summary": summary, "languages": languages(root), "projects": detect(root)}
    for proj in plan["projects"]:
        proj["repo"] = name
    print(json.dumps(plan, indent=2))
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            for system in ("linux", "windows", "mac", "android", "ios", "web"):
                mine = [p for p in plan["projects"] if system in p["systems"]]
                f.write("%s=%s\n" % (system, json.dumps(mine)))


if __name__ == "__main__":
    main()
