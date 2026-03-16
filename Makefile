SHELL := /usr/bin/env bash

.PHONY: run run-backend run-frontend

run:
	@set -m; \
	trap 'kill 0' INT TERM EXIT; \
	( \
		cd backend; \
		if command -v poetry >/dev/null 2>&1; then \
			poetry run uvicorn src.main:app --reload; \
		elif [ -x "venv/Scripts/python.exe" ]; then \
			venv/Scripts/python.exe -m uvicorn src.main:app --reload; \
		elif [ -x "../.venv/Scripts/python.exe" ]; then \
			../.venv/Scripts/python.exe -m uvicorn src.main:app --reload; \
		elif [ -x "venv/bin/python" ]; then \
			venv/bin/python -m uvicorn src.main:app --reload; \
		elif [ -x "../.venv/bin/python" ]; then \
			../.venv/bin/python -m uvicorn src.main:app --reload; \
		else \
			echo "No backend Python environment found. Install Poetry or create backend/venv or root .venv."; \
			exit 1; \
		fi \
	) & \
	( cd frontend && npm run dev -- --strictPort=false --port 1420 ) & \
	wait -n; \
	status=$$?; \
	kill 0 >/dev/null 2>&1 || true; \
	wait || true; \
	exit $$status

run-backend:
	@cd backend; \
	if command -v poetry >/dev/null 2>&1; then \
		poetry run uvicorn src.main:app --reload; \
	elif [ -x "venv/Scripts/python.exe" ]; then \
		venv/Scripts/python.exe -m uvicorn src.main:app --reload; \
	elif [ -x "../.venv/Scripts/python.exe" ]; then \
		../.venv/Scripts/python.exe -m uvicorn src.main:app --reload; \
	elif [ -x "venv/bin/python" ]; then \
		venv/bin/python -m uvicorn src.main:app --reload; \
	elif [ -x "../.venv/bin/python" ]; then \
		../.venv/bin/python -m uvicorn src.main:app --reload; \
	else \
		echo "No backend Python environment found. Install Poetry or create backend/venv or root .venv."; \
		exit 1; \
	fi

run-frontend:
	cd frontend && npm run dev -- --strictPort=false --port 1420
