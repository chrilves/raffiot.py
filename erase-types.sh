#!/bin/sh

FILE="$1"
TMP=$(mktemp)

[ -z "${FILE}" ] && exit 1

strip-hints "${FILE}" | \
grep -vE '(TypeVar|from typing |from typing_extensions|[ \t]*@final|install_requires=.*typing-extensions)' | \
sed 's/^class \(.*\)(Generic\[[^]]*\])/class \1/g;s/Result\[[^]]*\]/Result/g' > "${TMP}"
strip-hints "${TMP}" | sed 's/#\([a-z]\+\):.*/\1: None/g' > "${FILE}"