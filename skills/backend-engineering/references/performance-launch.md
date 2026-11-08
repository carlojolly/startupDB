# App performance and launch readiness

**Source:** `source:user-notes`  
Source claims about pricing/setup time are not independently verified — treat tool names as suggestions.

## 1. Unoptimised database queries

**Problem:** Queries fine with 10 rows crawl with 10,000.

**Fix:** Add indexes to every column the app filters or searches by.

## 2. No caching

**Problem:** Same unchanged data hit on every page load.

**Fix:** Cache slow-changing data (e.g. Redis / Upstash Redis). Invalidate on writes.

## 3. Images not optimised

**Problem:** Full-size images from storage hurt mobile users.

**Fix:** Use platform image optimization (e.g. Vercel / Cloudflare) or an image CDN; serve compressed responsive sizes.

## 4. No load testing before launch

**Problem:** Solo laptop testing hides concurrency failures.

**Fix:** Simulate multi-user traffic with k6 or Artillery before launch.

## 5. No rate limiting

**Problem:** Unlimited public requests invite slowdowns and abuse.

**Fix:** Rate-limit every public endpoint (per IP / per user). Upstash or equivalent is a common option.
