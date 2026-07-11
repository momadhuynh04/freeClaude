import uvicorn
from config.settings import settings

def main():
    print(f"Starting freeClaude proxy on {settings.host}:{settings.port}")
    uvicorn.run(
        "proxy.server:app",
        host=settings.host,
        port=settings.port,
        reload=True
    )

if __name__ == "__main__":
    main()
