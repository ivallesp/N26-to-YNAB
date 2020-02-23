import toml
from src.paths import get_n26_config_filepath, get_ynab_config_filepath


def load_ynab_config():
    path = get_ynab_config_filepath()
    config = toml.load(path)
    return config


def load_n26_config():
    path = get_n26_config_filepath()
    config = toml.load(path)
    return config


def get_n26_account_config(account_name):
    config = load_n26_config()
    if account_name not in config:
        raise ValueError(f"Account with name {account_name} not found in n26.toml")
    return config[account_name]
