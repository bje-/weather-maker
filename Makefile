check:
	flake8 *.py
	pylint *.py
	pylama *.py
	pylava *.py
	vulture --min-confidence=100 *.py
	bandit -q -s B101 *.py
	pydocstyle *.py
