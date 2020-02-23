import os


def get_log_config_filepath():
    return "logging.ini"


def get_config_path():
    path = os.path.join("config")
    return path


def get_n26_token_data_filepath(account_name):
    path = os.path.join(get_config_path(), f"token_data_{account_name}")
    return path


def get_n26_config_filepath():
    path = os.path.join("config", f"n26.toml")
    if not os.path.exists(path):
        raise ValueError(
            f"Account {account_name} not configured. File {path} not found!"
        )
    return path


def get_ynab_config_filepath():
    path = os.path.join("config", f"ynab.toml")
    if not os.path.exists(path):
        raise ValueError(
            f"Account {account_name} not configured. File {path} not found!"
        )
    return path
