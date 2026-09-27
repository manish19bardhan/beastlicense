from app import app, init_db

# Initialize the schema when the serverless function is imported.
init_db()
