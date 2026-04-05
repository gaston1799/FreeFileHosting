# Playwright Verify

Use this after the repo is pushed to GitHub.

Set:
- `GITHUB_TREE_URL` to the repo tree for `inject/`
- `RAW_ENTRY_URL` to the raw `inject/entry.lua` URL
- `RAW_MODULE_URL` to one raw module URL, for example `inject/modules/Forbidden/AI/__module.lua`

PowerShell example:

```powershell
$env:CODEX_HOME = $env:CODEX_HOME ? $env:CODEX_HOME : "$HOME/.codex"
$PWCLI = "$env:CODEX_HOME/skills/playwright/scripts/playwright_cli.sh"

bash $PWCLI open "GITHUB_TREE_URL" --headed
bash $PWCLI snapshot

bash $PWCLI tab-new "RAW_ENTRY_URL"
bash $PWCLI snapshot

bash $PWCLI tab-new "RAW_MODULE_URL"
bash $PWCLI snapshot
```

What to verify:
- the GitHub tree shows `inject/entry.lua`
- the raw entry URL is reachable
- at least one dependent raw module URL is reachable
- raw module contents are Lua source, not an error page
