# Architecture

This document describes the architecture of the Rclone GUI project.

## Components

- **Rclone Agents**: Instances of `rclone rcd` running on each managed server.
- **Backend Hub**: A FastAPI application that proxies requests to the rclone agents.
- **Frontend SPA**: A single-page application for interacting with the hub.

## Network

All communication occurs over a private Tailscale network. The hub and agents are not exposed to the public internet.
