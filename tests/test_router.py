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
    registrar.registerAccount(one_ct.address, {"from": user})

    b.tokenX.transfer(user, b.total_fee * 10, {"from": accounts[0]})
    b.tokenX.approve(b.router, b.total_fee * 10, {"from": user})
    chain.sleep(2)

    return b, user, one_ct, b.get_trade_params(user, one_ct)[:-1]


@pytest.fixture()
def init_lo(contracts, accounts, chain):
    b = utility(contracts, accounts, chain)
    registrar = AccountRegistrar.at(b.router.accountRegistrar())
    user = accounts.add()
    one_ct = accounts.add()
    registrar.registerAccount(one_ct.address, {"from": user})

    b.tokenX.transfer(user, b.total_fee * 10, {"from": accounts[0]})
    b.tokenX.approve(b.router, b.total_fee * 10, {"from": user})
    chain.sleep(2)

    return b, user, one_ct, b.get_trade_params(user, one_ct, True)[:-1]


def test_referral(init, contracts, accounts, chain):
    b, user, one_ct, _ = init
    referrer = accounts.add()
    referral_code = "test"
    trade_params = [
        b.total_fee,
        b.period,
        b.binary_options.address,
        b.strike,
        b.slippage,
        b.allow_partial_fill,
        referral_code,
        0,
        int(398e8),
        15e2,
    ]
    b.referral_contract.registerCode(
        referral_code,
        {"from": referrer},
    )
    trade_params = b.get_trade_params(user, one_ct, True, params=trade_params)[:-1]
    txn = b.router.openTrades([trade_params], {"from": b.bot})
    assert txn.events["OpenTrade"]["optionId"] == 0
    assert txn.events["OpenTrade"]["queueId"] == 0
    print(b.binary_options.options(txn.events["OpenTrade"]["optionId"]))


def test_boost(init, contracts, accounts, chain):
    b, user, one_ct, _ = init
    metadata_hash = "QmRu61jShPgiQp33UA5RNcULAvLU5JEPbnXGqEtBmVcdMg"
    booster = Booster.at(b.binary_options_config.boosterContract())

    accounts[0].transfer(user, "10 ether")
    base_payout = get_payout(
        b.binary_options.getSettlementFeePercentage(user, user, 15e2)
    )
    b.tokenX.transfer(user, booster.couponPrice(), {"from": b.owner})
    b.tokenX.approve(booster.address, booster.couponPrice(), {"from": user})
    b.trader_nft_contract.claim({"from": user, "value": "2 ether"})
    b.trader_nft_contract.safeMint(
        user,
        metadata_hash,
        1,
        0,
        {"from": b.owner},
    )
    booster.buy(b.tokenX.address, 0, {"from": user})

    def check_payout(option_id):
        option = b.binary_options.options(option_id)
        min_payout = option[-2] + (option[-2] * base_payout) / 100
        return min_payout, option[2]

    optionId, _, _ = b.create(user, one_ct, queue_id=0)
    chain.sleep(1)
    min_payout, payout = check_payout(optionId)
    assert payout > min_payout, "Wrong payout"
    optionId, _, _ = b.create(user, one_ct, queue_id=1)
    chain.sleep(1)
    min_payout, payout = check_payout(optionId)
    assert payout > min_payout, "Wrong payout"
    optionId, _, _ = b.create(user, one_ct, queue_id=2)
    chain.sleep(1)
    min_payout, payout = check_payout(optionId)
    assert payout == min_payout, "Wrong payout"


def test_boost_with_ref(init, contracts, accounts, chain):
    b, user, one_ct, _ = init
    referrer = accounts.add()
    referral_code = "test"
    trade_params = [
        b.total_fee,
        b.period,
        b.binary_options.address,
        b.strike,
        b.slippage,
        b.allow_partial_fill,
        referral_code,
        0,
        int(398e8),
        15e2,
    ]
    b.referral_contract.registerCode(
        referral_code,
        {"from": referrer},
    )
    base_sf = 15e2
    ref_discount = base_sf - b.binary_options.getSettlementFeePercentage(
        referrer, user, base_sf
    )

    metadata_hash = "QmRu61jShPgiQp33UA5RNcULAvLU5JEPbnXGqEtBmVcdMg"
    booster = Booster.at(b.binary_options_config.boosterContract())

    accounts[0].transfer(user, "10 ether")
    base_payout = 100 - (
        (b.binary_options.getSettlementFeePercentage(user, user, 15e2) * 2) / 100
    )
    b.tokenX.transfer(user, booster.couponPrice(), {"from": b.owner})
    b.tokenX.approve(booster.address, booster.couponPrice(), {"from": user})
    b.trader_nft_contract.claim({"from": user, "value": "2 ether"})
    b.trader_nft_contract.safeMint(
        user,
        metadata_hash,
        1,
        0,
        {"from": b.owner},
    )
    booster.buy(b.tokenX.address, 0, {"from": user})
    boost = base_sf - b.binary_options.getSettlementFeePercentage(user, user, base_sf)

    optionId, _, _ = b.create(user, one_ct, queue_id=0, params=trade_params)
    option = b.binary_options.options(optionId)
    min_payout = option[-2] + (
        option[-2] * get_payout(base_sf - boost - ref_discount) / 100
    )
    assert option[2] > min_payout, "Wrong payout"


def test_user_params(init, contracts, accounts, chain):
    b, user, one_ct, trade_params = init
    user_sign_info = b.get_user_signature(
        b.trade_params[:8],
        user.address,
        user.private_key,
    )
    wrong_trade_params = trade_params[:]
    wrong_trade_params[-2] = user_sign_info

    # Wrong pk
    txn = b.router.openTrades([wrong_trade_params], {"from": b.bot})
    assert (
        txn.events["FailResolve"]["reason"] == "Router: User signature didn't match"
    ), "Wrong reason"
    chain.sleep(2)
    # Right init
    txn = b.router.openTrades([trade_params], {"from": b.bot})
    assert txn.events["OpenTrade"]["optionId"] == 0
    assert txn.events["OpenTrade"]["queueId"] == 0
    # print(txn.events["OpenTrade"])
    # print(b.router.optionIdMapping(b.binary_options, 0))
    # print(b.router.queuedTrades(0))

    # Same signature, same queueId
    txn = b.router.openTrades([trade_params], {"from": b.bot})
    assert (
        txn.events["FailResolve"]["reason"] == "Router: Trade has already been opened"
    ), "Wrong reason"

    # Same signature, different queueId
    trade_params[0] = 1
    txn = b.router.openTrades([trade_params], {"from": b.bot})
    assert (
        txn.events["FailResolve"]["reason"] == "Router: Signature already used"
    ), "Wrong reason"

    chain.sleep(1)
    user_sign_info = b.get_user_signature(
        b.trade_params[:8],
        user.address,
        one_ct.private_key,
    )
    chain.sleep(61)
    sf_expiry = chain.time() + 3
    sf_signature = b.get_sf_signature(b.binary_options, sf_expiry)
    current_time = chain.time()

    publisher_signature = [
        b.get_signature(b.binary_options, current_time, b.trade_params[-2]),
        current_time,
    ]
    trade_params[-1] = publisher_signature
    trade_params[-2] = user_sign_info
    trade_params[-3] = [sf_signature, sf_expiry]
    txn = b.router.openTrades([trade_params], {"from": b.bot})
    assert (
        txn.events["FailResolve"]["reason"]
        == "Router: Invalid user signature timestamp"
    ), "Wrong reason"


def test_lo(init_lo, contracts, accounts, chain):
    b, user, one_ct, trade_params = init_lo

    chain.sleep(3600 * 4)
    txn = b.router.openTrades([trade_params], {"from": b.bot})
    assert (
        txn.events["FailResolve"]["reason"] == "Router: Settlement fee has expired"
    ), "Wrong reason"
    current_time = chain.time()
    sf_expiry = chain.time() + 3
    sf_signature = b.get_sf_signature(b.binary_options, sf_expiry)
    publisher_signature = [
        b.get_signature(b.binary_options, current_time, b.trade_params[-2]),
        current_time,
    ]
    trade_params[-1] = publisher_signature
    trade_params[-3] = [sf_signature, sf_expiry]
    txn = b.router.openTrades([trade_params], {"from": b.bot})
    assert txn.events["OpenTrade"]["optionId"] == 0
    assert txn.events["OpenTrade"]["queueId"] == 0
    # print(txn.events["OpenTrade"])
    # print("limit_order", b.router.queuedTrades(0))


def test_wrong_sf(init, contracts, accounts, chain):
    b, user, one_ct, trade_params = init
    sf_expiry = chain.time() + 3

    # Wrong asset
    binary_european_options_atm_2 = contracts["binary_european_options_atm_2"]
    sf_signature = b.get_sf_signature(binary_european_options_atm_2, sf_expiry)
    trade_params[-3] = [sf_signature, sf_expiry]
    txn = b.router.openTrades([trade_params], {"from": b.bot})
    assert (
        txn.events["FailResolve"]["reason"] == "Router: Wrong settlement fee"
    ), "Wrong reason"

    # Wrong time
    chain.sleep(4)
    sf_signature = b.get_sf_signature(b.binary_options, sf_expiry)
    trade_params[-3] = [sf_signature, sf_expiry]
    txn = b.router.openTrades([trade_params], {"from": b.bot})
    assert (
        txn.events["FailResolve"]["reason"] == "Router: Settlement fee has expired"
    ), "Wrong reason"


def test_exceution(init, contracts, accounts, chain):
    b, user, one_ct, _ = init
    closing_price = 300e8
    optionId, queueId, trade_params = b.create(user, one_ct)
    expiration_time = b.binary_options.options(optionId)[-3]
    chain.sleep(expiration_time - chain.time() + 1)

    one_ct = accounts.add()
    b.reregister(user, one_ct)
    close_params = [
        optionId,
        b.binary_options,
        closing_price,
        b.is_above,
        trade_params[-1],
        [
            b.get_signature(b.binary_options, expiration_time, closing_price),
            expiration_time,
        ],
    ]
    txn = b.router.executeOptions([close_params], {"from": b.bot})
    assert txn.events["Exercise"]["id"] == 0, "Wrong id"


def test_early_close_fail(init, contracts, accounts, chain):
    b, user, one_ct, _ = init

    closing_price = 300e8
    optionId, queueId, trade_params = b.create(user, one_ct)
    expiration_time = b.binary_options.options(optionId)[-3]
    chain.sleep(expiration_time - chain.time() - 1)
    current_time = int(chain.time())
    signature = b.get_close_signature(
        b.binary_options, current_time, optionId, one_ct.private_key
    )
    close_params = [
        (
            optionId,
            b.binary_options,
            closing_price,
            b.is_above,
            trade_params[-1],
            [
                b.get_signature(b.binary_options, current_time, closing_price),
                current_time,
            ],
        ),
        (signature, current_time),
    ]
    txn = b.router.closeAnytime([close_params], {"from": b.bot})
    assert txn.events["FailUnlock"]["optionId"] == 0, "Wrong id"
    assert (
        txn.events["FailUnlock"]["reason"] == "Router: Early close is not allowed"
    ), "Wrong reason"


def test_early_close(init, contracts, accounts, chain):
    b, user, one_ct, _ = init
    b.binary_options_config.toggleEarlyClose()

    closing_price = 300e8
    optionId, queueId, trade_params = b.create(user, one_ct)
    expiration_time = b.binary_options.options(optionId)[-3]
    chain.sleep(expiration_time - chain.time() - 1)
    current_time = int(chain.time())

    signature = b.get_close_signature(
        b.binary_options, current_time, optionId, one_ct.private_key
    )

    close_params = [
        (
            optionId,
            b.binary_options,
            closing_price,
            b.is_above,
            trade_params[-1],
            [
                b.get_signature(b.binary_options, current_time, closing_price),
                current_time,
            ],
        ),
        (signature, current_time),
    ]
    chain.snapshot()
    _one_ct = accounts.add()
    b.reregister(user, _one_ct)

    txn = b.router.closeAnytime([close_params], {"from": b.bot})
    print(txn.events)
    assert (
        txn.events["FailUnlock"]["reason"] == "Router: User signature didn't match"
    ), "Wrong reson"
    chain.revert()

    txn = b.router.closeAnytime([close_params], {"from": b.bot})
    # print(txn.events)
    assert txn.events["Exercise"]["id"] == 0, "Wrong id"
