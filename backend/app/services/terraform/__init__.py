"""Terraform services public API."""

from app.services.terraform.hcl import HCLAttribute, HCLBlock, parse_hcl, parse_hcl_file
from app.services.terraform.parser import Resource, TerraformConfig, parse_terraform_files
from app.services.terraform.registry import (
    SERVICE_CATEGORIES,
    classify,
    known_resource_type,
    provider_label,
    provider_of,
    resource_icon,
)

__all__ = [
    "HCLBlock",
    "HCLAttribute",
    "parse_hcl",
    "parse_hcl_file",
    "Resource",
    "TerraformConfig",
    "parse_terraform_files",
    "classify",
    "provider_label",
    "provider_of",
    "known_resource_type",
    "resource_icon",
    "SERVICE_CATEGORIES",
]
