#!/bin/sh

set -eu

binary=$1
page=$2

version=$("$binary" --version | awk '{ print $2 }')
text=$(sed 's/\\-/-/g' "$page")
status=0

if ! echo "$text" | grep -q "^\.TH GITRLZ 1 \"[^\"]*\" \"gitrl-z $version\""; then
	echo "FAIL: the manual page does not name version $version" >&2
	status=1
fi

for option in $("$binary" --help | awk '/^  -/ {
	for (i = 1; i <= NF; i++) {
		word = $i
		sub(/,$/, "", word)
		if (word !~ /^-/)
			break
		print word
	}
}'); do
	if ! echo "$text" | grep -q -- "\\.B.* $option\\( \\|\$\\)"; then
		echo "FAIL: the manual page does not list $option" >&2
		status=1
	fi
done

[ $status -eq 0 ] && echo "the manual page names version $version and every option of --help"
exit $status
