provider "aws" {
  region = "us-east-1"
}

variable "environment" {
  default = "production"
}

variable "instance_count" {
  default = 2
}

terraform {
  backend "s3" {
    bucket = "myapp-tfstate"
    key    = "prod/terraform.tfstate"
    region = "us-east-1"
  }
  required_version = ">= 1.5.0"
}

# --- Networking -----------------------------------------------------------

resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name        = "myapp-vpc"
    Environment = var.environment
  }
}

resource "aws_subnet" "public_a" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "us-east-1a"
  map_public_ip_on_launch = true

  tags = { Name = "myapp-public-a" }
}

resource "aws_subnet" "public_b" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.2.0/24"
  availability_zone       = "us-east-1b"
  map_public_ip_on_launch = true

  tags = { Name = "myapp-public-b" }
}

resource "aws_subnet" "private_a" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.10.0/24"
  availability_zone = "us-east-1a"
  tags              = { Name = "myapp-private-a" }
}

resource "aws_subnet" "private_b" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.11.0/24"
  availability_zone = "us-east-1b"
  tags              = { Name = "myapp-private-b" }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "myapp-public" }
}

resource "aws_route" "public_igw" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.main.id
}

resource "aws_route_table_association" "public_a" {
  subnet_id      = aws_subnet.public_a.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "public_b" {
  subnet_id      = aws_subnet.public_b.id
  route_table_id = aws_route_table.public.id
}

resource "aws_eip" "nat_a" {
  domain = "vpc"
}

resource "aws_eip" "nat_b" {
  domain = "vpc"
}

resource "aws_nat_gateway" "nat_a" {
  allocation_id = aws_eip.nat_a.id
  subnet_id     = aws_subnet.public_a.id
}

resource "aws_nat_gateway" "nat_b" {
  allocation_id = aws_eip.nat_b.id
  subnet_id     = aws_subnet.public_b.id
}

resource "aws_route_table" "private_a" {
  vpc_id = aws_vpc.main.id
}

resource "aws_route_table" "private_b" {
  vpc_id = aws_vpc.main.id
}

resource "aws_route" "private_a_nat" {
  route_table_id         = aws_route_table.private_a.id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.nat_a.id
}

resource "aws_route" "private_b_nat" {
  route_table_id         = aws_route_table.private_b.id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.nat_b.id
}

# --- Compute ----------------------------------------------------------------

resource "aws_security_group" "web" {
  name        = "myapp-web"
  description = "Web tier security group"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 22
    to_port     = 22
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

resource "aws_security_group" "db" {
  name        = "myapp-db"
  description = "Database security group"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.web.id]
  }

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "web" {
  count                       = var.instance_count
  ami                         = "ami-0c55b159cbfafe1f0"
  instance_type               = "m5.4xlarge"
  subnet_id                   = aws_subnet.public_a.id
  associate_public_ip_address = true
  key_name                    = "myapp-prod-key"

  root_block_device {
    volume_type = "gp2"
    volume_size = 100
  }

  tags = {
    Name        = "myapp-web-${count.index}"
    Environment = var.environment
  }
}

resource "aws_instance" "worker" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t3.xlarge"
  subnet_id     = aws_subnet.private_b.id

  tags = {
    Name = "myapp-worker"
  }
}

resource "aws_ebs_volume" "worker_data" {
  availability_zone = "us-east-1b"
  size              = 200
  type              = "gp2"

  tags = { Name = "worker-data" }
}

resource "aws_volume_attachment" "worker_attach" {
  device_name = "/dev/sdf"
  volume_id   = aws_ebs_volume.worker_data.id
  instance_id = aws_instance.worker.id
}

# --- Load balancing ---------------------------------------------------------

resource "aws_lb" "app" {
  name               = "myapp-alb"
  internal           = false
  load_balancer_type = "application"
  subnets            = [aws_subnet.public_a.id, aws_subnet.public_b.id]

  tags = { Name = "myapp-alb" }
}

resource "aws_lb_target_group" "app" {
  name     = "myapp-tg"
  port     = 80
  protocol = "HTTP"
  vpc_id   = aws_vpc.main.id
}

resource "aws_lb_listener" "app_http" {
  load_balancer_arn = aws_lb.app.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}

# --- Database ---------------------------------------------------------------

resource "aws_db_subnet_group" "main" {
  name       = "myapp-db-subnet"
  subnet_ids = [aws_subnet.private_a.id, aws_subnet.private_b.id]
}

resource "aws_db_instance" "postgres" {
  identifier             = "myapp-postgres"
  engine                 = "postgres"
  engine_version         = "16.1"
  instance_class         = "db.m5.xlarge"
  allocated_storage      = 200
  storage_type           = "gp3"
  db_name                = "myapp"
  username               = "myapp"
  password               = "changeme-super-secret"
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.db.id]
  skip_final_snapshot    = true
  multi_az               = false
}

# --- Storage -----------------------------------------------------------------

resource "aws_s3_bucket" "assets" {
  bucket = "myapp-production-assets"
  acl    = "private"

  tags = {
    Name        = "myapp-assets"
    Environment = var.environment
  }
}

resource "aws_s3_bucket_policy" "assets" {
  bucket = aws_s3_bucket.assets.id
}

# --- Serverless ---------------------------------------------------------------

resource "aws_lambda_function" "thumbnailer" {
  filename      = "thumbnailer.zip"
  function_name = "myapp-thumbnailer"
  role          = aws_iam_role.lambda.arn
  handler       = "index.handler"
  runtime       = "nodejs20.x"
  timeout       = 300
  memory_size   = 128
}

resource "aws_iam_role" "lambda" {
  name = "myapp-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/myapp-thumbnailer"
  retention_in_days = 0
}

# --- DNS ---------------------------------------------------------------------

resource "aws_route53_zone" "primary" {
  name = "myapp.example.com"
}

resource "aws_route53_record" "app" {
  zone_id = aws_route53_zone.primary.zone_id
  name    = "app.myapp.example.com"
  type    = "A"

  alias {
    name                   = aws_lb.app.dns_name
    zone_id                = aws_lb.app.zone_id
    evaluate_target_health = true
  }
}
