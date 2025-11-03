"""Kafka producer and consumer utilities."""
import json
import os
from typing import Optional, Callable
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError


KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")


def create_producer() -> KafkaProducer:
    """Create a Kafka producer."""
    return KafkaProducer(
        bootstrap_servers=KAFKA_BROKER,
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        key_serializer=lambda k: k.encode('utf-8') if k else None
    )


def publish_message(producer: KafkaProducer, topic: str, message: dict, key: Optional[str] = None):
    """Publish a message to a Kafka topic."""
    try:
        future = producer.send(topic, value=message, key=key)
        future.get(timeout=10)
    except KafkaError as e:
        print(f"Error publishing to {topic}: {e}")
        raise


def create_consumer(topic: str, group_id: str) -> KafkaConsumer:
    """Create a Kafka consumer."""
    return KafkaConsumer(
        topic,
        bootstrap_servers=KAFKA_BROKER,
        group_id=group_id,
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        auto_offset_reset='earliest',
        enable_auto_commit=True
    )


def consume_messages(consumer: KafkaConsumer, callback: Callable[[dict], None]):
    """Consume messages from a topic and call callback for each."""
    for message in consumer:
        try:
            callback(message.value)
        except Exception as e:
            print(f"Error processing message: {e}")

