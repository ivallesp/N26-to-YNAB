import logging
import tenacity
import time
import ynab_client

import n26.api
import n26.config

from datetime import datetime

from src.paths import get_n26_token_data_filepath
from src.config import load_ynab_config, get_n26_account_config
from src.exceptions import (
    BudgetNotFoundError,
    AccountNotFoundError,
    AuthenticationTimeoutError,
)

logger = logging.getLogger(__name__)


def update_ynab(account_name):
    ynab_conf = load_ynab_config()["ynab"]
    n26_conf = get_n26_account_config(account_name)
    ynab_account_name = n26_conf["ynab_account"]
    budget_name = ynab_conf["budget_name"]
    transactions = download_n26_transactions(account_name)
    upload_n26_transactions_to_ynab(
        transactions_n26=transactions,
        budget_name=budget_name,
        account_name=ynab_account_name,
    )


def download_n26_transactions(account_name):
    logger.info(f"Retrieving N26 transactions from the account '{account_name}'...")
    # Get access
    client = get_n26_client(account_name)
    # Get N26 transactions
    watchdog = 5  # trials before failure
    delay = 30  # minutes
    while watchdog >= 0:  # If there are still trials left...
        logger.info("Requesting transfers to the N26 API...")
        try:
            # Try to call the API. This will potentially show a two-factor notification
            # in the phone of the user. In that case, if the access is not granted, the
            # api client will timeout with a tenacy.RetryError exception
    transactions = client.get_transactions(limit=0)
            break  # Exit the loop on success
        except tenacity.RetryError:
            logger.error("No app authentication provided! Waiting 30 min...")
            if watchdog <= 0:
                raise AuthenticationTimeoutError("two-factor auth failed! 😡")
            watchdog -= 1
            time.sleep(60 * delay)

    logger.info(f"{len(transactions)} transactions have been retrieved!")
    return transactions


def upload_n26_transactions_to_ynab(transactions_n26, budget_name, account_name):
    logger.info(
        f"Requested {len(transactions_n26)} transaction updates to budget "
        f"'{budget_name}' and account '{account_name}'"
    )
    # Get an instance of YNAB and N26 APIs
    ynab_cli = get_ynab_client()

    # Find the existing budgets and its respective IDs in YNAB
    ynab_budget_id_map = get_ynab_budget_id_mapping(ynab_cli)
    # If the budget name is not among the budget names retrieved, raise an exception
    if budget_name not in ynab_budget_id_map:
        budgets = list(ynab_budget_id_map.keys())
        budgets_str = "'" + "', '".join(budgets) + "'"
        raise BudgetNotFoundError(
            f"Budget named '{budget_name}' not found, available ones: {budgets_str}"
        )
    # Get the budget ID
    budget_id = ynab_budget_id_map[budget_name]
    logger.info(f"YNAB budget with name '{budget_name}' paired with id '{budget_id}'")

    # Find the existing accounts and its respective IDs in YNAB, within the budget
    ynab_account_id_map = get_ynab_account_id_mapping(ynab_cli, budget_id)
    # If the account name is not among the account names retrieved, raise an exception
    if account_name not in ynab_account_id_map:
        accounts = list(ynab_account_id_map.keys())
        accounts_str = "'" + "', '".join(accounts) + "'"
        raise AccountNotFoundError(
            f"YNAB account named '{account_name}' not found, available ones: {accounts_str}"
        )
    # Get the account ID
    account_id = ynab_account_id_map[account_name]
    logger.info(f"Account with name '{account_name}' paired with id '{account_id}'")
    logger.info(f"Translating transactions to YNAB format...")
    transactions_ynab = list(
        map(lambda t: _convert_n26_transaction_to_ynab(t, account_id), transactions_n26)
    )
    logger.info(f"Requesting transactions push to the YNAB api...")
    transactions_ynab = ynab_cli.BulkTransactions(transactions=transactions_ynab)
    ynab_cli.TransactionsApi().bulk_create_transactions(budget_id, transactions_ynab)
    logger.info(f"Transactions pushed to YNAB successfully!")


def _convert_n26_transaction_to_ynab(t_n26, account_id):
    t_ynab = {
        "id": t_n26["id"],
        "import_id": t_n26["id"],
        "account_id": account_id,
        "date": datetime.fromtimestamp(t_n26["visibleTS"] / 1000),
        "amount": int(t_n26["amount"] * 1000),
        "cleared": "uncleared",
        "approved": False,
        "deleted": False,
        "payee_name": t_n26.get("merchantName", None),
    }
    t_ynab = ynab_client.TransactionWrapper(t_ynab)
    return t_ynab.transaction


def get_ynab_account_id_mapping(ynab_client, budget_id):
    response = ynab_client.AccountsApi().get_accounts(budget_id).data.accounts
    mapping = {account.name: account.id for account in response}
    return mapping


def get_ynab_budget_id_mapping(ynab_client):
    response = ynab_client.BudgetsApi().get_budgets().data.budgets
    mapping = {budget.name: budget.id for budget in response}
    return mapping


def get_ynab_client():
    config = load_ynab_config()
    configuration = ynab_client.Configuration()
    configuration.api_key_prefix["Authorization"] = "Bearer"
    configuration.api_key["Authorization"] = config["ynab"]["api_key"]
    return ynab_client


def get_n26_client(account_name):
    config = get_n26_account_config(account_name)
    conf = n26.config.Config(validate=False)
    conf.USERNAME.value = config["username"]
    conf.PASSWORD.value = config["password"]
    conf.LOGIN_DATA_STORE_PATH.value = get_n26_token_data_filepath(account_name)
    conf.MFA_TYPE.value = config["mfa_type"]
    conf.validate()
    client = n26.api.Api(conf)
    return client
