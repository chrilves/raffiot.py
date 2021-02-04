#!/bin/sh
set -ex
cp -riav src/ opt/
find opt/ -iname "*.py" -exec ./erase-types.sh {} \;
black `find opt/ -iname "*.py"`
