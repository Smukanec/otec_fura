import os

API_PORT = 8090
# Use an environment variable for the secret key. Provide a development default
# so the application can run without explicit configuration.
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
