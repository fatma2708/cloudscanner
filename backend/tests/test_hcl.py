"""HCL parser unit tests."""

import pytest

from app.services.terraform.hcl import ParseError, parse_hcl

SAMPLE = """
# comment
resource "aws_instance" "web" {
  ami           = "ami-123"
  instance_type = "t3.medium"
  count         = 2
  tags = {
    Name = "web"
  }
  root_block_device {
    volume_type = "gp3"
  }
}
"""

SAMPLE_HEREDOC = """
variable "script" {
  default = <<-EOF
    hello world
  EOF
}
"""


def test_parse_top_level_block():
    blocks = parse_hcl(SAMPLE)
    assert len(blocks) == 1
    block = blocks[0]
    assert block.type == "resource"
    assert block.labels == ["aws_instance", "web"]


def test_parse_attributes():
    blocks = parse_hcl(SAMPLE)
    block = blocks[0]
    assert block.attr("instance_type").value == "t3.medium"
    assert block.attr("count").value == 2
    assert block.attr("ami").value == "ami-123"


def test_parse_nested_block():
    blocks = parse_hcl(SAMPLE)
    nested = blocks[0].children("root_block_device")
    assert len(nested) == 1
    assert nested[0].attr("volume_type").value == "gp3"


def test_parse_map_value():
    blocks = parse_hcl(SAMPLE)
    tags = blocks[0].attr("tags").value
    assert tags == {"Name": "web"}


def test_parse_heredoc():
    blocks = parse_hcl(SAMPLE_HEREDOC)
    assert blocks[0].type == "variable"
    assert "hello world" in blocks[0].attr("default").value


def test_parse_malformed_does_not_raise():
    blocks = parse_hcl("resource aws_instance { this is ( broken ]}")
    assert isinstance(blocks, list)


def test_strict_parse_rejects_unterminated_block_without_spinning():
    with pytest.raises(ParseError):
        parse_hcl('resource "aws_instance" "broken"', strict=True)


def test_interpolation_preserved():
    blocks = parse_hcl("""resource "aws_instance" "x" {
  subnet_id = aws_subnet.private.id
}""")
    assert blocks[0].attr("subnet_id").value == "aws_subnet.private.id"


def test_line_numbers():
    blocks = parse_hcl('provider "aws" {\n}\nresource "a" "b" {\n}\n')
    res = [b for b in blocks if b.type == "resource"][0]
    assert res.line == 3
