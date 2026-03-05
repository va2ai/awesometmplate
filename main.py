from app import create_app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    from app.config import ENV, PORT

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=PORT,
        reload=(ENV == "dev"),
        workers=1,
    )
