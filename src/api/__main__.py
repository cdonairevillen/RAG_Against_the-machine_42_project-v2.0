"""Run the API: python -m src.api [--host H] [--port P]."""
import argparse


def main() -> None:
    """Start uvicorn with the RAG API."""
    import uvicorn

    from src.api.app import create_app

    parser = argparse.ArgumentParser(description="RAG against the Machine API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run(create_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
