
import os
import random
import time
import uuid
import logging

from flask import Flask, jsonify, request, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from pythonjsonlogger import jsonlogger

logger = logging.getLogger("app")
handler = logging.StreamHandler()
handler.setFormatter(jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(handler)
logger.setLevel(logging.INFO)

app = Flask(__name__)

REQ_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "route", "status"]
)

REQ_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "route"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
)


@app.before_request
def _start_timer():
    request._start = time.perf_counter()
    request._request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))


@app.after_request
def _record_metrics(resp):
    elapsed = time.perf_counter() - request._start

    REQ_COUNT.labels(
        method=request.method,
        route=request.endpoint or "unknown",
        status=str(resp.status_code)
    ).inc()

    REQ_LATENCY.labels(
        method=request.method,
        route=request.endpoint or "unknown"
    ).observe(elapsed)

    logger.info(
        "request",
        extra={
            "request_id": request._request_id,
            "method": request.method,
            "route": request.endpoint,
            "status": resp.status_code,
            "elapsed_ms": round(elapsed * 1000, 1),
        }
    )
    return resp


@app.route("/orders", methods=["GET"])
def list_orders():
    time.sleep(random.uniform(0.01, 0.150))
    if random.random() < 0.05:
        return jsonify(error="db unreachable"), 500
    return jsonify(orders=[{"id": 1}, {"id": 2}, {"id": 3}])


@app.route("/orders", methods=["POST"])
def place_order():
    time.sleep(random.uniform(0.02, 0.300))
    if random.random() < 0.05:
        return jsonify(error="payment declined"), 500
    return jsonify(order={"id": str(uuid.uuid4())[:8]}), 201


@app.route("/healthz")
def healthz():
    return "ok", 200


@app.route("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))