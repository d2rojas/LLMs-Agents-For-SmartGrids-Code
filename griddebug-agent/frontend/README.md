# Frontend

Next.js web interface for GridDebugAgent.

## Setup

```bash
npm install
npm run dev
```

Runs on http://localhost:3000

## Structure

```
src/
├── app/                 # Next.js app router
├── components/          # React components
│   ├── ui/              # shadcn/ui primitives
│   ├── diagnostic-layout.tsx
│   ├── input-panel.tsx
│   └── results-panel.tsx
├── data/                # Mock data (todo replace with API)
└── types/               # TypeScript interfaces
```
