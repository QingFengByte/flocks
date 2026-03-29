.PHONY: test test-core test-all test-verbose help

help:
	@echo "Flocks 测试命令:"
	@echo "  make test         - 运行核心测试（merge 前必须通过）"
	@echo "  make test-verbose - 运行测试并显示详细输出"
	@echo "  make test-all     - 运行所有测试（包括可能失败的）"

test:
	@python3 scripts/run-tests.py

test-verbose:
	@python3 scripts/run-tests.py --verbose

test-core: test

test-all:
	@uv run pytest tests/ -v --tb=short
