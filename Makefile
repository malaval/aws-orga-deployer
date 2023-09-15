format:
	isort src/ tests/
	black --preview src/ tests/

pylint:
	pylint src/ tests/

mypy:
	mypy src/

test:
	pytest tests/
	
coverage:
	coverage run --source src/ -m pytest -s tests/
	coverage report -m
	coverage html

clean:
	rm -fr dist/
	rm -f .coverage
	rm -f coverage.xml
	rm -fr htmlcov/
	rm -fr .pytest_cache
	rm -fr .mypy_cache
	rm -fr docs/.jekyll-cache
	rm -fr docs/_site
	find . -path ./venv -prune -false -o -name '*.egg-info' -exec rm -fr {} +
	find . -path ./venv -prune -false -o -name '*.egg' -exec rm -fr {} +
	find . -path ./venv -prune -false -o -name '*.pyc' -exec rm -f {} +
	find . -path ./venv -prune -false -o -name '*.pyo' -exec rm -f {} +
	find . -path ./venv -prune -false -o -name '*~' -exec rm -f {} +
	find . -path ./venv -prune -false -o -name '__pycache__' -exec rm -fr {} +

build:
	python -m build

upload:
	python -m twine upload dist/*

install:
	pip3 install -e .