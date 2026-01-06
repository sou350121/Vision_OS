# Releasing

This repo is designed to be usable without hardware (UI/dashboard) and optionally with WujiHand hardware (Python bridge).

## Before you tag a release

- Ensure the working tree is clean:
  - `git status`
- Run tests:
  - `npm test`
  - `pytest -q`

## Create a tag

Create an annotated tag:

```bash
git tag -a v1.0.0 -m "v1.0.0"
```

## Push to GitHub

Note: after running `git-filter-repo`, the `origin` remote may be removed to prevent accidental pushes.

Re-add your remote (example):

```bash
git remote add origin <your-github-repo-url>
```

Push branch + tags:

```bash
git push -u origin main
git push origin --tags
```

## GitHub Release notes (suggested)

Use a short release description:

- Highlights: ~50ms latency hardware control, ARM safety switch, auto USB scan, cyberpunk dashboard UI
- Quick Start: `python wuji_bridge.py --max-speed 2.0` + `npm run dev:8080`
- Hardware notes: see `docs/WUJI_INTEGRATION.md`


