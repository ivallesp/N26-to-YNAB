import argparse


from src.api import update_ynab

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="N26 to YNAB bridge. Run the program to download the transactions "
        "from the N26 account and upload the into the YNAB budget account. "
        "Example: python main.py -a my_account_name"
    )

    parser.add_argument(
        "-a",
        action="store",
        dest="account",
        required=True,
        help="Name of the account to update. Has to be defined in config/n26.toml",
    )

    results = parser.parse_args()

    # Run the update process
    update_ynab(results.account)
