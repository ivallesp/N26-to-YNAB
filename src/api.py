import ynab_client
import n26.api
import n26.config
from src.paths import get_n26_token_data_filepath
from src.config import load_ynab_config, get_n26_account_config
from datetime import datetime


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
    # Get access
    client = get_n26_client(account_name)
    # Get N26 transactions
    transactions = client.get_transactions(limit=0)
    return transactions


def upload_n26_transactions_to_ynab(transactions_n26, budget_name, account_name):
    # Get an instance of YNAB and N26 APIs
    ynab_cli = get_ynab_client()

    # Get YNAB budget and account maps to respective IDs
    ynab_budget_id_map = get_ynab_budget_id_mapping(ynab_cli)
    budget_id = ynab_budget_id_map[budget_name]
    ynab_account_id_map = get_ynab_account_id_mapping(ynab_cli, budget_id)
    account_id = ynab_account_id_map[account_name]

    transactions_ynab = list(
        map(lambda t: _convert_n26_transaction_to_ynab(t, account_id), transactions_n26)
    )
    transactions_ynab = ynab_cli.BulkTransactions(transactions=transactions_ynab)
    ynab_cli.TransactionsApi().bulk_create_transactions(budget_id, transactions_ynab)


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
