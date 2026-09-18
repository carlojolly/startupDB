@AGENTS.md

Claude Code specifics: the dev server is defined in `.claude/launch.json`
(`startup-map-web`, port 3000); use the preview tool rather than Bash to run
it. The database is unreachable from a network without IPv6 unless
`DATABASE_URL` uses the Session pooler host, so treat every database-backed
check as "not verified" unless its real output is in front of you.
