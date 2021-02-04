.PHONY: test-opt test-src clean format check publish docs opt

test-opt: opt
	cd opt/ && python -m pytest

test-src:
	cd src/ && python -m pytest

clean:
	./clean.sh

format:
	black `find . -iname "*.py" -type f`

check: format test-src clean test-opt docs

publish: check
	./clean.sh
	./opt.sh
	cd opt/ && python setup.py sdist
	cd opt/ && twine upload dist/*

docs:
	rm -r docs/ || true
	cd src/ && pdoc3 --html raffiot -o ../docs/
	mv docs/raffiot/* docs/
	rm -r docs/raffiot/

opt: clean
	./opt.sh
