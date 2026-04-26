import argparse
import json

from env_loader import load_repo_env
from onyx_runtime import ensure_onyx_running, onyx_status


def main():
    load_repo_env()
    parser = argparse.ArgumentParser(description="Check or bootstrap the local Onyx Docker stack.")
    parser.add_argument("--ensure", action="store_true", help="Try to start Docker Desktop and Onyx if needed.")
    args = parser.parse_args()

    payload = ensure_onyx_running() if args.ensure else onyx_status()
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
