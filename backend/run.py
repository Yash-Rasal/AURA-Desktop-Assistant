import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import uvicorn
from config import settings

if __name__ == "__main__":
    uvicorn.run(
        "api.main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=False,
    )
