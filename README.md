# Forbidden V2 Dump

Exported from Roblox asset `99009254123330` with `remodel`.

Contents:
- `ForbiddenV2.rbxmx`: raw exported model
- `manifest.txt`: exported script index
- `scripts/`: extracted `Script`, `LocalScript`, and `ModuleScript` sources
- `dump_forbidden_v2.lua`: export script used to create this dump
- `inject/`: generated injection-first loader and Git-hosted module tree
- `tools/build_injected_forbidden.py`: rebuilds `inject/` from the dumped sources
- `PLAYWRIGHT_VERIFY.md`: post-push GitHub/raw verification notes

Notes:
- No asset-id `require(12345...)` calls were found in the extracted sources.
- The raw dump in `scripts/` is Git-friendly, but not directly injectable by itself.
- The generated `inject/` tree is the injection-first version. Its top-level entry bootstraps a synthetic module tree and loads internal modules from raw Git URLs.

## Rebuild the injector tree

```powershell
py -3 E:\ForbiddenV2\tools\build_injected_forbidden.py
```

## One-loadstring usage after the repo is pushed

```lua
local url = "https://raw.githubusercontent.com/<owner>/<repo>/<branch>/inject/entry.lua"
local AI = loadstring(game:HttpGet(url), url)()
```

If your executor does not preserve the chunk source for `debug.info`, set the base URL first:

```lua
getgenv().__FORBIDDEN_BASE_URL = "https://raw.githubusercontent.com/<owner>/<repo>/<branch>/inject"
local AI = loadstring(game:HttpGet(getgenv().__FORBIDDEN_BASE_URL .. "/entry.lua"))()
```

Current injected-build behavior differences:
- `AI.InsertAntiLag` is stubbed and warns instead of cloning the dumped anti-lag script.
- Internal `require(script.X)` / `require(root.Y)` relationships are resolved through the synthetic module tree built by `inject/entry.lua`.
