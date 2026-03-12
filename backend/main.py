from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return{"message":"server running"}

@app.get("/health")
def health():
    return{"ok":True}

