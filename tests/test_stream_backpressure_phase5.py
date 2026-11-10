from gex.serve.stream import BackpressuredPublisher


def test_publish_subscribe_and_backpressure_drop_oldest():
    bus = BackpressuredPublisher(maxsize=2)
    sub = bus.subscribe()
    assert bus.publish({"n": 1}) == 1
    assert bus.publish({"n": 2}) == 1
    assert bus.publish({"n": 3}) == 1  # drops oldest (1), keeps 2,3
    assert bus.get(sub, timeout=0.01) == {"n": 2}
    assert bus.get(sub, timeout=0.01) == {"n": 3}
    assert bus.get(sub, timeout=0.01) is None
    bus.unsubscribe(sub)
    assert bus.publish({"n": 4}) == 0


def test_topic_filtering():
    bus = BackpressuredPublisher(maxsize=10)
    a = bus.subscribe(topic="a")
    all_sub = bus.subscribe(topic=None)
    bus.publish({"v": 1}, topic="a")
    bus.publish({"v": 2}, topic="b")
    assert bus.get(a, timeout=0.01) == {"v": 1}
    assert bus.get(a, timeout=0.01) is None
    assert bus.get(all_sub, timeout=0.01) == {"v": 1}
    assert bus.get(all_sub, timeout=0.01) == {"v": 2}
    bus.unsubscribe(a)
    bus.unsubscribe(all_sub)
