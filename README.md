# DiscordManimator

A Manim Rendering Bot for Discord.

## How to run

Prerequisites:
- Docker daemon running with the `manimcommunity/manim:stable` image pulled
- `uv`, a python dependency manager
- A discord bot token with the `MESSAGE CONTENT` Intent enabled.

Deployment:
- run `uv sync`
- create a new config file `config.toml` based on the template given in `example.config.toml`
- run `uv run python -m discordmanimator path/to/config.toml`

## Deploy on Zeabur

Zeabur detects the root `Dockerfile` and builds the service automatically. The bot listens on `PORT` (set by Zeabur) for health checks at `/health`.

### 1. Create the service

1. Connect this GitHub repository in the Zeabur dashboard.
2. Add a service — Zeabur should pick up the `Dockerfile` (Docker icon on deploy).
3. Under **Networking**, expose port **8080** as **HTTP** (health checks use TCP/HTTP on `PORT`).

### 2. Environment variables

| Variable | Required | Description |
| --- | --- | --- |
| `DISCORDMANIMATOR_TOKEN` | Yes | Discord bot token |
| `PORT` | Auto | Set by Zeabur; do not override unless needed |
| `DOCKER_HOST` | For rendering | Remote Docker API, e.g. `tcp://docker.zeabur.internal:2375` when using the template below |

Optional nested settings use `__`, for example `DISCORDMANIMATOR_RENDER__USE_ONLINETEX=true`. See `example.config.toml` for all options.

You do **not** need to commit `config.toml`; env-only startup is supported:

```bash
python -m discordmanimator
```

### 3. Manim rendering (Docker)

Rendering runs Manim inside Docker containers. On Zeabur you typically need a **second service** running Docker-in-Docker:

- Use `zeabur.template.yaml` (set your GitHub `repoID` on the `bot` service), **or**
- Manually add a `docker:27-dind` prebuilt service and set `DOCKER_HOST=tcp://<service-name>.zeabur.internal:2375` on the bot service.

The entrypoint script pulls `manimcommunity/manim:stable` when Docker is reachable.

### 4. Local Docker build (smoke test)

```bash
docker build -t discordmanimator .
docker run --rm -e DISCORDMANIMATOR_TOKEN="your-token" -e PORT=8080 -p 8080:8080 discordmanimator
```
