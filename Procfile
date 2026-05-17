release: python manage.py migrate --noinput && python manage.py collectstatic --noinput
web: gunicorn parking_belgium.wsgi --bind 0.0.0.0:$PORT --workers 3 --timeout 60 --access-logfile - --error-logfile -
