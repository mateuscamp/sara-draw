# Copiado da skill python-on-rails. `make check` é o portão: rode antes de dizer "pronto".
.PHONY: check rapido fmt test

check:
	scripts/portao.sh

rapido:
	scripts/portao.sh --rapido

fmt:
	uv run --locked ruff format .
	uv run --locked ruff check --fix .

test:
	uv run --locked pytest
