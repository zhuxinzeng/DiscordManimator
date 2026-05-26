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

### 5. 502 SERVICE_UNAVAILABLE 排查

这是一个 **Discord Bot**，不是网站。公网域名只用于 Zeabur 健康检查，正常访问应看到纯文本或 `/health` 返回 `ok`。

若出现 502，按顺序检查：

1. **Networking 端口**：Zeabur 控制台 → 服务 → **Networking** → 容器端口必须是 **8080**（与 `Dockerfile` 的 `EXPOSE 8080` 一致）。域名应绑定到这个端口。
2. **不要手动改 `PORT`**：除非你知道在做什么，否则删掉自定义的 `PORT` 环境变量，让 Zeabur 自动注入。
3. **看 Logs**：若容器启动后立刻退出（Token 无效、配置错误等），网关也会 502。日志里应有 `Health check server listening` 和 `Logged in as ...`。
4. **重新部署**：推送最新代码后 Redeploy（已修复：Docker 初始化不再阻塞 Bot 启动）。
5. **Bot 是否在线**：502 不影响 Discord 侧——若日志显示已登录，在 Discord 服务器成员列表里看 Bot 是否在线即可。
