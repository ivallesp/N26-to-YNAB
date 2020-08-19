import logging
import tenacity
import time
import os
import ynab_client

import n26.api
import n26.config
import pandas as pd

from datetime import datetime

from src.paths import get_n26_token_data_filepath
from src.config import load_ynab_config, get_n26_account_config
from src.exceptions import (
    BudgetNotFoundError,
    AccountNotFoundError,
    AuthenticationTimeoutError,
)

logger = logging.getLogger(__name__)


def update_ynab(account_name, retries, delay):
    """Call the N26 API with account name specified, download all the transactions, and
    bulk push them to YNAB through their API.

    Args:
        account_name (str): Name of the N26 account as configured in the config/n26.toml
        file.
        retry (int): Number of retries when downloading the n26 transactions
        delay (int): Number of seconds delay between retries
    """
    ynab_conf = load_ynab_config()["ynab"]
    n26_conf = get_n26_account_config(account_name)
    ynab_account_name = n26_conf["ynab_account"]
    budget_name = ynab_conf["budget_name"]
    transactions = download_n26_transactions(account_name, retries=retries, delay=delay)

    # Save the transactions for traceback purposes
    filename = datetime.now().isoformat() + "_" + account_name + ".csv"
    path = os.path.join("logs", filename)
    pd.DataFrame(transactions).to_csv(path, sep=",", index=False)

    transactions = filter_transactions(transactions)
    upload_n26_transactions_to_ynab(
        transactions_n26=transactions,
        budget_name=budget_name,
        account_name=ynab_account_name,
    )


def filter_transactions(transactions):
    """
    This function is intended to be applied to the raw list of transactions provided by
    the N26 API.

    Args:
        transactions (list): list of dictionaries, one dict per transaction, as given by
        the N26 API.

    Returns:
        list: same format as the input transactions list but potentially shortened.
    """
    # Remove the temporary transactions. These transactions will disappear and be
    # replaced by permanent ones. If not removed, this causes duplicates in YNAB,
    # because they have different import IDs.
    logger.info(f"Received {len(transactions)} transactions to filter")
    filtered_types = ["AA", "AE", "AV"]
    transactions = list(filter(lambda x: x["type"] not in filtered_types, transactions))
    logger.info(
        f"{len(transactions)} transactions remaining after applying the filter!"
    )
    return transactions


def download_n26_transactions(account_name, retries=0, delay=60):
    """Download all the N26 transactions from the specified account

    Args:
        account_name (str): Name of the N26 account as configured in the config/n26.toml
        file
        retries (int): Number of retries
        delay (int): Number of seconds delay between retries

    Raises:
        AuthenticationTimeoutError: if the user doesn't give acces through the mobile
        app (2-factor-auth), the function waits for 30 min and retries again. If the
        user does not respond after 5 trials, the function fails with this exception.

    Returns:
        list: transactions with the N26 native format
    """
    logger.info(f"Retrieving N26 transactions from the account '{account_name}'...")
    # Get access
    client = get_n26_client(account_name)
    # Get N26 transactions
    watchdog = retries  # trials before failure
    while watchdog >= 0:  # If there are still trials left...
        logger.info("Requesting transfers to the N26 API...")
        try:
            # Try to call the API. This will potentially show a two-factor notification
            # in the phone of the user. In that case, if the access is not granted, the
            # api client will timeout with a tenacy.RetryError exception
            transactions = client.get_transactions(limit=99999)
            break  # Exit the loop on success
        except tenacity.RetryError:
            logger.error("No app authentication provided! Waiting 30 min...")
            if watchdog <= 0:
                raise AuthenticationTimeoutError("two-factor auth failed! 😡")
            watchdog -= 1
            time.sleep(delay)

    logger.info(f"{len(transactions)} transactions have been retrieved!")
    return transactions


def upload_n26_transactions_to_ynab(transactions_n26, budget_name, account_name):
    """Gets a set of transactions as input and uploads them to the specified budget
    and account. It uses the bulk method for uploading the transactions to YNAB

    Args:
        transactions_n26 (list): list of dictionaries, N26 native format
        budget_name (str): name of the budget as configured in the config/ynab.toml
        account_name (str): name of the YNAB account associated to a N26 account as
        configured in the config/n26.toml

    Raises:
        BudgetNotFoundError: this exception is raised when the budget specified does
        not exist in the YNAB account configured
        AccountNotFoundError: this exception is raised when the account specified does
        not exist in the specified budget of the YNAB account configured
    """
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
    """Converts from the N26 format to the YNAB format. Can be enhanced so that it
    translates from the N26 automatic categorization to the YNAB one.

    Args:
        t_n26 (dict): dictionary containing all the N26 native transaction keys
        account_id (str): id of the YNAB account

    Returns:
        ynab_client.Transaction: transaction in the YNAB native format.
    """
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


def get_ynab_budget_id_mapping(ynab_client):
    """Build a mapping of YNAB budget names to internal ids

    Args:
        ynab_client (ynab_client): YNAB configured client with the credentials

    Returns:
        dict: Dictionary with budget names as keys and ids as values
    """
    response = ynab_client.BudgetsApi().get_budgets().data.budgets
    mapping = {budget.name: budget.id for budget in response}
    return mapping


def get_ynab_account_id_mapping(ynab_client, budget_id):
    """Build a mapping of YNAB account names to internal ids

    Args:
        ynab_client (ynab_client): YNAB configured client with the credentials
        budget_id (str): id of the budget to query

    Returns:
        dict: Dictionary with account names as keys and ids as values
    """
    response = ynab_client.AccountsApi().get_accounts(budget_id).data.accounts
    mapping = {account.name: account.id for account in response}
    return mapping


def get_ynab_client():
    """Handles YNAB connection and returns the cli

    Returns:
        ynab_client: client ready to query the API
    """
    config = load_ynab_config()
    configuration = ynab_client.Configuration()
    configuration.api_key_prefix["Authorization"] = "Bearer"
    configuration.api_key["Authorization"] = config["ynab"]["api_key"]
    return ynab_client


def get_n26_client(account_name):
    """Handles the N26 connection and returns the cli

    Args:
        account_name (str): name of the YNAB account associated to a N26 account as
        configured in the config/n26.toml

    Returns:
        n26.api.Api: client ready to query the API
    """
    config = get_n26_account_config(account_name)
    conf = n26.config.Config(validate=False)
    conf.USERNAME.value = config["username"]
    conf.PASSWORD.value = config["password"]
    conf.LOGIN_DATA_STORE_PATH.value = get_n26_token_data_filepath(account_name)
    conf.MFA_TYPE.value = config["mfa_type"]
    conf.DEVICE_TOKEN.value = config["device_token"]
    conf.validate()
    client = n26.api.Api(conf)
    return client
