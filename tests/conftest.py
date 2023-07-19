#!/usr/bin/python3

import time
from enum import IntEnum

import pytest

ONE_DAY = 86400


class OptionType(IntEnum):
    ALL = 0
    PUT = 1
    CALL = 2
    NONE = 3


@pytest.fixture(scope="function", autouse=True)
def isolate(fn_isolation):
    # perform a chain rewind after completing each test, to ensure proper isolation
    # https://eth-brownie.readthedocs.io/en/v1.10.3/tests-pytest-intro.html#isolation-fixtures
    pass


@pytest.fixture(scope="module")
def contracts(
    accounts,
    FakeUSDC,
    BFR,
    BufferBinaryPool,
    BufferBinaryOptions,
    OptionsConfig,
    BufferRouter,
    FakeTraderNFT,
    ReferralStorage,
    CreationWindow,
    ABDKMath64x64,
    OptionMath,
    Validator,
    PoolOIConfig,
    PoolOIStorage,
    OptionStorage,
    MarketOIConfig,
    AccountRegistrar,
    Booster,
):
    publisher = accounts.add()
    sf_publisher = accounts.add()
    admin = accounts.add()
    ibfr_contract = BFR.deploy({"from": accounts[0]})
    sfd = accounts.add()
    tokenX = FakeUSDC.deploy({"from": accounts[0]})
    ABDKMath64x64.deploy({"from": accounts[0]})
    OptionMath.deploy({"from": accounts[0]})
    validator = Validator.deploy({"from": accounts[0]})
    creation_window = CreationWindow.deploy(
        1682269200, 1682701200, {"from": accounts[0]}
    )
    binary_pool_atm = BufferBinaryPool.deploy(
        tokenX.address, 600, {"from": accounts[0]}
    )
    OPTION_ISSUER_ROLE = binary_pool_atm.OPTION_ISSUER_ROLE()
    registrar = AccountRegistrar.deploy({"from": accounts[0]})

    router = BufferRouter.deploy(
        publisher, sf_publisher, admin, registrar.address, {"from": accounts[0]}
    )
    ADMIN_ROLE = registrar.ADMIN_ROLE()
    registrar.grantRole(
        ADMIN_ROLE,
        router.address,
        {"from": accounts[0]},
    )
    trader_nft = FakeTraderNFT.deploy(accounts[9], {"from": accounts[0]})
    booster = Booster.deploy(trader_nft.address, {"from": accounts[0]})
    booster.setConfigure([20, 40, 60, 80], {"from": accounts[0]})
    booster.setPrice(1e6, {"from": accounts[0]})
    booster.setBoostPercentage(100, {"from": accounts[0]})

    print("############### Binary ATM Options 1 #################")
    binary_options_config_atm = OptionsConfig.deploy(
        binary_pool_atm.address,
        {"from": accounts[0]},
    )
    referral_contract = ReferralStorage.deploy({"from": accounts[0]})

    binary_european_options_atm = BufferBinaryOptions.deploy({"from": accounts[0]})
    binary_european_options_atm.initialize(
        tokenX.address,
        binary_pool_atm.address,
        binary_options_config_atm.address,
        referral_contract.address,
        1,
        "ETH",
        "BTC",
        {"from": accounts[0]},
    )
    market_oi_config = MarketOIConfig.deploy(
        10e6, 2e6, binary_european_options_atm.address, {"from": accounts[0]}
    )
    option_storage = OptionStorage.deploy({"from": accounts[0]})
    pool_oi_storage = PoolOIStorage.deploy({"from": accounts[0]})
    pool_oi_config = PoolOIConfig.deploy(
        12e6, pool_oi_storage.address, {"from": accounts[0]}
    )

    binary_options_config_atm.setSettlementFeeDisbursalContract(
        sfd,
        {"from": accounts[0]},
    )
    binary_options_config_atm.setCreationWindowContract(
        creation_window.address, {"from": accounts[0]}
    )
    binary_options_config_atm.setBoosterContract(booster.address, {"from": accounts[0]})

    binary_european_options_atm.approvePoolToTransferTokenX(
        {"from": accounts[0]},
    )
    binary_pool_atm.grantRole(
        OPTION_ISSUER_ROLE,
        binary_european_options_atm.address,
        {"from": accounts[0]},
    )
    booster.grantRole(
        OPTION_ISSUER_ROLE,
        binary_european_options_atm.address,
        {"from": accounts[0]},
    )
    ROUTER_ROLE = binary_european_options_atm.ROUTER_ROLE()
    UPDATOR_ROLE = pool_oi_storage.UPDATOR_ROLE()
    binary_european_options_atm.grantRole(
        ROUTER_ROLE,
        router.address,
        {"from": accounts[0]},
    )
    pool_oi_storage.grantRole(
        UPDATOR_ROLE,
        binary_european_options_atm.address,
        {"from": accounts[0]},
    )

    # bfr_binary_options_config_atm.settraderNFTContract(trader_nft.address)
    referral_contract.setConfigure([2, 4, 6], [25e3, 50e3, 75e3], {"from": accounts[0]})

    binary_options_config_atm.setOptionStorageContract(option_storage.address)
    binary_options_config_atm.setPoolOIStorageContract(pool_oi_storage.address)
    binary_options_config_atm.setMarketOIConfigContract(market_oi_config.address)
    binary_options_config_atm.setPoolOIConfigContract(pool_oi_config.address)
    binary_options_config_atm.setIV(11000)

    binary_european_options_atm_2 = BufferBinaryOptions.deploy(
        {"from": accounts[0]},
    )

    binary_european_options_atm_2.initialize(
        tokenX.address,
        binary_pool_atm.address,
        binary_options_config_atm.address,
        referral_contract.address,
        1,
        "ETH",
        "USD",
    )
    return {
        "tokenX": tokenX,
        "referral_contract": referral_contract,
        "binary_pool_atm": binary_pool_atm,
        "binary_options_config_atm": binary_options_config_atm,
        "binary_european_options_atm": binary_european_options_atm,
        "router": router,
        "trader_nft_contract": trader_nft,
        "ibfr_contract": ibfr_contract,
        "publisher": publisher,
        "settlement_fee_disbursal": sfd,
        "creation_window": creation_window,
        "binary_european_options_atm_2": binary_european_options_atm_2,
        "sf_publisher": sf_publisher,
        "validator": validator,
    }
