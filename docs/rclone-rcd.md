# Rclone Agent Setup

This document explains how to set up and configure the rclone agents on each server you want to manage.

## Installation

1.  Install rclone on your server. See the [rclone documentation](https://rclone.org/install/) for instructions.
2.  Configure your remotes with `rclone config`.

## Running the Agent

To run the rclone remote control daemon, use the following command:

```bash
rclone rcd --rc-addr=0.0.0.0:5572 --rc-user=your_user --rc-pass=your_pass --rc-serve
```

-   `--rc-addr`: The address and port to listen on. Use your Tailscale IP.
-   `--rc-user` and `--rc-pass`: Credentials for the rclone API.
-   `--rc-serve`: Enables serving of file listings over HTTP.

For security, it is recommended to bind to the Tailscale IP address of the machine. You can also use `--rc-no-auth` if you are relying solely on Tailscale ACLs for security.
