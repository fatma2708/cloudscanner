"""Pricing engine tests."""

from app.services.pricing.catalog import get_ec2
from app.services.pricing.engine import estimate_resource_cost
from app.services.terraform.parser import parse_terraform_files


def test_ec2_estimate():
    config = parse_terraform_files(
        files={"m.tf": 'resource "aws_instance" "x" { instance_type = "t3.medium" }'}
    )
    cost = estimate_resource_cost(config.resources[0])
    assert cost > 20
    assert cost < 60


def test_spot_discount():
    config = parse_terraform_files(
        files={
            "m.tf": 'resource "aws_instance" "x" { instance_type = "t3.medium" instance_market_options {} }'
        }
    )
    on_demand = estimate_resource_cost(config.resources[0])
    assert on_demand < 20


def test_rds_estimate():
    config = parse_terraform_files(
        files={"m.tf": 'resource "aws_db_instance" "db" { instance_class = "db.t3.medium" }'}
    )
    cost = estimate_resource_cost(config.resources[0])
    assert cost > 40


def test_nat_estimate():
    config = parse_terraform_files(files={"m.tf": 'resource "aws_nat_gateway" "n" {}'})
    cost = estimate_resource_cost(config.resources[0])
    assert cost > 30


def test_s3_estimate():
    config = parse_terraform_files(files={"m.tf": 'resource "aws_s3_bucket" "b" {}'})
    cost = estimate_resource_cost(config.resources[0])
    assert cost > 0


def test_catalog_lookup():
    assert get_ec2("t3.micro").vcpu == 2
    assert get_ec2("M5.XLARGE") is not None
    assert get_ec2("nope-42") is None
