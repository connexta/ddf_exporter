IMAGE_NAME=connexta/ddf_exporter
GIT_BRANCH:=$(shell git symbolic-ref HEAD | sed -e 's,.*/\(.*\),\1,' 2>/dev/null)
ifneq ($(GIT_BRANCH), master)
	IMAGE_TAG=$(GIT_BRANCH)
else
	IMAGE_TAG=latest
endif

.PHONY: help
help: ## Display help.
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)```

.PHONY: image
image: ## Create the docker image
	docker build -t $(IMAGE_NAME):$(IMAGE_TAG) -f Dockerfile .

.PHONY: push
push: image ## Push docker image
	docker push $(IMAGE_NAME):$(IMAGE_TAG)