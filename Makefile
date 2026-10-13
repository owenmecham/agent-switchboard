.PHONY: test demo check
test:
	python3 -m unittest discover -s tests -v
demo:
	./scripts/demo.sh
check: test demo
