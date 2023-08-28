from enum import IntEnum
import math

import copy
from brownie import (
    AccountRegistrar,
    Booster,
    PoolOIConfig,
    MarketOIConfig,
    PoolOIStorage,
)
import brownie
from utility import utility
import pytest
from custom_fixtures import init, early_close, init_lo, close

ONE_DAY = 86400


def get_payout(sf):
    return 100 - ((sf * 2) / 100)


def get_publisher_signature(b, closing_price, time):
    return [
        b.get_signature(b.binary_options, time, closing_price),
        time,
    ]


def test_revoke(init, contracts, accounts, chain):
    b, user, one_ct, trade_params = init
    b.tokenX.approve(b.router.address, 10e6, {"from": user})
    assert b.tokenX.allowance(user, b.router.address) == 10e6, "Wrong allowance"
    deadline = b.chain.time() + 50
    allowance = 0
    permit = [
        allowance,
        deadline,
        *b.get_permit(allowance, deadline, user),
        True,
    ]
    txn = b.router.revokeApprovals([(b.tokenX.address, user, permit)])
    assert txn.events["RevokeRouter"], "Wrong event"
    assert b.tokenX.allowance(user, b.router.address) == 0, "Wrong allowance"


def test_option_transfers(init, contracts, accounts, chain):
    b, user, one_ct, trade_params = init
    optionId, queueId, trade_params, txn = b.create(user, one_ct)

    with brownie.reverts("Token transfer not allowed"):
        b.binary_options.transferFrom(user, accounts[2], optionId, {"from": user})
    b.binary_options.approveAddress(user, {"from": accounts[0]})
    txn = b.binary_options.transferFrom(user, accounts[2], optionId, {"from": user})
    assert txn.events["Transfer"], "Transfer event not emitted"


def test_user_params(init, contracts, accounts, chain):
    b, user, one_ct, trade_params = init
    user_1 = accounts.add()

    # No balance
    params = b.get_trade_params(user_1, one_ct)
    txn = b.router.openTrades([*params[:-1]], {"from": b.bot})
    assert (
        txn.events["FailResolve"]["reason"] == "Router: Insufficient balance"
    ), "Wrong reason"

    # Wrong allowance
    b.tokenX.transfer(user_1, b.total_fee * 10, {"from": accounts[0]})
    params[0][2][-1] = False
    txn = b.router.openTrades([*params[:-1]], {"from": b.bot})
    assert (
        txn.events["FailResolve"]["reason"] == "Router: Incorrect allowance"
    ), "Wrong reason"

    # Right init
    txn = b.router.openTrades([*trade_params], {"from": b.bot})
    # print(txn.events)
    assert (
        b.router.getAccountMapping(user.address)[0] == one_ct.address
    ), "Wrong mapping"
    assert txn.events["OpenTrade"]["optionId"] == 0
    assert txn.events["OpenTrade"]["queueId"] == 0
    assert len(txn.events["Approval"]) == 3

    # Should fail since the approval nonce is same
    txn = b.router.openTrades([*trade_params], {"from": b.bot})
    assert (
        txn.events["FailResolve"]["reason"] == "ERC20Permit: invalid signature"
    ), "Wrong reason"

    # Same signature, same queueId
    trade_params[0][2][-1] = False
    txn = b.router.openTrades([*trade_params], {"from": b.bot})
    assert (
        txn.events["FailResolve"]["reason"] == "Router: Trade has already been opened"
    ), "Wrong reason"

    # Same signature, different queueId
    trade_params[0][0][0] = 1
    txn = b.router.openTrades([*trade_params], {"from": b.bot})
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
    trade_params[0][0][-1] = publisher_signature
    trade_params[0][0][-2] = user_sign_info
    trade_params[0][0][-3] = [sf_signature, sf_expiry]
    txn = b.router.openTrades([*trade_params], {"from": b.bot})
    assert (
        txn.events["FailResolve"]["reason"]
        == "Router: Invalid user signature timestamp"
    ), "Wrong reason"

    # SHould fail if approval deadline exceeds
    params = b.get_trade_params(user, one_ct, queue_id=1)
    chain.sleep(51)
    txn = b.router.openTrades([*params[:-1]], {"from": b.bot})
    assert (
        txn.events["FailResolve"]["reason"] == "ERC20Permit: expired deadline"
    ), "Wrong reason"

    # Second buy should pass
    params[0][2][-1] = False
    txn = b.router.openTrades([*params[:-1]], {"from": b.bot})
    assert txn.events["OpenTrade"]["optionId"] == 1
    assert txn.events["OpenTrade"]["queueId"] == 1
    assert len(txn.events["Approval"]) == 2

    # Should fail if the allowance is exhausted
    trade_params = b.trade_params
    trade_params[0] = int(3e6)
    params = b.get_trade_params(user, one_ct, params=trade_params, queue_id=2)
    params[0][2][-1] = False
    txn = b.router.openTrades([*params[:-1]], {"from": b.bot})
    assert (
        txn.events["FailResolve"]["reason"] == "Router: Incorrect allowance"
    ), "Wrong reason"

    # Should pass with added allowance
    params[0][2][-1] = True
    txn = b.router.openTrades([*params[:-1]], {"from": b.bot})
    total_amount_deducted = sum(
        [x["value"] if x["from"] == user.address else 0 for x in txn.events["Transfer"]]
    )
    assert txn.events["OpenTrade"]["optionId"] == 2
    assert txn.events["OpenTrade"]["queueId"] == 2
    assert (
        total_amount_deducted == trade_params[0] + b.binary_options_config.platformFee()
    ), "Wrong amount deducted"


def test_lo(init_lo, contracts, accounts, chain):
    b, user, one_ct, trade_params = init_lo
    chain.snapshot()
    txn = b.router.openTrades([*trade_params], {"from": b.bot})
    chain.revert()
    assert txn.events["OpenTrade"]["optionId"] == 0
    assert txn.events["OpenTrade"]["queueId"] == 0

    # Should fail after the lo expiration
    chain.sleep(31)
    txn = b.router.openTrades([*trade_params], {"from": b.bot})
    assert (
        txn.events["FailResolve"]["reason"] == "Router: Limit order has already expired"
    ), "Wrong reason"


def test_wrong_sf(init, contracts, accounts, chain):
    b, user, one_ct, trade_params = init
    sf_expiry = chain.time() + 3

    # Wrong asset
    binary_european_options_atm_2 = contracts["binary_european_options_atm_2"]
    sf_signature = b.get_sf_signature(binary_european_options_atm_2, sf_expiry)
    trade_params[0][0][-3] = [sf_signature, sf_expiry]
    txn = b.router.openTrades([*trade_params], {"from": b.bot})
    assert (
        txn.events["FailResolve"]["reason"] == "Router: Wrong settlement fee"
    ), "Wrong reason"

    # Wrong time
    chain.sleep(4)
    sf_signature = b.get_sf_signature(b.binary_options, sf_expiry)
    trade_params[0][2][-1] = False
    trade_params[0][0][-3] = [sf_signature, sf_expiry]
    txn = b.router.openTrades([*trade_params], {"from": b.bot})
    assert (
        txn.events["FailResolve"]["reason"] == "Router: Settlement fee has expired"
    ), "Wrong reason"


def test_creation_window(init, contracts, accounts, chain):
    b, user, one_ct, _ = init
    period = 5 * 60

    b.check_trading_window(6, 22, 0, period, False)  # Saturday 22:00 (5m)
    b.check_trading_window(0, 15, 0, period, False)  # Sunday 15:00 (5m)
    b.check_trading_window(0, 21, 59, period, False)  # Sunday 21:59 (5m)
    b.check_trading_window(0, 22, 0, period, True)  # Sunday 22:00   (5m)
    b.check_trading_window(0, 22, 59, period, True)  # Sunday 22:59 (5m)
    b.check_trading_window(0, 22, 0, period, True)  # Sunday 22:00  (5m)
    b.check_trading_window(0, 23, 0, period, True)  # Sunday 23:00   (5m)
    b.check_trading_window(0, 23, 0, 23 * 3600, True)  # Sunday 23:00 (23h)
    b.check_trading_window(0, 23, 0, (23 * 3600) - 1, True)  # Sunday 23:00 (22.59)
    b.check_trading_window(1, 21, 30, (30 * 60), True)  # Monday 21:30 (30m)
    b.check_trading_window(1, 21, 30, (30 * 60) - 1, True)  # Monday 21:30 (29.59m)
    b.check_trading_window(1, 22, 0, (30 * 60), True)  # Monday 22:00 (30m)
    b.check_trading_window(1, 23, 0, (2 * 3600), True)  # Monday 23:00 (2h)
    b.check_trading_window(2, 1, 0, (2 * 3600), True)  # Tuesday 1:00 (2h)
    b.check_trading_window(5, 19, 30, (30 * 60), False)  # Friday 19:30 (30m)
    b.check_trading_window(5, 19, 30, (30 * 60) - 1, True)  # Friday 19:30 (29.59m)
    b.check_trading_window(5, 20, 0, (30 * 60), False)  # Friday 18:00 (30m)


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
    txn = b.router.openTrades([*trade_params], {"from": b.bot})
    assert txn.events["OpenTrade"]["optionId"] == 0
    assert txn.events["OpenTrade"]["queueId"] == 0
    print(b.binary_options.options(txn.events["OpenTrade"]["optionId"]))


def test_boost_buy(init, contracts, accounts, chain):
    b, user, one_ct, _ = init
    user_1 = accounts.add()
    booster = Booster.at(b.binary_options_config.boosterContract())
    metadata_hash = "QmRu61jShPgiQp33UA5RNcULAvLU5JEPbnXGqEtBmVcdMg"
    accounts[0].transfer(user_1, "10 ether")
    b.trader_nft_contract.claim({"from": user_1, "value": "2 ether"})
    b.trader_nft_contract.safeMint(
        user_1,
        metadata_hash,
        1,
        0,
        {"from": b.owner},
    )
    deadline = chain.time() + 3600
    permit = [
        booster.couponPrice() * 5,
        deadline,
        *b.get_permit(
            booster.couponPrice() * 5, deadline, user, spender=booster.address
        ),
        True,
    ]
    b.tokenX.approve(booster.address, booster.couponPrice() * 5, {"from": user})
    b.tokenX.transfer(user, booster.couponPrice() * 5, {"from": b.owner})
    txn = booster.buy(b.tokenX.address, 0, user, permit, 5, {"from": b.owner})
    assert booster.userBoostTrades(b.tokenX.address, user)[0] == 10, "Wrong boost"
    assert txn.events["Transfer"]["value"] == booster.couponPrice() * 5, "Wrong amount"


def test_boost(init, contracts, accounts, chain):
    b, user, one_ct, _ = init
    metadata_hash = "QmRu61jShPgiQp33UA5RNcULAvLU5JEPbnXGqEtBmVcdMg"
    booster = Booster.at(b.binary_options_config.boosterContract())

    accounts[0].transfer(user, "10 ether")
    base_payout = get_payout(
        b.binary_options.getSettlementFeePercentage(user, user, 15e2)
    )
    print(booster.getNftTierDiscounts())
    b.tokenX.transfer(user, booster.couponPrice(), {"from": b.owner})
    # b.tokenX.approve(booster.address, booster.couponPrice(), {"from": user})
    b.trader_nft_contract.claim({"from": user, "value": "2 ether"})
    b.trader_nft_contract.safeMint(
        user,
        metadata_hash,
        1,
        0,
        {"from": b.owner},
    )
    deadline = chain.time() + 3600
    permit = [
        booster.couponPrice(),
        deadline,
        *b.get_permit(booster.couponPrice(), deadline, user, spender=booster.address),
        True,
    ]
    booster.buy(b.tokenX.address, 0, user, permit, 1, {"from": b.owner})

    def check_payout(option_id):
        option = b.binary_options.options(option_id)
        min_payout = option[-2] + (option[-2] * base_payout) / 100
        return min_payout, option[2]

    optionId, _, _, _ = b.create(user, one_ct, queue_id=0)
    chain.sleep(1)
    min_payout, payout = check_payout(optionId)
    assert payout > min_payout, "Wrong payout"
    optionId, _, _, _ = b.create(user, one_ct, queue_id=1)
    chain.sleep(1)
    min_payout, payout = check_payout(optionId)
    assert payout > min_payout, "Wrong payout"
    optionId, _, _, _ = b.create(user, one_ct, queue_id=2)
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
    # b.tokenX.approve(booster.address, booster.couponPrice(), {"from": user})
    b.trader_nft_contract.claim({"from": user, "value": "2 ether"})
    b.trader_nft_contract.safeMint(
        user,
        metadata_hash,
        1,
        0,
        {"from": b.owner},
    )
    deadline = chain.time() + 3600
    permit = [
        booster.couponPrice(),
        deadline,
        *b.get_permit(booster.couponPrice(), deadline, user, spender=booster.address),
        True,
    ]
    booster.buy(b.tokenX.address, 0, user, permit, 1, {"from": b.owner})
    boost = base_sf - b.binary_options.getSettlementFeePercentage(user, user, base_sf)

    optionId, _, _, _ = b.create(user, one_ct, queue_id=0, params=trade_params)
    option = b.binary_options.options(optionId)
    min_payout = option[-2] + (
        option[-2] * get_payout(base_sf - boost - ref_discount) / 100
    )
    assert option[2] >= min_payout, "Wrong payout"


def test_pool_oi(init, contracts, accounts, chain):
    b, user, one_ct, trade_params = init
    chain.sleep(1)
    chain.mine(1)
    pool_oi_config_contract = PoolOIConfig.at(
        b.binary_options_config.poolOIConfigContract()
    )
    market_oi_config_contract = MarketOIConfig.at(
        b.binary_options_config.marketOIConfigContract()
    )
    pool_oi_storage_contract = PoolOIStorage.at(
        b.binary_options_config.poolOIStorageContract()
    )
    pool_oi_config_contract.setMaxPoolOI(7e6)
    market_oi_config_contract.setMaxMarketOI(11e6)
    market_oi_config_contract.setMaxTradeSize(6e6)

    def get_oi():
        return (
            pool_oi_config_contract.getMaxPoolOI(),
            pool_oi_config_contract.getPoolOICap(),
            pool_oi_storage_contract.totalPoolOI(),
            market_oi_config_contract.getMaxMarketOI(b.binary_options.totalMarketOI()),
            market_oi_config_contract.getMarketOICap(),
            b.binary_options.totalMarketOI(),
        )

    def print_oi():
        (
            get_max_pool_oi,
            get_pool_oi_cap,
            get_total_pool_oi,
            get_max_market_oi,
            get_market_oi_cap,
            get_total_market_oi,
        ) = get_oi()
        print(get_max_pool_oi / 1e6, "max pool oi")
        print(get_pool_oi_cap / 1e6, "pool oi cap")
        print(get_total_pool_oi / 1e6, "total pool oi")
        print(get_max_market_oi / 1e6, "max market oi")
        print(get_market_oi_cap / 1e6, "market oi cap")
        print(get_total_market_oi / 1e6, "total market oi")

    # print_oi()
    # print(b.router.queuedTrades(0))
    # Max Pool oi > trade size
    trade_params = b.trade_params
    fee = int(4e6)
    trade_params[0] = fee  # total_fee
    _, _, _, _, _, tmi_before = get_oi()
    optionId, queueId, trade_params, txn = b.create(
        user, one_ct, params=trade_params, queue_id=1
    )
    _, _, _, _, _, tmi_after = get_oi()
    option = b.binary_options.options(optionId)
    uint_fee, _, _ = b.binary_options.fees(int(1e6), user, "", 15e2)
    assert option[-2] == fee, "Wrong fee"
    x = option[2] / 1e6
    y = ((fee * 1e6) // uint_fee) / 1e6
    assert math.isclose(x, y, abs_tol=5e-6)

    assert (
        txn.events["UpdatePoolOI"]["isIncreased"]
        and txn.events["UpdatePoolOI"]["interest"] == fee
    ), "Wrong event"
    assert tmi_after == tmi_before + fee, "Wrong total market interest"

    # Max Pool oi  < current pool oi + trade size
    chain.sleep(1)
    trade_params = b.trade_params
    fee = int(4e6)
    trade_params[0] = fee  # total_fee
    max_pool_oi, _, _, _, _, tmi_before = get_oi()
    optionId, queueId, trade_params, txn = b.create(
        user, one_ct, params=trade_params, queue_id=2
    )
    _, _, _, _, _, tmi_after = get_oi()
    option = b.binary_options.options(optionId)
    uint_fee, _, _ = b.binary_options.fees(int(1e6), user, "", 15e2)
    assert option[-2] == max_pool_oi, "Wrong fee"
    # assert option[2] == (max_pool_oi * 1e6) // uint_fee, "Wrong amount"
    x = option[2] / 1e6
    y = ((max_pool_oi * 1e6) // uint_fee) / 1e6
    assert math.isclose(x, y, abs_tol=5e-6)

    assert (
        txn.events["UpdatePoolOI"]["isIncreased"]
        and txn.events["UpdatePoolOI"]["interest"] == max_pool_oi
    ), "Wrong event"
    assert tmi_after == tmi_before + max_pool_oi, "Wrong total market interest"
    # print_oi()


def test_market_oi(init, contracts, accounts, chain):
    b, user, one_ct, trade_params = init
    pool_oi_config_contract = PoolOIConfig.at(
        b.binary_options_config.poolOIConfigContract()
    )
    market_oi_config_contract = MarketOIConfig.at(
        b.binary_options_config.marketOIConfigContract()
    )
    pool_oi_storage_contract = PoolOIStorage.at(
        b.binary_options_config.poolOIStorageContract()
    )
    pool_oi_config_contract.setMaxPoolOI(10e6)
    market_oi_config_contract.setMaxMarketOI(4e6)
    market_oi_config_contract.setMaxTradeSize(2e6)

    def get_oi():
        return (
            pool_oi_config_contract.getMaxPoolOI(),
            pool_oi_config_contract.getPoolOICap(),
            pool_oi_storage_contract.totalPoolOI(),
            market_oi_config_contract.getMaxMarketOI(b.binary_options.totalMarketOI()),
            market_oi_config_contract.getMarketOICap(),
            b.binary_options.totalMarketOI(),
        )

    def print_oi():
        (
            get_max_pool_oi,
            get_pool_oi_cap,
            get_total_pool_oi,
            get_max_market_oi,
            get_market_oi_cap,
            get_total_market_oi,
        ) = get_oi()
        print(get_max_pool_oi / 1e6, "max pool oi")
        print(get_pool_oi_cap / 1e6, "pool oi cap")
        print(get_total_pool_oi / 1e6, "total pool oi")
        print(get_max_market_oi / 1e6, "max market oi")
        print(get_market_oi_cap / 1e6, "market oi cap")
        print(get_total_market_oi / 1e6, "total market oi")

    # print_oi()
    # print_oi()
    # print(b.router.queuedTrades(0))
    queue_id = 1
    # Max Trade Size > trade size
    _, _, _, _, _, tmi_before = get_oi()
    optionId, queueId, trade_params, txn = b.create(user, one_ct, queue_id=queue_id)
    _, _, _, _, _, tmi_after = get_oi()
    option = b.binary_options.options(optionId)
    uint_fee, _, _ = b.binary_options.fees(int(1e6), user, "", 15e2)

    assert option[-2] == b.total_fee, "Wrong fee"
    assert option[2] == (b.total_fee * 1e6) // uint_fee, "Wrong amount"
    assert (
        txn.events["UpdatePoolOI"]["isIncreased"]
        and txn.events["UpdatePoolOI"]["interest"] == b.total_fee
    ), "Wrong event"
    assert tmi_after == tmi_before + b.total_fee, "Wrong total market interest"
    # print_oi()

    # Max Trade Size < trade size & allowed partial fill false
    queue_id += 1
    trade_params = b.trade_params
    trade_params[0] = int(3e6)  # total_fee
    trade_params[-5] = False  # allow_partial_fill
    trade_params = b.get_trade_params(
        user, one_ct, True, params=trade_params, queue_id=queue_id
    )[:-1]
    max_market_oi = market_oi_config_contract.getMaxMarketOI(
        b.binary_options.totalMarketOI()
    )
    chain.snapshot()
    txn = b.router.openTrades([*trade_params], {"from": b.bot})
    chain.revert()
    assert txn.events["CancelTrade"]["reason"] == "O29", "Wrong reason"

    # Max Trade Size < trade size
    trade_params = b.trade_params
    trade_params[0] = int(3e6)  # total_fee
    trade_params[-5] = True  # allow_partial_fill
    trade_params = b.get_trade_params(
        user, one_ct, True, params=trade_params, queue_id=queue_id
    )[:-1]
    max_market_oi = market_oi_config_contract.getMaxMarketOI(
        b.binary_options.totalMarketOI()
    )
    _, _, _, _, _, tmi_before = get_oi()
    txn = b.router.openTrades([*trade_params], {"from": b.bot})
    _, _, _, _, _, tmi_after = get_oi()
    option_id = txn.events["OpenTrade"]["optionId"]
    option = b.binary_options.options(option_id)

    print(option)

    assert option[-2] == max_market_oi, "Wrong fee"
    # assert option[2] == (max_market_oi * 1e6) // uint_fee, "Wrong amount"
    x = option[2] / 1e6
    y = ((max_market_oi * 1e6) // uint_fee) / 1e6
    assert math.isclose(x, y, abs_tol=5e-6)
    assert (
        txn.events["UpdatePoolOI"]["isIncreased"]
        and txn.events["UpdatePoolOI"]["interest"] == max_market_oi
    ), "Wrong event"
    assert tmi_after == tmi_before + max_market_oi, "Wrong total market interest"
    # print_oi()

    # Market oi cap < trade size + total market oi
    queue_id += 1
    trade_params = b.trade_params
    trade_params[0] = int(2e6)  # total_fee
    trade_params = b.get_trade_params(
        user, one_ct, True, params=trade_params, queue_id=queue_id
    )[:-1]
    max_market_oi = market_oi_config_contract.getMaxMarketOI(
        b.binary_options.totalMarketOI()
    )
    _, _, _, _, _, tmi_before = get_oi()
    txn = b.router.openTrades([*trade_params], {"from": b.bot})
    _, _, _, _, _, tmi_after = get_oi()
    option_id = txn.events["OpenTrade"]["optionId"]
    option = b.binary_options.options(option_id)

    assert option[-2] == max_market_oi, "Wrong fee"
    assert option[2] == (max_market_oi * 1e6) // uint_fee, "Wrong amount"
    assert (
        txn.events["UpdatePoolOI"]["isIncreased"]
        and txn.events["UpdatePoolOI"]["interest"] == max_market_oi
    ), "Wrong event"
    print(option)
    assert tmi_after == tmi_before + max_market_oi, "Wrong total market interest"
    # print_oi()

    # Buying after the market oi cap is reached should fail
    queue_id += 1
    trade_params = b.trade_params
    trade_params[0] = int(2e6)  # total_fee
    chain.sleep(1)
    trade_params = b.get_trade_params(
        user, one_ct, True, params=trade_params, queue_id=queue_id
    )[:-1]
    max_market_oi = market_oi_config_contract.getMaxMarketOI(
        b.binary_options.totalMarketOI()
    )
    txn = b.router.openTrades([*trade_params], {"from": b.bot})
    assert txn.events["CancelTrade"]["reason"] == "O36", "Wrong reason"
    # print_oi()

    # Buying from another market should succeed
    trade_params = b.trade_params
    trade_params[2] = b.binary_options_2.address
    max_market_oi = market_oi_config_contract.getMaxMarketOI(
        b.binary_options_2.totalMarketOI()
    )
    option_id, queueId, trade_params, txn = b.create(
        user,
        one_ct,
        params=trade_params,
        queue_id=queue_id,
        options_contact=b.binary_options_2,
    )
    option = b.binary_options_2.options(option_id)

    assert option[-2] == max_market_oi, "Wrong fee"
    # assert option[2] == (max_market_oi * 1e6) // uint_fee, "Wrong amount"
    x = option[2] / 1e6
    y = ((max_market_oi * 1e6) // uint_fee) / 1e6
    assert math.isclose(x, y, abs_tol=5e-6)

    assert (
        txn.events["UpdatePoolOI"]["isIncreased"]
        and txn.events["UpdatePoolOI"]["interest"] == max_market_oi
    ), "Wrong event"
    # print_oi()


def test_exceution(close, contracts, accounts, chain):
    b, params, closing_price, user, optionId = close
    current_time = chain.time()
    expiration_time = b.binary_options.options(optionId)[-3]
    option = b.binary_options.options(optionId)

    # SHould fail if the price timestamp is not equal to expiration
    close_params = [
        *params,
        get_publisher_signature(b, closing_price, current_time),
    ]
    txn = b.router.executeOptions([close_params], {"from": b.bot})
    assert txn.events["FailUnlock"]["reason"] == "Router: Wrong price"

    # SHould fail if market direction is wrong
    params[3] = not b.is_above
    close_params = [
        *params,
        get_publisher_signature(b, closing_price, expiration_time),
    ]
    txn = b.router.executeOptions([close_params], {"from": b.bot})
    assert txn.events["FailUnlock"]["reason"] == "Router: Wrong market direction"

    # SHould fail before the expiration time
    params[3] = b.is_above
    close_params = [*params, get_publisher_signature(b, closing_price, expiration_time)]
    txn = b.router.executeOptions([close_params], {"from": b.bot})
    assert txn.events["FailUnlock"]["reason"] == "Router: Wrong closing time"

    # Time travel to the expiration time
    chain.sleep(expiration_time - chain.time() + 1)

    # Should succeed after the time lapse
    chain.snapshot()
    txn = b.router.executeOptions([close_params], {"from": b.bot})
    chain.revert()
    assert txn.events["Exercise"]["id"] == optionId, "Wrong id"
    assert len(txn.events["Transfer"]) == 3, "Wrong transfer"
    assert (
        txn.events["Transfer"][1]["value"] == txn.events["Transfer"][0]["value"]
    ), "Wrong payout"
    assert txn.events["Transfer"][1]["to"] == user, "Wrong transfer"
    assert (
        txn.events["Transfer"][1]["from"] == txn.events["Transfer"][0]["to"]
    ), "Wrong transfer"
    assert txn.events["LpLoss"]["amount"] == option[2] - option[4], "Wrong lp loss"

    # Should succeed even after one_ct change
    _one_ct = accounts.add()
    b.reregister(user, _one_ct)

    txn = b.router.executeOptions([close_params], {"from": b.bot})
    assert txn.events["Exercise"]["id"] == optionId, "Wrong id"


def test_early_close(early_close, contracts, accounts, chain):
    b, close_params, option, user, optionId = early_close

    # Early close not disabled should fail
    txn = b.router.closeAnytime([close_params], {"from": b.bot})
    assert txn.events["FailUnlock"]["optionId"] == optionId, "Wrong id"
    assert (
        txn.events["FailUnlock"]["reason"] == "Router: Early close is not allowed"
    ), "Wrong reason"

    # Early close before threshold should fail
    b.binary_options_config.toggleEarlyClose()
    b.binary_options_config.setEarlyCloseThreshold(300)
    txn = b.router.closeAnytime([close_params], {"from": b.bot})
    assert txn.events["FailUnlock"]["optionId"] == optionId, "Wrong id"
    assert (
        txn.events["FailUnlock"]["reason"] == "Router: Early close is not allowed"
    ), "Wrong reason"

    # Early close after threshold should succeed
    chain.sleep(300 + 1)
    chain.snapshot()
    txn = b.router.closeAnytime([close_params], {"from": b.bot})
    chain.revert()
    assert txn.events["Exercise"]["id"] == optionId, "Wrong id"
    assert txn.events["Transfer"][0]["value"] == option[2], "Wrong transfer from pool"
    assert len(txn.events["Transfer"]) == 4, "Wrong transfer"
    assert txn.events["Transfer"][1]["value"] < option[2], "Wrong payout"
    assert txn.events["Transfer"][1]["to"] == user, "Wrong transfer"
    assert (
        txn.events["Transfer"][1]["from"] == txn.events["Transfer"][0]["to"]
    ), "Wrong transfer"
    assert (
        txn.events["Transfer"][2]["value"]
        == option[2] - txn.events["Transfer"][1]["value"]
    ), "Wrong transfer to pool"
    assert txn.events["Transfer"][2]["to"] == b.binary_pool, "Wrong transfer"
    assert (
        txn.events["LpProfit"]["amount"]
        == option[4] - txn.events["Transfer"][1]["value"]
    ), "Wrong lp profit"

    # Wrong onc_ct should fail
    _one_ct = accounts.add()
    b.reregister(user, _one_ct)

    txn = b.router.closeAnytime([close_params], {"from": b.bot})
    assert (
        txn.events["FailUnlock"]["reason"] == "Router: User signature didn't match"
    ), "Wrong reson"

    # Changing one_ct after trade has opened
    new_one_ct = accounts.add()
    signature_time = int(chain.time())
    signature = b.get_close_signature(
        b.binary_options, signature_time, close_params[0][0], new_one_ct.private_key
    )
    b.registrar.deregisterAccount(
        user.address, b.get_deregister_signature(user), {"from": b.owner}
    )
    register_params = [
        new_one_ct.address,
        b.get_register_signature(
            new_one_ct,
            user,
        ),
        True,
    ]
    chain.sleep(1)
    close_params[-1] = (signature, signature_time)
    close_params[1] = register_params

    txn = b.router.closeAnytime([close_params], {"from": b.bot})
    assert txn.events["RegisterAccount"], "Wrong events"
    assert txn.events["RegisterAccount"]["user"] == user, "Wrong user"
    assert txn.events["RegisterAccount"]["oneCT"] == new_one_ct.address, "Wrong one ct"
    assert txn.events["Exercise"]["id"] == optionId, "Wrong id"
