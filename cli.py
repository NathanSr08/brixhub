import asyncio
import argparse
from app.db.clickhouse import init_clients, close_clients
from app.services.key_service import KeyService
from app.repositories import keys_repo
from starlette.concurrency import run_in_threadpool

async def run_cli():
    parser = argparse.ArgumentParser(prog="brixhub-cli", description="Gestionnaire des Clés API BrixHub")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # Commande create
    c = sub.add_parser("create", help="Créer une nouvelle clé API")
    c.add_argument("--label", required=True, help="Nom ou libellé du client")
    c.add_argument("--email", required=True, help="Email du propriétaire")
    c.add_argument("--plan", default="free", choices=["free", "pro", "business", "unlimited"], help="Plan tarifaire")

    # Commande list
    sub.add_parser("list", help="Lister les clés existantes")

    # Commande revoke
    r = sub.add_parser("revoke", help="Révoquer une clé API")
    r.add_argument("--key-id", required=True, help="ID de la clé (ex: a1b2c3d4e5f60718)")

    args = parser.parse_args()
    await init_clients()

    svc = KeyService()

    try:
        if args.cmd == "create":
            res = await svc.create(args.label, args.email, args.plan)
            print("\n=======================================================")
            print(" Clé API créée avec succès !")
            print("=======================================================")
            print(f"Key ID      : {res['key_id']}")
            print(f"Label       : {res['label']}")
            print(f"Email       : {res['owner_email']}")
            print(f"Plan        : {res['plan']} ({res['quota_per_day']} req/jour)")
            print(f"Preview     : {res['preview']}")
            print("\nRAW API KEY (À COPIER MAINTENANT, NE SERA PLUS AFFICHÉE) :")
            print(f"  {res['key']}")
            print("=======================================================\n")

        elif args.cmd == "list":
            rows = await run_in_threadpool(keys_repo.list_all)
            print("\n{:<18} {:<18} {:<12} {:<20} {:<8}".format("KEY_ID", "PREVIEW", "PLAN", "EMAIL", "ACTIVE"))
            print("-" * 80)
            for r in rows:
                print("{:<18} {:<18} {:<12} {:<20} {:<8}".format(
                    r["key_id"], r["preview"], r["plan"], r["owner_email"][:18], str(bool(r["is_active"]))
                ))
            print()

        elif args.cmd == "revoke":
            success = await svc.revoke(args.key_id)
            if success:
                print(f"\n Clé {args.key_id} révoquée avec succès.\n")
            else:
                print(f"\n Erreur : clé {args.key_id} introuvable.\n")
    finally:
        await close_clients()

if __name__ == "__main__":
    asyncio.run(run_cli())
