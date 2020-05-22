web: flask db upgrade; gunicorn fal:app
worker: rq worker -u $REDIS_URL