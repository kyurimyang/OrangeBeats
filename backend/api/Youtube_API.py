import os 
import resource
from urllib.parse import uriparse, parse_qs

import requests
from fastapi import FASTAPI, HTTPException, Query
from dotenv import load_dotenv

load_dotenv()

app = FASTAPI(title = "YouTube API Example")

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
Y
