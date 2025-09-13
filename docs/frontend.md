# Frontend Development

This document provides guidance for developing the frontend single-page application (SPA).

## Scaffolding a Project

You can use Vite to scaffold a new Svelte or React project.

### SvelteKit

```bash
npx sv create myapp
cd myapp
npm install
npm run dev
```

### Vite (Svelte or React)

```bash
npm create vite@latest my-app -- --template svelte
# or
npm create vite@latest my-app -- --template react
```

## API Interaction

The frontend should exclusively communicate with the backend hub's API. It should not directly contact the rclone agents. All requests to the hub's API must include the API key in the `X-API-Key` header.
