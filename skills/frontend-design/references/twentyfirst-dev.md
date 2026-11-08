# 21st.dev CLI + MCP

**Source:** `source:21st-dev` · provenance: `catalog.21st-sections`  
Site: https://21st.dev · MCP: https://21st.dev/mcp

## Setup

```bash
npm i -g @21st-dev/cli
# user npm prefix is fine if global /usr is locked down
21st login
```

Login opens a browser and saves a token locally.  
In CI/scripts, skip login and pass `--api-key $API_KEY_21ST` (or set `API_KEY_21ST` / `TWENTYFIRST_TOKEN` in the environment).

MCP configs (Cursor `.cursor/mcp.json`, Claude Code `.mcp.json`):

```json
{
  "mcpServers": {
    "21st": {
      "url": "https://21st.dev/api/mcp",
      "headers": { "x-api-key": "${API_KEY_21ST}" }
    }
  }
}
```

Examples also live at repo root: `.cursor/mcp.json.example`, `.mcp.json.example`.

```bash
21st init --client cursor --write
21st init --client claude --write
```

Optional official skills (not vendored here): `21st skills install` → `21st-ui-build`, `21st-ui-review`, etc.

## Agent usage

1. Prefer MCP `search` / CLI `21st search` for heroes, pricing, nav, dashboard widgets, forms **before** hand-rolling.
2. Show options when useful; install/adapt the chosen component to **project tokens** (never keep foreign brand colors).
3. Record in `decision.md`: `source:21st-dev`, `provenance_id:catalog.21st-sections`, plus component id/slug.
4. Map files in `agents.md` Components table.
5. Still run design checklist + a11y after install.
6. If CLI/MCP/key missing: fall back to craft patterns + mockup assets; **do not block** the build.

## Useful commands

```bash
21st whoami
21st search "pricing table" --limit 5
21st get <id>
21st add <user>/<slug>
21st generate "dashboard stats row with sparklines"   # needs AI credits
```
