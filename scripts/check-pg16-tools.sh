#!/bin/sh
set -eu
for tool in pg_dump pg_restore; do
    path=$(command -v "$tool")
    version=$("$path" --version)
    printf '%s: %s\n' "$path" "$version"
    case "$version" in
        "$tool (PostgreSQL) 16."*) ;;
        *) echo "PostgreSQL 16 client required" >&2; exit 1 ;;
    esac
done
