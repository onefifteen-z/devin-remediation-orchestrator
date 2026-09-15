# Operations Dashboard

React + TypeScript + Vite frontend for the Devin Remediation Orchestrator.

## Setup

```bash
npm install
cp .env.example .env
npm run dev
```

Dashboard: http://localhost:3000

## Configuration

| Variable | Description |
|----------|-------------|
| `VITE_API_BASE_URL` | Backend URL (default: `http://localhost:8000`) |

Never put secrets in `VITE_*` variables.

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Development server with HMR |
| `npm run build` | Production build |
| `npm test` | Run Vitest unit tests |
| `npm run lint` | Oxlint |
| `npm run preview` | Preview production build |

## Features

- Metrics cards (merge rate, MTTR, CI recovery, verified ACU)
- Throughput chart and Devin org metrics section
- Task table with pagination, filtering, sorting, and expandable rows
- Structured result, CI metadata, and session insights panels
- **Scan labeled issues** and **Refresh** (Devin sync) actions
- Auto-refresh every 15 seconds via TanStack Query

## Tests

```bash
npm test
```

60 unit tests across `src/lib/` and component helpers.
