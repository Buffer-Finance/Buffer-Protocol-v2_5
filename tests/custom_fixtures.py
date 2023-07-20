from enum import IntEnum
import copy
from brownie import AccountRegistrar, Booster
from utility import utility
import pytest

ONE_DAY = 86400


def get_payout(sf):
    return 100 - ((sf * 2) / 100)


@pytest.fixture()
def init(contracts, accounts, chain):
    b = utility(contracts, accounts, chain)
    registrar = AccountRegistrar.at(b.router.accountRegistrar())
    user = accounts.add()
    one_ct = accounts.add()
    # registrar.registerAccount(one_ct.address, {"from": user})

    b.tokenX.transfer(user, b.total_fee * 10, {"from": accounts[0]})
    chain.sleep(2)

    return b, user, one_ct, b.get_trade_params(user, one_ct)[:-1]


@pytest.fixture()
def early_close(contracts, accounts, chain):
    b = utility(contracts, accounts, chain)
    registrar = AccountRegistrar.at(b.router.accountRegistrar())
    user = accounts.add()
    one_ct = accounts.add()
    # registrar.registerAccount(one_ct.address, {"from": user})

    b.tokenX.transfer(user, b.total_fee * 10, {"from": accounts[0]})
    chain.sleep(2)

    b.binary_options_config.toggleEarlyClose()

    optionId, queueId, trade_params, _ = b.create(user, one_ct)
    option = b.binary_options.options(optionId)
    closing_price = 400e8
    close_params = [
        optionId,
        b.binary_options,
        closing_price,
        b.is_above,
        trade_params[-1],
    ]
    signature_time = int(chain.time())
    signature = b.get_close_signature(
        b.binary_options, signature_time, optionId, one_ct.private_key
    )

    chain.sleep(1)

    current_time = int(chain.time())
    close_params = [
        (
            *close_params,
            [
                b.get_signature(b.binary_options, current_time, closing_price),
                current_time,
            ],
        ),
        (signature, signature_time),
    ]
    return b, close_params, option, user


@pytest.fixture()
def init_lo(contracts, accounts, chain):
    b = utility(contracts, accounts, chain)
    registrar = AccountRegistrar.at(b.router.accountRegistrar())
    user = accounts.add()
    one_ct = accounts.add()

    b.tokenX.transfer(user, b.total_fee * 10, {"from": accounts[0]})
    chain.sleep(2)

    return b, user, one_ct, b.get_trade_params(user, one_ct, True)[:-1]


@pytest.fixture()
def close(contracts, accounts, chain):
    b = utility(contracts, accounts, chain)
    registrar = AccountRegistrar.at(b.router.accountRegistrar())
    user = accounts.add()
    one_ct = accounts.add()
    # registrar.registerAccount(one_ct.address, {"from": user})

    b.tokenX.transfer(user, b.total_fee * 10, {"from": accounts[0]})
    chain.sleep(2)
    closing_price = 300e8

    optionId, queueId, trade_params, _ = b.create(user, one_ct)
    params = [
        optionId,
        b.binary_options,
        closing_price,
        b.is_above,
        trade_params[-1],
    ]

    return (b, params, closing_price, user, optionId)
