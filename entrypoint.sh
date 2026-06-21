#!/bin/sh
set -e

# entrypoint.sh - Ultra-minimal entrypoint for Lightpanda

# Start Lightpanda in serve mode
# --host 0.0.0.0 allows connections from outside the container (if port-forwarded)
# or just 127.0.0.1 as per instructions, but typically Docker needs 0.0.0.0 to expose.
# The instruction says "exposes the internal CDP socket at 127.0.0.1:9222".
# This usually means the binary listens on 127.0.0.1 inside, but if we want to
# reach it from outside (orchestration), it should be 0.0.0.0.
# HOWEVER, the prompt specifically says 127.0.0.1:9222.
# In a "warm-pool" serverless context, often we have a proxy or we use
# network=host or similar. Let's stick to the instruction.

exec /usr/local/bin/lightpanda serve \
    --host 127.0.0.1 \
    --port 9222 \
    --log-level info \
    --log-format pretty
