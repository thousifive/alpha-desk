# Sourced by the other scripts: values docker-compose.yml reads from the environment.
export ALPHA_HOST="${ALPHA_HOST:-$(hostname -s 2>/dev/null || hostname)}"
export ALPHA_UID="${ALPHA_UID:-$(id -u)}"
export ALPHA_GID="${ALPHA_GID:-$(id -g)}"
export GIT_SHA="${GIT_SHA:-$(git rev-parse HEAD 2>/dev/null || true)}"
