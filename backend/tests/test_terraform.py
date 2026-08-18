"""Terraform config parser tests."""

from app.services.terraform.parser import parse_terraform_files
from app.services.terraform.registry import classify, provider_label, provider_of

CFG = {
    "main.tf": """
provider "aws" { region = "us-east-1" }

resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
}

resource "aws_subnet" "private_a" {
  vpc_id     = aws_vpc.main.id
  cidr_block = "10.0.1.0/24"
}

resource "aws_instance" "web" {
  instance_type = "t3.medium"
  subnet_id     = aws_subnet.private_a.id
  security_groups = [aws_security_group.web.id]
}

resource "aws_security_group" "web" {
  name = "web"
}
""",
}


def test_parses_resources():
    config = parse_terraform_files(files=CFG, default_region="us-east-1")
    types = {r.resource_type for r in config.resources}
    assert types == {
        "aws_vpc",
        "aws_subnet",
        "aws_instance",
        "aws_security_group",
    }


def test_provider_and_service_classification():
    config = parse_terraform_files(files=CFG)
    web = next(r for r in config.resources if r.resource_type == "aws_instance")
    assert web.provider == "aws"
    assert web.service == "compute"
    assert web.kind == "ec2"


def test_references_discovered():
    config = parse_terraform_files(files=CFG)
    web = next(r for r in config.resources if r.resource_type == "aws_instance")
    assert "aws_subnet.private_a" in web.references
    assert "aws_security_group.web" in web.references


def test_graph_edges():
    config = parse_terraform_files(files=CFG)
    edges = config.graph_edges()
    assert len(edges) >= 3


def test_classify():
    assert classify("aws_instance").kind == "ec2"
    assert classify("aws_db_instance").service == "database"
    assert classify("aws_lambda_function").kind == "lambda"
    assert provider_of("azurerm_resource_group") == "azurerm"
    assert provider_label("azurerm") == "Azure"


def test_count_attribute():
    config = parse_terraform_files(files={"m.tf": 'resource "aws_instance" "x" { count = 3 }'})
    assert config.resources[0].attributes["count"] == 3
