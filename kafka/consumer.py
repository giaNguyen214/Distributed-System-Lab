from confluent_kafka import Consumer

conf = {
    'bootstrap.servers': 'kafka-0:9092,kafka-1:9092',
    'group.id': 'test-group',
    'auto.offset.reset': 'earliest'
}

consumer = Consumer(conf)
consumer.subscribe(['test'])

try:
    while True:
        msg = consumer.poll(1.0)
        if msg is None:
            continue
        if msg.error():
            print("Error:", msg.error())
            break
        print("Received:", msg.value().decode())
except KeyboardInterrupt:
    pass
finally:
    consumer.close()
