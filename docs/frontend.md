# Building the frontend SPA

The frontend is a single‑page application that talks exclusively to the hub’s REST and WebSocket API.  You can build it with any modern JavaScript framework.  This guide focuses on [SvelteKit](https://svelte.dev) and [Vite](https://vite.dev), but the same principles apply to React, Vue or any other template supported by Vite.

## Choosing a framework

* **SvelteKit** – The official application framework for Svelte.  It is powered by Vite and provides routing, layouts and server logic.  Create a new project by running `npx sv create myapp && cd myapp && npm install && npm run dev`【884361458094095†L124-L131】.  During development, the app runs on `localhost:5173`.
* **Vite with template** – Vite can scaffold a project for multiple frameworks.  To create a project interactively, run `npm create vite@latest` and follow the prompts【986861734222727†L238-L258】.  You can also specify a template and project name in one command:

  ```bash
  # Create a React project (React + SWC + TypeScript variant)
  npm create vite@latest my-react-app -- --template react-swc

  # Create a Svelte project
  npm create vite@latest my-svelte-app -- --template svelte
  ```

  The `--template` flag accepts many values including `vanilla`, `react`, `react-ts`, `svelte`, `svelte-ts` and others【986861734222727†L265-L297】.  See the Vite documentation for more details.

Vite requires Node 20.19 or newer【986861734222727†L258-L262】.  After scaffolding your project, install dependencies with your package manager (e.g., `npm install`) and start the dev server with `npm run dev`.  Visit `http://localhost:5173` to view the app.

## Connecting to the hub

Your SPA should not call rclone directly; instead it should send requests to the hub.  During development the hub runs on `http://<hub‑tailscale‑ip>:8000`.  When the frontend runs from `localhost:5173` you may need to configure CORS on the hub to allow cross‑origin requests; FastAPI makes this easy with [`fastapi.middleware.cors`](https://fastapi.tiangolo.com/tutorial/cors/).

### Example API call

Here is a minimal example using the Fetch API to list nodes:

```js
// src/lib/api.js
export async function listNodes() {
  const res = await fetch('http://<hub-ip>:8000/v1/nodes');
  if (!res.ok) throw new Error('Failed to fetch nodes');
  return res.json();
}
```

You can then call this function inside your Svelte component or React hook and render the nodes in a table.  For streaming stats via WebSockets, open a `new EventSource('http://<hub-ip>:8000/v1/stream')` or use the native `WebSocket` API to read newline‑delimited JSON messages.

### Handling authentication

If you enabled API keys on the hub, include the key in an HTTP header.  For example:

```js
fetch('http://<hub-ip>:8000/v1/nodes', {
  headers: {
    'X-API-Key': '<your-key>'
  }
});
```

You can also protect the frontend itself via HTTP basic auth at the reverse proxy or by serving it only to your tailnet.

## Production build

When you are ready to deploy the SPA, run `npm run build`.  Vite outputs static files into a `dist` directory.  You can serve these files from the hub’s `/static` route, from a separate Nginx container, or even from a CDN.  The hub does not impose any restrictions on where the frontend is hosted; as long as it can reach the hub over the tailnet the application will work.

## Future enhancements

* **UI kit** – Consider using a component library such as [Shadcn/UI](https://ui.shadcn.com/) or [Tailwind CSS](https://tailwindcss.com) to accelerate development and ensure a consistent look.
* **Job wizard** – Implement a multi‑step form that runs a dry‑run preview, displays the list of operations and asks the user for confirmation before starting a transfer.  Save frequently used presets.
* **Scheduler** – Build UI pages to manage scheduled jobs (cron expressions, last run status and logs).  The hub can later execute these schedules automatically.
* **Diff/preview** – For `sync` operations, render planned deletions and updates.  Require explicit confirmation before deleting files on the destination.
