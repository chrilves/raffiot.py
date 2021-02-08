#!/bin/sh
rm -r `find . -type d -and \( -iname ".hypothesis" -or -iname ".pytest_cache" -or -iname "dist" -or -iname "raffiot.egg-info" -or -iname "__pycache__"  -or -iname "untyped" \)` || true
rm -r tests/test_untyped_*.py || true
