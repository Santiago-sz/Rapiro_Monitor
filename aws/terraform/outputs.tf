output "iot_endpoint_hint" {
  description = "Obtener el endpoint con: aws iot describe-endpoint --endpoint-type iot:Data-ATS"
  value       = "Ejecutar: aws iot describe-endpoint --endpoint-type iot:Data-ATS"
}

output "ec2_public_ip" {
  description = "IP pública del servidor EC2 — usala para SSH y para configurar el RPi"
  value       = aws_instance.rapiro_server.public_ip
}

output "ec2_ssh_command" {
  description = "Comando para conectarte al EC2"
  value       = "ssh -i <tu-key.pem> ubuntu@${aws_instance.rapiro_server.public_ip}"
}

output "iot_thing_arn" {
  value = aws_iot_thing.rapiro.arn
}

output "certificate_pem" {
  description = "Guardar como certs/device.pem.crt en el Raspberry Pi"
  value       = aws_iot_certificate.rapiro.certificate_pem
  sensitive   = true
}

output "private_key" {
  description = "Guardar como certs/private.pem.key en el Raspberry Pi"
  value       = aws_iot_certificate.rapiro.private_key
  sensitive   = true
}

output "dynamodb_table_name" {
  value = aws_dynamodb_table.events.name
}

output "sns_topic_arn" {
  value = aws_sns_topic.alerts.arn
}

output "lambda_function_name" {
  value = aws_lambda_function.alert_handler.function_name
}
