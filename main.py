import argparse
import logging.config
from src.api import update_ynab
from src.paths import get_log_config_filepath

logging.config.fileConfig(get_log_config_filepath(), disable_existing_loggers=False)
logger = logging.getLogger(__name__)

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

    parser.add_argument(
        "-r",
        action="store",
        dest="retries",
        required=False,
        default=0,  # No retries
        help=" Number of retries when downloading the n26 transactions",
    )

    parser.add_argument(
        "-d",
        action="store",
        dest="delay",
        required=False,
        default=30 * 60,  # 30 min
        help="Number of seconds delay between retries",
    )

    results = parser.parse_args()

    # Run the update process
    logger.info(f"Requested 💰 YNAB update for account name: {results.account}")
    update_ynab(
        results.account, retries=int(results.retries), delay=int(results.retries)
    )
    logger.info(f"YNAB update performed successfully! 🎉🎊🥳")
