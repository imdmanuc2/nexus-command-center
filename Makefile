.PHONY: run restart stop status logs test clean

run:
	PYTHONPATH=. python3 backend/api/server.py

restart:
	./scripts/restart-api.sh

stop:
	sudo systemctl stop nexus-api

status:
	sudo systemctl status nexus-api --no-pager

logs:
	sudo journalctl -u nexus-api -f

test:
	python3 -m py_compile \
	backend/api/server.py \
	backend/modules/*.py \
	backend/core/*.py \
	backend/connectors/*.py

clean:
	find . -name "__pycache__" -type d -exec rm -rf {} +
