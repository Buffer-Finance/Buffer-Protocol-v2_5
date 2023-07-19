from enum import IntEnum
import copy
from brownie import AccountRegistrar, Booster
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

    # Seconf buy should pass
    params[0][2][-1] = False
    txn = b.router.openTrades([*params[:-1]], {"from": b.bot})
    assert txn.events["OpenTrade"]["optionId"] == 1
    assert txn.events["OpenTrade"]["queueId"] == 1
    assert len(txn.events["Approval"]) == 2


def test_lo(init_lo, contracts, accounts, chain):
    b, user, one_ct, trade_params = init_lo
    txn = b.router.openTrades([*trade_params], {"from": b.bot})
    assert txn.events["OpenTrade"]["optionId"] == 0
    assert txn.events["OpenTrade"]["queueId"] == 0


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


def test_early_close(early_close, contracts, accounts, chain):
    b, close_params, option, user = early_close

    # Early close not disabled should fail
    txn = b.router.closeAnytime([close_params], {"from": b.bot})
    assert txn.events["FailUnlock"]["optionId"] == 0, "Wrong id"
    assert (
        txn.events["FailUnlock"]["reason"] == "Router: Early close is not allowed"
    ), "Wrong reason"

    # Early close before threshold should fail
    b.binary_options_config.toggleEarlyClose()
    b.binary_options_config.setEarlyCloseThreshold(300)
    txn = b.router.closeAnytime([close_params], {"from": b.bot})
    assert txn.events["FailUnlock"]["optionId"] == 0, "Wrong id"
    assert (
        txn.events["FailUnlock"]["reason"] == "Router: Early close is not allowed"
    ), "Wrong reason"

    # Early close after threshold should succeed
    chain.sleep(300 + 1)
    txn = b.router.closeAnytime([close_params], {"from": b.bot})
    assert txn.events["Exercise"]["id"] == 0, "Wrong id"
    assert txn.events["Transfer"][0]["value"] < option[2], "Wrong payout"
    assert txn.events["Transfer"][0]["to"] == user, "Wrong user"

    # Wrong onc_ct should fail
    _one_ct = accounts.add()
    b.reregister(user, _one_ct)

    txn = b.router.closeAnytime([close_params], {"from": b.bot})
    assert (
        txn.events["FailUnlock"]["reason"] == "Router: User signature didn't match"
    ), "Wrong reson"


def test_creation_window(init, contracts, accounts, chain):
    b, user, one_ct, _ = init
    period = 5 * 60
    b.check_trading_window(6, 17, 0, period, False)  # Saturday 17:00 (5m)
    b.check_trading_window(0, 15, 0, period, False)  # Sunday 15:00 (5m)
    b.check_trading_window(0, 16, 59, period, False)  # Sunday 16:59 (5m)
    b.check_trading_window(0, 17, 0, period, True)  # Sunday 17:00   (5m)
    b.check_trading_window(0, 21, 59, period, False)  # Sunday 21:59 (5m)
    b.check_trading_window(0, 22, 0, period, False)  # Sunday 22:00  (5m)
    b.check_trading_window(0, 23, 0, period, True)  # Sunday 23:00   (5m)
    b.check_trading_window(0, 23, 0, 23 * 3600, False)  # Sunday 23:00 (23h)
    b.check_trading_window(0, 23, 0, (23 * 3600) - 1, True)  # Sunday 23:00 (22.59)
    b.check_trading_window(1, 21, 30, (30 * 60), False)  # Monday 21:30 (30m)
    b.check_trading_window(1, 21, 30, (30 * 60) - 1, True)  # Monday 21:30 (29.59m)
    b.check_trading_window(1, 22, 0, (30 * 60), False)  # Monday 22:00 (30m)
    b.check_trading_window(1, 23, 0, (2 * 3600), True)  # Monday 23:00 (2h)
    b.check_trading_window(2, 1, 0, (2 * 3600), True)  # Tuesday 1:00 (2h)
    b.check_trading_window(5, 16, 30, (30 * 60), False)  # Friday 16:30 (30m)
    b.check_trading_window(5, 16, 30, (30 * 60) - 1, True)  # Friday 16:30 (29.59m)
    b.check_trading_window(5, 18, 0, (30 * 60), False)  # Friday 18:00 (30m)


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

    assert txn.events["Exercise"]["id"] == 0, "Wrong id"
    assert txn.events["Transfer"][0]["value"] == option[2], "Wrong payout"
    assert txn.events["Transfer"][0]["to"] == user, "Wrong user"

    # Should succeed even after one_ct change
    _one_ct = accounts.add()
    b.reregister(user, _one_ct)

    txn = b.router.executeOptions([close_params], {"from": b.bot})
    assert txn.events["Exercise"]["id"] == 0, "Wrong id"
