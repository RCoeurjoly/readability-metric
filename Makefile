.PHONY: clean lint test nix-check process-downloads

DOWNLOADS ?= $(HOME)/Downloads
OUTPUT ?= results/downloads-readability.jsonl
JOBS ?= 1
SAMPLES ?= 10
MAX_SIZE_MB ?= 10

clean:
	rm -rf .pytest_cache __pycache__ result

lint:
	ruff check .

test:
	python -m unittest -v

nix-check:
	nix flake check

process-downloads:
	mkdir -p $(dir $(OUTPUT))
	nix run . -- --corpus-dir "$(DOWNLOADS)" --output "$(OUTPUT)" --jobs "$(JOBS)" --samples "$(SAMPLES)" --max-size-mb "$(MAX_SIZE_MB)"
