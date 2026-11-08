# Screen inventory — Glimpse

**Source:** `source:our-skill` · provenance: `workflow.screen-inventory`  
Filled 2026-11-08 (Europe/Rome) while trialing `/frontend-design` on `startupDB`.

## Meta

- Product: Glimpse — searchable directory of Italian innovative startups
- Audience: operators / scouts exploring the public registry with LLM-enriched tags
- Primary platform: web (desktop + mobile web)
- Page kind: app-ui (dashboard), not marketing

## Screens

### 1. Directory (home)

| Field | Value |
|-------|-------|
| Name | Company directory |
| Route / entry | `/` |
| Purpose | Search, filter, and browse tagged registry companies |
| Primary CTA | Open a company row → detail |
| Secondary CTA | Export CSV; Feedback |
| Key data shown | Overview stats; company name, one-liner, sectors/products/customers, place, VC relevance, homepage evidence |
| Empty state | “No companies match these filters” with recovery copy; past-end page has its own message |
| Loading state | Sticky `PendingBar` + dimmed results (`aria-busy`) |
| Error state | Relies on Next error boundary / host; no dedicated query-error surface yet |
| Success / confirmation | Feedback popover success (header) |
| Desktop notes | Sticky header + command bar; 256px filter aside; result list |
| Mobile notes | Filters in sheet (`MobileFilters`); search full-width; signals wrap under title |
| Provenance plan | `checklist.unslop-20`, `a11y.baseline`, `impeccable.critique-audit-polish`, `anti.inter-everywhere` |
| Source tags | `source:our-skill`, `source:impeccable` |

### 2. Company detail

| Field | Value |
|-------|-------|
| Name | Company profile |
| Route / entry | `/company/[cf]` |
| Purpose | Inspect one company’s tags, evidence, and registry facts |
| Primary CTA | Visit homepage / back to filtered results |
| Secondary CTA | Feedback on this company |
| Key data shown | Tags, VC signal, fetch quality, registry fields, one-liner |
| Empty state | `not-found` when CF missing |
| Loading state | Server render; no client pending chrome on this route |
| Error state | `not-found.tsx` |
| Success / confirmation | Feedback |
| Desktop notes | Card sections with eyebrow headers |
| Mobile notes | Stacked cards |
| Provenance plan | `a11y.baseline`, `craft.tight-palette` |
| Source tags | `source:our-skill` |

### 3. Not found

| Field | Value |
|-------|-------|
| Name | Not found |
| Route / entry | `web/app/not-found.tsx` |
| Purpose | Recover from bad company CF or unknown route |
| Primary CTA | Back to directory |
| Empty / loading / error | N/A (is the error surface) |
| Provenance plan | `a11y.baseline` |
| Source tags | `source:our-skill` |

## Checklist before coding

- [x] Every user journey has a screen (browse → detail → back)
- [x] Auth gates listed — none (public read dashboard)
- [x] Settings / empty / error covered (empty + not-found; dedicated fetch-error still open)
- [x] No screen missing a primary action
