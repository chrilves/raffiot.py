.PHONY: test clean format check publish docs opt

test: opt
	python -m pytest

clean:
	./scripts/clean.sh

format:
	black `find . -iname "*.py" -type f`

check: format test docs

publish: check clean
	./scripts/opt.sh
	python setup.py sdist
	twine upload dist/*

docs: opt
	rm -r docs/ || true
	cd guide && mdbook build
	pdoc3 --html raffiot -o docs/
	mv docs/raffiot/ docs/api/
	git add docs/

opt:
	./scripts/opt.sh
env: conda/env.yml
	conda env remove -n raffiot -y
	conda env create -f conda/env.yml
