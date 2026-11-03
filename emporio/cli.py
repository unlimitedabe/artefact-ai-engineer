"""Command-line entry points for loading data and chatting."""

import argparse
import getpass
import json

from emporio.bootstrap import create_agent, resources
from emporio.config import Settings
from emporio.ingest import DataError, build_database
from emporio.provider import ProviderError
from emporio.session import Verification


def main():
    parser = argparse.ArgumentParser(description="Empório da Música customer-service prototype")
    parser.add_argument("command", choices=["load", "chat"])
    parser.add_argument("--demo", action="store_true", help="Limited offline mode; no LLM calls")
    args = parser.parse_args()
    try:
        settings = Settings.from_env()
        if args.demo:
            settings.mode = "demo"
        if args.command == "load":
            print(json.dumps(build_database(settings.data_dir, settings.database_path), indent=2))
            return
        store, policies = resources(settings)
        verification = Verification()
        agent = create_agent(settings, store, policies)
        print(f"Empório da Música [{settings.mode}]. /verify, /logout, /clear, /quit")
        while True:
            try:
                message = input("Você: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if message == "/quit":
                break
            if message in {"/verify", "/logout", "/clear"}:
                if message == "/verify":
                    verified = verification.verify(
                        store, input("E-mail: "), getpass.getpass("Telefone: ")
                    )
                    print(
                        "Cliente verificado."
                        if verified
                        else "Não foi possível verificar os dados."
                    )
                elif message == "/logout":
                    verification.customer_id = None
                agent = create_agent(settings, store, policies, verification.customer_id)
                continue
            print("Empório:", agent.reply(message).answer)
    except (ProviderError, DataError, ValueError, OSError) as exc:
        parser.exit(
            1, f"Unable to start ({type(exc).__name__}). Check .env and run emporio load.\n"
        )


if __name__ == "__main__":
    main()
