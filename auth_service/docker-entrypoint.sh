#!/bin/sh
set -e

echo "Starting docker-entrypoint.sh..."

if [ -z "$DB_HOST" ] || [ -z "$DB_PORT" ]; then
  echo "Error: DB_HOST and DB_PORT must be set"
  exit 1
fi

if [ -z "$RABBITMQ_HOST" ] || [ -z "$RABBITMQ_PORT" ]; then
  echo "Error: RABBITMQ_HOST and RABBITMQ_PORT must be set"
  exit 1
fi

wait_for_db() {
  echo "Waiting for database at $DB_HOST:$DB_PORT..."
  while ! nc -z "$DB_HOST" "$DB_PORT"; do
    echo "Database is not ready yet..."
    sleep 1
  done
  echo "Database is ready!"
}

wait_for_rabbitmq() {
  echo "Waiting for RabbitMQ at $RABBITMQ_HOST:$RABBITMQ_PORT..."
  while ! nc -z "$RABBITMQ_HOST" "$RABBITMQ_PORT"; do
    echo "RabbitMQ is not ready yet..."
    sleep 1
  done
  echo "RabbitMQ is ready!"
}

wait_for_db
wait_for_rabbitmq

echo "Applying Alembic migrations..."
alembic upgrade head

echo "Starting AuthService..."
exec uvicorn main:app --host 0.0.0.0 --port 8003
