.PHONY: test clean format check publish docs

test:
	python -m pytest

clean:
	rm -r `find . -iname "__pycache__" -type d` || true
	rm -r .hypothesis/ .pytest_cache/ dist/ raffiot.egg-info/ || true

format:
	black `find raffiot/ tests/ -iname "*.py" -type f`

check: format test docs clean

publish: check
	python setup.py sdist
	twine upload dist/*

docs:
	rm -r docs/ || true
	pdoc3 --html raffiot -o docs/
	mv docs/raffiot/* docs/
	rm -r docs/raffiot/
