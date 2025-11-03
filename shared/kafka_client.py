"""
Kafka client utilities for ERAS services.
"""

import os
import json
from typing import List, Optional
from kafka import KafkaProducer, KafkaConsumer


def create_producer(
    bootstrap_servers: Optional[str] = None,
    value_serializer=None
) -> KafkaProducer:
    """
    Create and return a Kafka producer instance.
    
    Args:
        bootstrap_servers: Kafka broker address (defaults to env var or localhost:9092)
        value_serializer: Serializer function (defaults to JSON)
    
    Returns:
        KafkaProducer instance
    """
    if bootstrap_servers is None:
        bootstrap_servers = os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS", 
            "localhost:9092"
        )
    
    if value_serializer is None:
        value_serializer = lambda v: json.dumps(v).encode('utf-8')
    
    return KafkaProducer(
        bootstrap_servers=bootstrap_servers,
        value_serializer=value_serializer,
        api_version=(0, 10, 1),
        retries=3,
        acks='all',
    )


def create_consumer(
    topics: List[str],
    group_id: Optional[str] = None,
    bootstrap_servers: Optional[str] = None,
    value_deserializer=None,
    auto_offset_reset: str = "earliest"
) -> KafkaConsumer:
    """
    Create and return a Kafka consumer instance.
    
    Args:
        topics: List of topic names to subscribe to
        group_id: Consumer group ID (required for proper offset management)
        bootstrap_servers: Kafka broker address (defaults to env var or localhost:9092)
        value_deserializer: Deserializer function (defaults to JSON)
        auto_offset_reset: What to do when there is no initial offset ('earliest' or 'latest')
    
    Returns:
        KafkaConsumer instance
    """
    if bootstrap_servers is None:
        bootstrap_servers = os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS",
            "localhost:9092"
        )
    
    if value_deserializer is None:
        value_deserializer = lambda m: json.loads(m.decode('utf-8'))
    
    if group_id is None:
        group_id = os.getenv("KAFKA_CONSUMER_GROUP_ID", "eras-default-group")
    
    return KafkaConsumer(
        *topics,
        bootstrap_servers=bootstrap_servers,
        group_id=group_id,
        value_deserializer=value_deserializer,
        auto_offset_reset=auto_offset_reset,
        enable_auto_commit=True,
        api_version=(0, 10, 1),
    )

