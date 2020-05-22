web: flask db upgrade; gunicorn fal:app --timeout 360
worker: rq worker -u $REDIS_URL