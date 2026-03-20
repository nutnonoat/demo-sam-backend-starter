.PHONY: build deploy delete

build:
	sam build

deploy: build
	sam deploy

deploy-guided: build
	sam deploy --guided

delete:
	sam delete
