#!/bin/sh

set -eu

root=$(dirname "$(dirname "$(dirname "$(readlink -f "$0")")")")
changes=${1:-$(ls "$root"/_build/deb/gitrl-z_*_amd64.changes 2>/dev/null | head -1)}

if [ ! -f "$changes" ]; then
	echo "no .changes found; run docker/build-deb.sh first" >&2
	exit 1
fi

changes=$(readlink -f "$changes")

echo "--- overridden tags (expected, and each one justified in debian/) ---"
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp \
	-v "$(dirname "$changes"):/src" -w /src gitrlz-build \
	lintian --pedantic --show-overrides "$(basename "$changes")" 2>&1 | grep '^O:' || true

echo "--- unoverridden tags (must be none) ---"
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp \
	-v "$(dirname "$changes"):/src" -w /src gitrlz-build \
	lintian --pedantic --info "$(basename "$changes")"

echo "lintian clean"
