.PHONY: test clean format check publish

test:
	python -m pytest

clean:
	rm -r `find . -iname "__pycache__" -type d` || true
	rm -r .hypothesis/ .pytest_cache/ dist/ raffiot.egg-info/ || true

format:
	black `find raffiot/ tests/ -iname "*.py" -type f`

check: format test clean

publish: check
	python setup.py sdist
	twine upload dist/*

