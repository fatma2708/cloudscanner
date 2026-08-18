resource "aws_instance" "web" {
  count                       = 2
  ami                         = "ami-0c55b159cbfafe1f0"
  instance_type               = "m5.4xlarge"
  subnet_id                   = "subnet-abc123"
  associate_public_ip_address = true

  root_block_device {
    volume_type = "gp2"
    volume_size = 100
  }

  tags = {
    Name = "web-overrides"
  }
}
