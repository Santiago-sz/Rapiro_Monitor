variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "project_name" {
  type    = string
  default = "rapiro-monitor"
}

variable "alert_email" {
  type        = string
  description = "Email para recibir notificaciones SNS de alertas críticas"
}

variable "ec2_key_name" {
  type        = string
  description = "Nombre del key pair EC2 para acceso SSH (debe existir en AWS)"
}
