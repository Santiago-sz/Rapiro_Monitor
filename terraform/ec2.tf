data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_security_group" "ec2" {
  name        = "${var.project_name}-ec2-sg"
  description = "Rapiro processing server"

  ingress {
    description = "SSH"
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

resource "aws_iam_role" "ec2" {
  name = "${var.project_name}-ec2-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "ec2_iot" {
  name = "${var.project_name}-ec2-iot-policy"
  role = aws_iam_role.ec2.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["iot:Connect"]
        Resource = "arn:aws:iot:${var.aws_region}:*:client/${var.project_name}-ec2"
      },
      {
        Effect = "Allow"
        Action = ["iot:Subscribe"]
        Resource = "arn:aws:iot:${var.aws_region}:*:topicfilter/rapiro/frames"
      },
      {
        Effect = "Allow"
        Action = ["iot:Receive"]
        Resource = "arn:aws:iot:${var.aws_region}:*:topic/rapiro/frames"
      },
      {
        Effect = "Allow"
        Action = ["iot:Publish"]
        Resource = [
          "arn:aws:iot:${var.aws_region}:*:topic/rapiro/commands",
          "arn:aws:iot:${var.aws_region}:*:topic/rapiro/events/*"
        ]
      }
    ]
  })
}

resource "aws_iam_instance_profile" "ec2" {
  name = "${var.project_name}-ec2-profile"
  role = aws_iam_role.ec2.name
}

resource "aws_instance" "rapiro_server" {
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = "t3.small"
  key_name                    = var.ec2_key_name
  iam_instance_profile        = aws_iam_instance_profile.ec2.name
  vpc_security_group_ids      = [aws_security_group.ec2.id]
  associate_public_ip_address = true

  user_data = <<-EOF
    #!/bin/bash
    apt-get update -y
    apt-get install -y python3-pip python3-venv postgresql postgresql-contrib
    systemctl enable postgresql
    systemctl start postgresql
    pip3 install \
      awsiotsdk \
      opencv-python-headless \
      tensorflow-cpu \
      psycopg2-binary \
      numpy
  EOF

  tags = {
    Name    = "${var.project_name}-server"
    Project = var.project_name
  }
}
