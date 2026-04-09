"""Entry point — start the ICT Daily Bias Tool server."""

import os
import sys
import uvicorn

# Ensure working directory is the project root (where run.py lives)
_project_root = os.path.dirname(os.path.abspath(__file__))
os.chdir(_project_root)
sys.path.insert(0, _project_root)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8888))
    uvicorn.run("api.routes:app", host="0.0.0.0", port=port, reload=False)
