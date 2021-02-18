#!/bin/sh
set -ex
rm -frv raffiot/untyped/ tests/test_untyped_* || true
cp -riav raffiot/ raffiot/untyped/ || true
for f in `ls -1 tests/*.py`; do cp -v "${f}" "tests/test_untyped$(echo ${f} | grep -Eo "_[^.]*.")py"; done
find raffiot/untyped/ -iname "*.py" -exec ./scripts/erase-types.sh {} \;
find tests/ -iname "test_untyped_*.py" -exec ./scripts/erase-types.sh {} \;
black `find . -iname "*.py"`
