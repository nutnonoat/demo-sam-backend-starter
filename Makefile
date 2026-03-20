.PHONY: build deploy delete

build:
	sam build --use-container

deploy: build
	sam deploy

deploy-guided: build
	sam deploy --guided

delete:
	sam delete
