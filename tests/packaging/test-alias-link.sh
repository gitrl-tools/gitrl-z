#!/bin/sh

set -eu

if [ $# -ne 1 ]; then
	echo "usage: $0 <build directory>" >&2
	exit 2
fi

build=$1
dest=$(mktemp -d)
trap 'rm -rf "$dest"' EXIT

install_to_dest()
{
	meson install -C "$build" --no-rebuild --quiet --destdir "$dest" \
		>/dev/null
}

install_to_dest

prefix=$(meson introspect "$build" --buildoptions | python3 -c 'import json, sys; print([o["value"] for o in json.load(sys.stdin) if o["name"] == "prefix"][0])')

cd "$dest$prefix"

links="bin/gitz share/bash-completion/completions/gitz share/man/man1/gitz.1"

for link in $links; do
	if ! cmp -s "$link" "$(dirname "$link")/gitrlz${link##*/gitz}"; then
		echo "test-alias-link.sh: $link is not the same as gitrlz" >&2
		exit 1
	fi
done

DESTDIR=$dest share/gitrl-z/alias-link.sh remove

for link in $links; do
	if [ -e "$link" ] || [ -L "$link" ]; then
		echo "test-alias-link.sh: the removal left $link" >&2
		exit 1
	fi
done

keeps_other()
{
	before=$(ls -l bin/gitz)
	install_to_dest
	DESTDIR=$dest share/gitrl-z/alias-link.sh remove

	if [ "$(ls -l bin/gitz)" != "$before" ]; then
		echo "test-alias-link.sh: another bin/gitz was changed" >&2
		exit 1
	fi

	for link in $links; do
		if [ "$link" != bin/gitz ] && [ -e "$link" ]; then
			echo "test-alias-link.sh: $link beside another bin/gitz" >&2
			exit 1
		fi
	done

	rm bin/gitz
}

echo other >bin/gitz
keeps_other
ln -s /bin/true bin/gitz
keeps_other

echo "gitz is linked to gitrlz, removed, and a gitz of another owner is kept"
