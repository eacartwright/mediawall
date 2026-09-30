"""
Run the app-level checks: each tests/app/check_*.py starts the real
MediaWall in its own process and drives it. Slow (seconds per check),
needs a display and the sample media in MEDIATEST/.

    Windows:  venv\\Scripts\\python.exe tests\\app\\run.py [name ...]
    Linux:    venv/bin/python tests/app/run.py [name ...]

With names (e.g. `browsing layers`), only those checks run. Each check
gets its own scratch settings file, so the real settings are never
touched. Screenshots and scratch projects go to a temporary folder,
printed at the end. Exit code: 0 if everything passed.

(The fast unit tests are separate: python -m unittest)
"""

import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TIMEOUT = 180                       # seconds per check


def main():
    wanted = sys.argv[1:]
    checks = sorted(HERE.glob("check_*.py"))
    if wanted:
        checks = [p for p in checks if p.stem[len("check_"):] in wanted or p.stem in wanted]
        if not checks:
            print("No such checks. Available:",
                  ", ".join(p.stem[len("check_"):] for p in sorted(HERE.glob("check_*.py"))))
            return 2

    out = Path(tempfile.mkdtemp(prefix="mediawall-checks-"))
    total_passed = total = 0
    failed_checks = []

    for path in checks:
        name = path.stem[len("check_"):]
        env = dict(os.environ,
                   MEDIAWALL_CHECK_OUT=str(out / name),
                   MEDIAWALL_SETTINGS=str(out / name / "settings.ini"))
        started = time.monotonic()
        try:
            result = subprocess.run(
                [sys.executable, str(path)], env=env, cwd=HERE,
                stdin=subprocess.DEVNULL, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=TIMEOUT)
            output = result.stdout + result.stderr
        except subprocess.TimeoutExpired as exc:
            output = (exc.stdout or "") + (exc.stderr or "") if isinstance(exc.stdout, str) else ""
            output += f"\nTIMEOUT after {TIMEOUT} s"
        seconds = time.monotonic() - started

        lines = output.splitlines()
        summary = next((l for l in reversed(lines) if re.match(r"^\d+/\d+ passed$", l)), None)
        skipped = any(l.startswith("SKIP") for l in lines)
        problems = [l for l in lines if l.startswith(("FAIL", "JS ERROR", "Traceback", "TIMEOUT"))]

        if skipped:
            print(f"  SKIP  {name:<12} {next(l for l in lines if l.startswith('SKIP'))[6:]}")
            continue
        if summary:
            passed, count = map(int, summary.split()[0].split("/"))
        else:
            passed, count = 0, 1
            problems = problems or ["no result (crashed?)"] + lines[-5:]
        total_passed += passed
        total += count
        ok = summary and passed == count and not problems
        print(f"  {'ok  ' if ok else 'FAIL'}  {name:<12} {passed}/{count}  ({seconds:.0f} s)")
        if not ok:
            failed_checks.append(name)
            for line in problems:
                print(f"          {line}")

    print(f"\n{total_passed}/{total} checks passed"
          + (f"; failing: {', '.join(failed_checks)}" if failed_checks else ""))
    print(f"Screenshots and scratch files: {out}")
    return 0 if not failed_checks and total else 1


if __name__ == "__main__":
    sys.exit(main())
