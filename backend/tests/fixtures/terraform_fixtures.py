"""Test fixtures: Terraform configurations for regression and integration tests."""

# ---------------------------------------------------------------------------
# ECS-only architecture (no EC2 instances)
# Simulates aws-samples/amazon-ecs-fullstack-app-terraform patterns
# ---------------------------------------------------------------------------

ECS_ONLY = {
    "main.tf": """
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags = { Name = "main-vpc" }
}

resource "aws_subnet" "public_a" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.1.0/24"
  availability_zone = "us-east-1a"
  tags = { Name = "public-a" }
}

resource "aws_subnet" "private_a" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.2.0/24"
  availability_zone = "us-east-1a"
  tags = { Name = "private-a" }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
}

resource "aws_nat_gateway" "main" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public_a.id
}

resource "aws_eip" "nat" {
  domain = "vpc"
}

resource "aws_security_group" "alb" {
  name        = "alb-sg"
  description = "ALB security group"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "ecs" {
  name        = "ecs-sg"
  description = "ECS tasks security group"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_lb" "app" {
  name               = "app-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = [aws_subnet.public_a.id]
}

resource "aws_lb_target_group" "app" {
  name        = "app-tg"
  port        = 8080
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    path                = "/healthz"
    healthy_threshold   = 3
    unhealthy_threshold = 3
    interval            = 30
    timeout             = 5
  }
}

resource "aws_ecs_cluster" "main" {
  name = "main-cluster"
}

resource "aws_ecs_task_definition" "app" {
  family                   = "app-task"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.ecs_task_exec.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "app"
      image     = "123456789.dkr.ecr.us-east-1.amazonaws.com/app:latest"
      essential = true
      portMappings = [
        { containerPort = 8080, protocol = "tcp" }
      ]
    }
  ])
}

resource "aws_ecs_service" "app" {
  name            = "app-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = 2
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = [aws_subnet.private_a.id]
    security_groups  = [aws_security_group.ecs.id]
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = "app"
    container_port   = 8080
  }
}

resource "aws_iam_role" "ecs_task_exec" {
  name = "ecs-task-exec-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role" "ecs_task" {
  name = "ecs-task-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_s3_bucket" "assets" {
  bucket = "app-assets-bucket"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "assets" {
  bucket = aws_s3_bucket.assets.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "assets" {
  bucket = aws_s3_bucket.assets.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_dynamodb_table" "sessions" {
  name         = "sessions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "session_id"

  attribute {
    name = "session_id"
    type = "S"
  }
}

resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/app"
  retention_in_days = 30
}

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}
data "aws_availability_zones" "available" {
  state = "available"
}
""",
    "variables.tf": """
variable "environment" {
  type    = string
  default = "production"
}

variable "region" {
  type    = string
  default = "us-east-1"
}
""",
}


# ---------------------------------------------------------------------------
# Secure S3 bucket — should NOT trigger encryption or versioning findings
# ---------------------------------------------------------------------------

SECURE_S3 = {
    "main.tf": """
resource "aws_s3_bucket" "data" {
  bucket = "secure-data-bucket"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id
  versioning_configuration {
    status = "Enabled"
  }
}
""",
}


# ---------------------------------------------------------------------------
# Insecure S3 bucket — SHOULD trigger encryption and versioning findings
# ---------------------------------------------------------------------------

INSECURE_S3 = {
    "main.tf": """
resource "aws_s3_bucket" "logs" {
  bucket = "insecure-logs-bucket"
}
""",
}


# ---------------------------------------------------------------------------
# Insecure security group — SHOULD trigger open-world finding
# ---------------------------------------------------------------------------

INSECURE_SG = {
    "main.tf": """
resource "aws_security_group" "open" {
  name   = "open-sg"
  vpc_id = "vpc-12345"

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 3306
    to_port     = 3306
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
""",
}


# ---------------------------------------------------------------------------
# Data sources only — should not produce any billable resources
# ---------------------------------------------------------------------------

DATA_SOURCES_ONLY = {
    "main.tf": """
data "aws_region" "current" {}
data "aws_caller_identity" "current" {}
data "aws_availability_zones" "available" {
  state = "available"
}
data "aws_ami" "latest" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }
}
""",
}


# ---------------------------------------------------------------------------
# Standalone EC2 (should trigger ASG recommendation)
# ---------------------------------------------------------------------------

STANDALONE_EC2 = {
    "main.tf": """
resource "aws_instance" "web" {
  ami           = "ami-12345678"
  instance_type = "t3.medium"

  tags = { Name = "web-server" }
}
""",
}


# ---------------------------------------------------------------------------
# EC2 behind ASG (should NOT trigger ASG recommendation)
# ---------------------------------------------------------------------------

EC2_WITH_ASG = {
    "main.tf": """
resource "aws_launch_template" "web" {
  name          = "web-lt"
  image_id      = "ami-12345678"
  instance_type = "t3.medium"
}

resource "aws_autoscaling_group" "web" {
  name                = "web-asg"
  min_size            = 1
  max_size            = 4
  desired_capacity    = 2
  vpc_zone_identifier = ["subnet-12345"]

  launch_template {
    id = aws_launch_template.web.id
  }
}
""",
}


# ---------------------------------------------------------------------------
# ALB with health check (should NOT trigger health check finding)
# ---------------------------------------------------------------------------

ALB_WITH_HC = {
    "main.tf": """
resource "aws_lb" "app" {
  name               = "app-alb"
  internal           = false
  load_balancer_type = "application"
  subnets            = ["subnet-12345"]
}

resource "aws_lb_target_group" "app" {
  name     = "app-tg"
  port     = 80
  protocol = "HTTP"
  vpc_id   = "vpc-12345"

  health_check {
    path                = "/health"
    healthy_threshold   = 3
    unhealthy_threshold = 3
    interval            = 30
  }
}
""",
}


# ---------------------------------------------------------------------------
# ALB without health check (SHOULD trigger health check finding)
# ---------------------------------------------------------------------------

ALB_NO_HC = {
    "main.tf": """
resource "aws_lb" "app" {
  name               = "app-alb"
  internal           = false
  load_balancer_type = "application"
  subnets            = ["subnet-12345"]
}

resource "aws_lb_target_group" "app" {
  name     = "app-tg"
  port     = 80
  protocol = "HTTP"
  vpc_id   = "vpc-12345"
}
""",
}
