"""Entry point — start the ICT Daily Bias Tool server."""

import os
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8888))
    uvicorn.run("api.routes:app", host="0.0.0.0", port=port, reload=False)
