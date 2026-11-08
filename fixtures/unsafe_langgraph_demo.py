"""Intentionally insecure example. Never import or execute as a real workflow."""

def demo(graph, publisher):
    graph.add_edge("draft", "check")
    graph.add_edge("check", "draft")  # guarded only by prompt (bad)
    graph.add_edge("check", "publish")
    publisher.publish("demo")  # no idempotency check


def another_issue():
    while True:
        pass  # unsafe busy loop, do NOT call
