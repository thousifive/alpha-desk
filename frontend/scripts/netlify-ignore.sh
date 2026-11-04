#!/bin/sh
# Netlify "ignore" command: exit 0 skips the build (no deploy, no deploy credits), exit 1 builds.
# Runs from the base directory (frontend/). Env vars are set by Netlify.
set -u

if [ "${CONTEXT:-}" != "production" ] || [ "${BRANCH:-}" != "main" ]; then
  echo "skip: ${CONTEXT:-?} build of ${BRANCH:-?} (only main deploys)"
  exit 0
fi

# First deploy, or a "clear cache and deploy": nothing to compare against, so build.
if [ -z "${CACHED_COMMIT_REF:-}" ] || [ "${CACHED_COMMIT_REF}" = "${COMMIT_REF:-}" ]; then
  exit 1
fi

# The bundle includes frontend/ and the backend Python the browser runs (backend/app/*.py via
# ?raw imports). Anything else (docs, content YAML, server-only config) doesn't change it.
if git diff --quiet "$CACHED_COMMIT_REF" "$COMMIT_REF" -- . ../backend/app ../netlify.toml; then
  echo "skip: no changes that affect the frontend build"
  exit 0
fi
exit 1
