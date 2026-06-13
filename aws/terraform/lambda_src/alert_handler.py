import json
import os
import time
import boto3

dynamodb = boto3.resource("dynamodb")
sns = boto3.client("sns")

TABLE_NAME = os.environ["DYNAMODB_TABLE"]
SNS_TOPIC_ARN = os.environ["SNS_TOPIC_ARN"]

NOTIFY_LEVELS = {"warning", "critical"}


def handler(event, context):
    table = dynamodb.Table(TABLE_NAME)

    item = {
        "event_id": event.get("event_id", "unknown"),
        "captured_at": event.get("captured_at", ""),
        "hour_of_day": event.get("hour_of_day", 0),
        "motion_detected": event.get("motion_detected", False),
        "motion_confidence": str(event.get("motion_confidence", 0)),
        "face_detected": event.get("face_detected", False),
        "light_percent": str(event.get("light_percent", 0)),
        "alert_level": event.get("alert_level", "none"),
        "anomaly_score": str(event.get("anomaly_score", 0)),
        "rapiro_command": event.get("rapiro_command", ""),
        "expires_at": int(time.time()) + 30 * 24 * 3600,  # TTL 30 días
    }
    table.put_item(Item=item)

    alert_level = event.get("alert_level", "none")
    if alert_level in NOTIFY_LEVELS:
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=f"[Rapiro] Alerta {alert_level.upper()} detectada",
            Message=json.dumps(event, indent=2, ensure_ascii=False),
        )

    return {"statusCode": 200, "body": "ok"}
