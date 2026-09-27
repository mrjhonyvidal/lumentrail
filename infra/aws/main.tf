terraform {
  required_version = ">= 1.7"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
  }
}

variable "region" { type = string }
variable "image" { type = string }
variable "vpc_id" { type = string }
variable "private_subnet_ids" { type = list(string) }
variable "client_security_group_id" {
  type        = string
  description = "Security group allowed to connect to the private task"
}
variable "api_token_secret_arn" { type = string }

provider "aws" { region = var.region }

resource "aws_cloudwatch_log_group" "api" {
  name              = "/lumentrail/api"
  retention_in_days = 7
}

resource "aws_iam_role" "execution" {
  name = "lumentrail-execution"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "secret" {
  name = "lumentrail-secret"
  role = aws_iam_role.execution.id
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = var.api_token_secret_arn }]
  })
}

resource "aws_security_group" "api" {
  name        = "lumentrail-api"
  description = "Private LumenTrail demo"
  vpc_id      = var.vpc_id
  ingress {
    description     = "Approved VPC client only"
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [var.client_security_group_id]
  }
  egress {
    description = "Pull image and write logs through VPC endpoints or NAT"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_ecs_cluster" "api" { name = "lumentrail" }

resource "aws_ecs_task_definition" "api" {
  family                   = "lumentrail-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.execution.arn
  container_definitions = jsonencode([{
    name         = "api"
    image        = var.image
    essential    = true
    portMappings = [{ containerPort = 8080, protocol = "tcp" }]
    environment  = [{ name = "LUMENTRAIL_BEHIND_TLS_PROXY", value = "1" }]
    secrets      = [{ name = "LUMENTRAIL_API_TOKEN", valueFrom = var.api_token_secret_arn }]
    logConfiguration = {
      logDriver = "awslogs"
      options   = { awslogs-group = aws_cloudwatch_log_group.api.name, awslogs-region = var.region, awslogs-stream-prefix = "api" }
    }
  }])
}

resource "aws_ecs_service" "api" {
  name            = "lumentrail-api"
  cluster         = aws_ecs_cluster.api.id
  task_definition = aws_ecs_task_definition.api.arn
  launch_type     = "FARGATE"
  desired_count   = 1
  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.api.id]
    assign_public_ip = false
  }
  depends_on = [aws_iam_role_policy_attachment.execution, aws_iam_role_policy.secret]
}

output "cluster_name" { value = aws_ecs_cluster.api.name }
output "service_name" { value = aws_ecs_service.api.name }
