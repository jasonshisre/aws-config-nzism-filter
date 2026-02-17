STACK_NAME ?= nzism-config-filter
REGION ?= ap-southeast-2
WAF_STACK_NAME ?= $(STACK_NAME)-waf

define get_bucket
$(shell aws cloudformation describe-stacks \
	--stack-name $(STACK_NAME) --region $(REGION) \
	--query 'Stacks[0].Outputs[?OutputKey==`FrontendBucketName`].OutputValue' \
	--output text 2>/dev/null)
endef

define get_waf_arn
$(shell aws cloudformation describe-stacks \
	--stack-name $(WAF_STACK_NAME) --region us-east-1 \
	--query 'Stacks[0].Outputs[?OutputKey==`WafWebAclArn`].OutputValue' \
	--output text 2>/dev/null)
endef

.PHONY: build-frontend build-backend deploy deploy-waf deploy-all clean destroy destroy-waf destroy-all

build-frontend:
	cd frontend && npm ci && npm run build

build-backend:
	cd backend && pip install -r requirements.txt -t .package/
	cp -r backend/src backend/.package/

deploy-waf:
	@echo "Deploying WAF stack to us-east-1..."
	aws cloudformation deploy \
		--template-file waf-template.yaml \
		--stack-name $(WAF_STACK_NAME) \
		--region us-east-1 \
		--parameter-overrides StackName=$(STACK_NAME) \
		--no-fail-on-empty-changeset
	@echo "WAF stack deployed!"
	@aws cloudformation describe-stacks \
		--stack-name $(WAF_STACK_NAME) --region us-east-1 \
		--query 'Stacks[0].Outputs' --output table

deploy: build-frontend build-backend
	sam build
	$(eval WAF_ARN := $(call get_waf_arn))
	sam deploy \
		--stack-name $(STACK_NAME) \
		--region $(REGION) \
		--resolve-s3 \
		--capabilities CAPABILITY_IAM \
		--no-confirm-changeset \
		--no-fail-on-empty-changeset \
		$(if $(WAF_ARN),--parameter-overrides CloudFrontWafArn=$(WAF_ARN),)
	@echo "Uploading frontend assets..."
	$(eval FRONTEND_BUCKET := $(call get_bucket))
	aws s3 sync frontend/dist s3://$(FRONTEND_BUCKET) --delete --region $(REGION)
	@echo "Deployment complete!"
	@aws cloudformation describe-stacks \
		--stack-name $(STACK_NAME) --region $(REGION) \
		--query 'Stacks[0].Outputs' --output table

deploy-all: deploy-waf deploy
	@echo "Full deployment complete (WAF + Application)!"

clean:
	rm -rf frontend/dist frontend/node_modules
	rm -rf backend/.package
	rm -rf .aws-sam

destroy:
	$(eval FRONTEND_BUCKET := $(call get_bucket))
	aws s3 rm s3://$(FRONTEND_BUCKET) --recursive --region $(REGION) 2>/dev/null || true
	sam delete --stack-name $(STACK_NAME) --region $(REGION) --no-prompts

destroy-waf:
	aws cloudformation delete-stack --stack-name $(WAF_STACK_NAME) --region us-east-1
	@echo "Waiting for WAF stack deletion..."
	aws cloudformation wait stack-delete-complete --stack-name $(WAF_STACK_NAME) --region us-east-1

destroy-all: destroy destroy-waf
	@echo "Full cleanup complete!"
