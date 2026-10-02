#!/bin/sh
set -e
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$script_dir"
flatpak-builder --user --force-clean --disable-cache --install \
    --state-dir=.flatpak-builder build io.github.samugallo06.noot.yaml

flatpak build-bundle repo noot.flatpak io.github.samugallo06.noot