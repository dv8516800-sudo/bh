# Production-ready, ultra-minimal Dockerfile for Lightpanda
# Optimized for serverless environments (fast startup, small footprint)

# Stage 1: Build Stage
FROM debian:bookworm-slim AS builder

# Build arguments
ARG ZIG_VERSION=0.15.2
ARG V8_VERSION=14.0.365.4
ARG ZIG_V8_TAG=v0.4.8

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    xz-utils \
    ca-certificates \
    clang \
    make \
    pkg-config \
    libglib2.0-dev \
    llvm \
    && rm -rf /var/lib/apt/lists/*

# Install Rust (required for html5ever component)
RUN curl --fail -sSL https://sh.rustup.rs | sh -s -- -y --profile minimal
ENV PATH="/root/.cargo/bin:${PATH}"

# Install Zig
RUN ARCH=$(uname -m) && \
    curl -L https://ziglang.org/download/${ZIG_VERSION}/zig-linux-${ARCH}-${ZIG_VERSION}.tar.xz | tar -xJ -C /usr/local && \
    ln -s /usr/local/zig-linux-${ARCH}-${ZIG_VERSION}/zig /usr/local/bin/zig

WORKDIR /build

# Copy Lightpanda source from the local context
COPY . .

# Download prebuilt V8 static library
RUN mkdir -p v8 && \
    ARCH=$(uname -m) && \
    curl -L -o v8/libc_v8.a https://github.com/lightpanda-io/zig-v8-fork/releases/download/${ZIG_V8_TAG}/libc_v8_${V8_VERSION}_linux_${ARCH}.a

# 1. Build the V8 snapshot creator and generate snapshot.bin
# Target musl for a static binary to ensure it runs on Alpine/Distroless
RUN zig build -Doptimize=ReleaseSmall \
    -Dtarget=$(uname -m)-linux-musl \
    -Dprebuilt_v8_path=v8/libc_v8.a \
    snapshot_creator -- src/snapshot.bin

# 2. Build Lightpanda binary
RUN zig build -Doptimize=ReleaseSmall \
    -Dtarget=$(uname -m)-linux-musl \
    -Dsnapshot_path=../../snapshot.bin \
    -Dprebuilt_v8_path=v8/libc_v8.a

# Stage 2: Final Image
FROM alpine:3.20

# Install runtime dependencies
# tini is used for proper signal handling as PID 1
# ca-certificates are needed for HTTPS requests
RUN apk add --no-cache ca-certificates tini

# Copy the statically linked Lightpanda binary
COPY --from=builder /build/zig-out/bin/lightpanda /usr/local/bin/lightpanda

# Copy the entrypoint script
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Environment variables
ENV LIGHTPANDA_DISABLE_TELEMETRY=true

# Expose the CDP socket port
EXPOSE 9222

# Use tini as the init process
ENTRYPOINT ["/sbin/tini", "--", "entrypoint.sh"]
