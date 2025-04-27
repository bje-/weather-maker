all: venv

# define the name of the virtual environment directory
VENV=pyenv

$(VENV)/bin/activate: requirements.txt
	python3 -m venv $(VENV)
	./$(VENV)/bin/pip install -r requirements.txt

# env is a shortcut target
venv: $(VENV)/bin/activate

check:
	flake8 *.py
	pylint *.py
	pydocstyle *.py
