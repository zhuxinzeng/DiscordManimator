#!/bin/sh
set -e

start_dockerd_if_needed() {
  if [ -n "$DOCKER_HOST" ]; then
    echo "Using remote Docker at $DOCKER_HOST"
    return 0
  fi

  if docker info >/dev/null 2>&1; then
    echo "Docker is already available"
    return 0
  fi

  if ! command -v dockerd >/dev/null 2>&1; then
    echo "WARNING: Docker daemon unavailable; set DOCKER_HOST or enable privileged mode for rendering"
    return 0
  fi

  echo "Starting local Docker daemon..."
  dockerd >/var/log/dockerd.log 2>&1 &
  i=0
  while [ "$i" -lt 60 ]; do
    if docker info >/dev/null 2>&1; then
      echo "Docker daemon is ready"
      return 0
    fi
    i=$((i + 1))
    sleep 1
  done

  echo "WARNING: Docker daemon did not become ready; Manim rendering may fail"
}

start_dockerd_if_needed

if docker info >/dev/null 2>&1; then
  MANIM_IMAGE="${DISCORDMANIMATOR_RENDER__DOCKER_IMAGE:-manimcommunity/manim:stable}"
  echo "Pulling Manim image $MANIM_IMAGE in background..."
  docker pull "$MANIM_IMAGE" >/dev/null 2>&1 &
fi

CONFIG_ARGS=""
if [ -n "$CONFIG_PATH" ] && [ -f "$CONFIG_PATH" ]; then
  CONFIG_ARGS="$CONFIG_PATH"
fi

exec python -m discordmanimator $CONFIG_ARGS
