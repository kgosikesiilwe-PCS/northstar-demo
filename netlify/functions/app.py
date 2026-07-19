"""
Netlify Functions adapter for the NorthStar FastAPI app.
Uses Mangum to bridge AWS Lambda / Netlify Functions with ASGI.
"""
from mangum import Mangum
from app.main import app

handler = Mangum(app, lifespan="on")
