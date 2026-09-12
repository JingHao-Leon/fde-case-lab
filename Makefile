.PHONY: test bench data clean

test:
	pytest

data:
	bash scripts/gen_all_data.sh

bench:
	bash scripts/run_all_bench.sh

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + ; \\
	find . -type d -name ".pytest_cache" -exec rm -rf {} + ; \\
	find . -type d -name "data" -path "*/cases/*" -exec rm -rf {} +
