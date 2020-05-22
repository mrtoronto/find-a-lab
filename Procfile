web: flask db upgrade; gunicorn fal:app --timeout 180
worker: rq worker -u $REDIS_URL