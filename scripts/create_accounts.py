import os
import time

import brownie
from brownie import (
    accounts,
    network,
)
from colorama import Fore, Style
from eth_account import Account
from eth_account.messages import encode_defunct

from .utility import deploy_contract, save_flat, transact


def main():
    funds = {
        "open_keeper": "1 ether",
        "close_keeper": "1 ether",
        "revoke_keeper": "1 ether",
        "early_close_keeper": "1 ether",
        "sf_publisher": "0 ether",
        "config_setter": "0.5 ether",
        "admin": "1 ether",
    }

    super_admin = accounts.add(os.environ["BFR_PK"])
    all_accounts = {}
    for account in funds:
        acc = accounts.add()
        if funds[account] != "0 ether":
            super_admin.transfer(acc, funds[account])
        all_accounts.update(
            {
                account: {
                    "pk": acc.private_key,
                    "address": acc.address,
                    "balance": acc.balance() / 1e18,
                }
            }
        )
    print(Fore.GREEN + "Accounts created" + Style.RESET_ALL)
    print(all_accounts)
