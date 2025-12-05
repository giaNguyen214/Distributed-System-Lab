from confluent_kafka import Producer

conf = {
    'bootstrap.servers': 'kafka-0:9092,kafka-1:9092'
}

producer = Producer(conf)

for i in range(10):
    message = f"Hello Kafka {i}"
    producer.produce('test', message.encode())
    print("Sent:", message)
    producer.poll(0)

producer.flush()
