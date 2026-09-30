#!/bin/bash

set -euo pipefail

binary=$(readlink -f "$1")
script=$2

if [ ! -f /usr/share/bash-completion/bash_completion ]; then
	echo "SKIP: bash-completion is not installed"
	exit 77
fi

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

mkdir -p "$tmp/completions" "$tmp/work/sub"
cp "$script" "$tmp/completions/gitrlz"
export BASH_COMPLETION_USER_DIR=$tmp
touch "$tmp/work/notes.txt"
cd "$tmp/work"

"$binary" --help | awk '/^  -/ {
	for (i = 1; i <= NF; i++) {
		word = $i
		sub(/,$/, "", word)
		if (word !~ /^-/)
			break
		print word
	}
}' | sort -u > "$tmp/options"

set +eu
. /usr/share/bash-completion/bash_completion

complete_line()
{
	local line=$1 spec

	read -ra COMP_WORDS <<< "$line"
	[[ $line == *" " ]] && COMP_WORDS+=("")
	COMP_CWORD=$((${#COMP_WORDS[@]} - 1))
	COMP_LINE=$line
	COMP_POINT=${#line}
	COMPREPLY=()

	spec=$(complete -p "${COMP_WORDS[0]}" 2>/dev/null) || {
		_completion_loader "${COMP_WORDS[0]}"
		spec=$(complete -p "${COMP_WORDS[0]}")
	}
	spec=${spec##*-F }
	${spec%% *} "${COMP_WORDS[0]}" "${COMP_WORDS[COMP_CWORD]}" \
		"${COMP_WORDS[COMP_CWORD-1]}"
	printf '%s\n' "${COMPREPLY[@]}" | sort -u
}

status=0

expect()
{
	local line=$1 expected=$2 offered

	offered=$(complete_line "$line")
	if [ "$offered" = "$expected" ]; then
		echo "PASS: '$line'"
	else
		echo "FAIL: '$line'" >&2
		diff <(echo "$expected") <(echo "$offered") | sed 's/^/  /' >&2
		status=1
	fi
}

expect "gitrlz -" "$(cat "$tmp/options")"
expect "gitrlz n" "notes.txt"
expect "gitrlz --no-wd s" "sub"

exit $status
