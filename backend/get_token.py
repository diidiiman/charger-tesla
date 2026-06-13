import asyncio
from app.security import make_session_token

def main():
    print(make_session_token(1))

if __name__ == "__main__":
    main()