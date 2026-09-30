#!/bin/sh
set -e
cd "$(dirname "$0")"
flatpak-builder --user --force-clean --install \
    --state-dir=.flatpak-builder \
    build io.github.samugallo06.noot.yaml