# Frontend placeholder

This directory contains documentation for building the single‑page application that communicates with the backend hub.  The actual source code for the frontend is not provided here; instead you will find guidance for scaffolding and connecting your application to the hub.

See `../docs/frontend.md` for detailed instructions on choosing a framework, scaffolding a project with Vite or SvelteKit, and connecting your UI to the hub’s API endpoints.

You are free to organise your frontend however you like.  A typical SvelteKit layout might look like:

```
myapp/
├── src/
│   ├── routes/
│   │   ├── +page.svelte      # dashboard page
│   │   └── job/[uid]/+page.svelte # job detail page
│   └── lib/
│       └── api.js           # helper functions to call the hub
├── static/                  # static assets
├── package.json             # npm scripts
└── vite.config.js           # Vite configuration
```

After building with `npm run build`, copy the contents of `dist/` to a folder served by your hub or another static server.
