#!/bin/sh
echo "__all__ = ["
cat "$1" | \
grep -oE "^((def|class) [^(:]+|[a-zA-Z0-9_]+:)" | \
grep -v "TypeVar" | \
sed "s/^\(class\|def\) //g;s/:$//g" | \
awk '{print "    \"" $1 "\","}'
echo "]"