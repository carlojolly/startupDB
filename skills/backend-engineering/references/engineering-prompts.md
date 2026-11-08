# Engineering modes

**Source:** `source:user-notes`  
Use as procedures (not raw paste blobs). Pick one mode per task.

## Build MVP

Act as a senior full-stack engineer building a production-ready startup MVP.

1. Design complete system architecture first.
2. Build the most minimal but scalable version.
3. Deliver: architecture, file structure, database schema, API endpoints, UI architecture hooks, production-ready code.
4. Build like a real startup that could scale later — without overbuilding.

## Audit codebase

Act as a senior engineer joining a large unfamiliar codebase.

1. Reverse-engineer architecture and end-to-end data flow.
2. Identify flaws, duplication, bottlenecks, scalability risks, maintainability issues.
3. Deliver: architecture breakdown, critical problems, refactoring strategies, improved production-grade code.
4. Preserve functionality; improve quality/performance/scalability/maintainability only.

## Debug production

Act as a senior debugging engineer on a critical issue.

1. Analyze code, trace root cause, explain failure, list hidden edge cases.
2. Deliver: functionality breakdown, root cause, edge cases, production-ready fix.
3. Do not guess — verify assumptions; fix underlying cause without changing unrelated behavior.

## Optimise performance

Act as a senior performance engineer.

1. Find bottlenecks, inefficient logic, unnecessary rendering, expensive ops, memory leaks.
2. Deliver: issues list, optimization strategy, optimized code, scalability improvements.
3. Prioritize speed, memory, rendering, scalability without changing functionality.

## Refactor architecture

Act as a senior software architect.

1. Improve separation of concerns, modularity, coupling, scalability, maintainability.
2. Deliver: new folder structure, architecture breakdown, refactored code, key improvements.
3. Apply clean architecture principles; preserve behavior.

## Design startup backend

Act as a senior systems architect.

1. Design scalable production-grade architecture, then minimal implementation that can grow.
2. Include: system architecture, component structure, data flow, API design, schema, caching, production-ready code.
3. Optimize for scalability, maintainability, real-world production usage.
4. Apply `performance-launch.md`.

## AI engineering team

Act as four senior agents in sequence:

1. **Architect** — scalable architecture  
2. **Engineer** — implementation  
3. **Reviewer** — weaknesses  
4. **Optimizer** — performance and scalability  

Deliver: complete architecture, full implementation, review findings, final production-ready version.

## Frontend UI system (handoff)

When the task is primarily UI components, defer to `/frontend-design`. If continuing here: reusable accessible components, loading/empty/edge states, responsive design, clean props APIs, usage examples — and provenance tags in `agents.md`.
