import os 
from urllib.parse import urlparse, parse_qs

import requests
from fastapi import FastAPI, HTTPException, Query
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title = "YouTube API Example")

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")


