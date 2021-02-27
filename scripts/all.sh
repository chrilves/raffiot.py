#!/bin/sh
echo "__all__ = ["
cat "$1" | \
grep -oE "^(def|class) [^(:]+" | \
awk '{print "    \"" $2 "\","}'
echo "]"