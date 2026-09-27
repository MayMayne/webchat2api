from __future__ import annotations

import os

import uvicorn
from api import create_app

app = create_app()

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "83"))
    uvicorn.run(app, host=host, port=port, access_log=False, log_level="info")
