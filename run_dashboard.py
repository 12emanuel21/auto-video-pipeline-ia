"""Quick startup runner for Stoic Studio Dashboard."""

import sys
import uvicorn

if __name__ == "__main__":
    print("=" * 70)
    print(" INICIANDO STOIC STUDIO CONTROL DASHBOARD")
    print(" URL: http://localhost:8855 (0.0.0.0:8855  5678)")
    print("=" * 70)
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=5678,
        reload=True,
    )
