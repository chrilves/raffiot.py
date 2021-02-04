#!/bin/sh
rm -r opt || true
rm -r `find . -type d -and \( -iname ".hypothesis" -or -iname ".pytest_cache" -or -iname "dist" -or -iname "raffiot.egg-info" -or -iname "__pycache__"  \)` || true
