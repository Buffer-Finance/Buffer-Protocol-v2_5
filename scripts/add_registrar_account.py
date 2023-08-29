import os

from brownie import accounts, AccountRegistrar
from colorama import Fore, Style
from .utility import deploy_contract, save_flat, transact


def main():
    account_registrar = AccountRegistrar.at(
        "0xC2fa406F8149Eb2c5a0bA9Cc9b7eD0339792c7c4"
    )
    super_admin = accounts.add(os.environ["BFR_PK"])
    # Add pk here only for temp purpose
    admin = accounts.add("")
    acc = accounts.add()
    super_admin.transfer(acc, "1 ether")
    ADMIN_ROLE = account_registrar.ADMIN_ROLE()

    transact(
        account_registrar.address,
        account_registrar.abi,
        "grantRole",
        ADMIN_ROLE,
        acc.address,
        sender=admin,
    )
    print({"pk": acc.private_key, "address": acc.address})

    assert account_registrar.hasRole(ADMIN_ROLE, acc.address)
