#!/bin/sh
rm -r `find . -type d -and \( -iname ".hypothesis" -or -iname ".pytest_cache" -or -iname "dist" -or -iname "raffiot.egg-info" -or -iname "__pycache__" \)` || true
rm -r raffiot/untyped tests/test_untyped_*.py build/ dist/ mymy-report/ || true
