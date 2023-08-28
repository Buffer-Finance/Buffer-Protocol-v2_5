import os

from brownie import (
    accounts,
)
from colorama import Fore, Style



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
    print(super_admin.balance() / 1e18)
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
