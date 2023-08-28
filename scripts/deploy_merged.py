import json
import os
import time

import brownie
from brownie import (
    ABDKMath64x64,
    AccountRegistrar,
    Booster,
    BufferBinaryOptions,
    BufferBinaryPool,
    BufferRouter,
    CreationWindow,
    FakeToken,
    Faucet,
    MarketOIConfig,
    OptionMath,
    OptionsConfig,
    OptionStorage,
    PoolOIConfig,
    PoolOIStorage,
    ReferralStorage,
    TraderNFT,
    Validator,
    accounts,
    network,
)
from colorama import Fore, Style
from eth_account import Account
from eth_account.messages import encode_defunct

from .utility import deploy_contract, save_flat, transact


def create_accounts():
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
    return all_accounts


def deploy_usdc(
    admin,
    config_setter,
    sf_publisher,
    open_keeper,
    close_keeper,
    revoke_keeper,
    early_close_keeper,
):
    is_testnet_token = False

    router_contract_address = None
    nft_contract_address = None
    pool_address = None
    token_contract_address = None
    option_config_address = None
    options_address = None
    referral_storage_address = None
    faucet_address = None
    option_reader_address = None
    sfd = None
    creation_window_address = None
    max_pool_oi = 75000e6
    referrerTierStep = [4, 10, 16]
    referrerTierDiscount = [int(25e3), int(50e3), int(75e3)]
    nftTierStep = [5, 10, 16, 24]
    lockupPeriod = 600
    account_registrar_address = None
    pool_oi_storage = None
    pool_oi_config = None
    booster = None

    asset_pairs = [
        {
            "token1": "BTC",
            "token2": "USD",
            "full_name": "Bitcoin",
            "asset_category": 1,
            "minFee": int(5e6),
            "platformFee": int(1e5),
            "minPeriod": 60,
            "maxPeriod": 4 * 60 * 60,
            "max_trade_size": int(1000e6),
            "max_market_oi": int(10000e6),
            "is_early_close_allowed": True,
            "early_close_threshold": 60,
        },
        {
            "token1": "ETH",
            "token2": "USD",
            "full_name": "Ethereum",
            "asset_category": 1,
            "minFee": int(5e6),
            "platformFee": int(1e5),
            "minPeriod": 60,
            "maxPeriod": 4 * 60 * 60,
            "max_trade_size": int(1000e6),
            "max_market_oi": int(10000e6),
            "is_early_close_allowed": True,
            "early_close_threshold": 60,
        },
        {
            "token1": "EUR",
            "token2": "USD",
            "full_name": "Euro",
            "asset_category": 0,
            "minFee": int(5e6),
            "platformFee": int(1e5),
            "minPeriod": 60,
            "maxPeriod": 4 * 60 * 60,
            "max_trade_size": int(1000e6),
            "max_market_oi": int(10000e6),
            "is_early_close_allowed": True,
            "early_close_threshold": 60,
        },
        {
            "token1": "GBP",
            "token2": "USD",
            "full_name": "Pound",
            "asset_category": 0,
            "minFee": int(5e6),
            "platformFee": int(1e5),
            "minPeriod": 60,
            "maxPeriod": 4 * 60 * 60,
            "max_trade_size": int(1000e6),
            "max_market_oi": int(10000e6),
            "is_early_close_allowed": True,
            "early_close_threshold": 60,
        },
        {
            "token1": "XAU",
            "token2": "USD",
            "full_name": "Gold",
            "asset_category": 2,
            "minFee": int(5e6),
            "platformFee": int(1e5),
            "minPeriod": 10 * 60,
            "maxPeriod": 4 * 60 * 60,
            "max_trade_size": int(1000e6),
            "max_market_oi": int(10000e6),
            "is_early_close_allowed": False,
            "early_close_threshold": 60,
        },
        {
            "token1": "XAG",
            "token2": "USD",
            "full_name": "Silver",
            "asset_category": 2,
            "minFee": int(5e6),
            "platformFee": int(1e5),
            "minPeriod": 10 * 60,
            "maxPeriod": 4 * 60 * 60,
            "max_trade_size": int(1000e6),
            "max_market_oi": int(10000e6),
            "is_early_close_allowed": False,
            "early_close_threshold": 60,
        },
    ]
    initialLiquidityForTestnet = int(499999.786093e6)

    allow_revert = True
    pool_admin = accounts.add(os.environ["POOL_PK"])
    # admin = accounts.add(os.environ["BFR_PK"])
    # config_setter = accounts.add(os.environ["CONFIG_SETTER_PK"])
    # nft_deployer = accounts.add(os.environ["NFT_DEPLOYER_PRIVATE_KEY"])
    publisher = "0x2156972c36088AA94fAeF84359C75FB4Bb83c745"

    # open_keeper = ""
    # close_keeper = ""
    # revoke_keeper = ""
    # early_close_keeper = ""
    # sf_publisher = ""

    token_contract_address = "0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8"
    sfd = "0x7912BC879a6AE9947b85b203BE47346de56442aB"

    # is_testnet_token = False
    # nft_base_contract_address = "0x53bD6b734F50AC058091077249A40f5351629d05"
    nft_contract_address = "0xf00bBb1Eb631CeE582D95664e341A95547A3491A"
    pool_address = "0x6Ec7B10bF7331794adAaf235cb47a2A292cD9c7e"
    referral_storage_address = "0xFea57B9548cd72D8705e4BB0fa83AA35966D9c29"

    print(pool_admin, admin)
    print(pool_admin.balance() / 1e18, admin.balance() / 1e18)

    initial_balance_admin = admin.balance()
    initial_balance_config_setter = config_setter.balance()
    # ########### Get TokenX ###########
    # if not token_contract_address:
    #     token_contract = deploy_contract(
    #         admin,
    #         network,
    #         FakeToken,
    #         [],
    #     )
    #     token_contract_address = token_contract.address
    # elif network.show_active() != mainnet:
    #     token_contract = FakeToken.at(token_contract_address)

    ####### Deploy Creation window #######
    if not creation_window_address:
        creation_window = deploy_contract(
            admin,
            network,
            CreationWindow,
            [1682287200, 1682711940],  # new
        )
        creation_window_address = creation_window.address

    ####### Deploy Registrar #######
    if not account_registrar_address:
        account_registrar = deploy_contract(
            admin,
            network,
            AccountRegistrar,
            [],
        )
        account_registrar_address = account_registrar.address
    else:
        account_registrar = AccountRegistrar.at(account_registrar_address)

    ####### Deploy Booster #######
    if not booster:
        booster = deploy_contract(
            admin,
            network,
            Booster,
            [nft_contract_address],
        )
        booster = booster.address

    if not pool_oi_storage:
        pool_oi_storage = deploy_contract(admin, network, PoolOIStorage, [])
    else:
        pool_oi_storage = PoolOIStorage.at(pool_oi_storage)

    if not pool_oi_config:
        pool_oi_config = deploy_contract(
            admin, network, PoolOIConfig, [max_pool_oi, pool_oi_storage.address]
        )
    else:
        pool_oi_config = PoolOIConfig.at(pool_oi_config)

    ########### Router ###########

    if not router_contract_address:
        router_contract = deploy_contract(
            admin,
            network,
            BufferRouter,
            [publisher, sf_publisher, admin, account_registrar.address],
        )
        router_contract_address = router_contract.address

        # router_contract_address = "0xB1be98504is_testnet_tokenD40d3644ef069A2543536a8Eb11dD87"
        # router_contract = BufferRouter.at(router_contract_address)

        for keeper in [open_keeper, close_keeper, revoke_keeper, early_close_keeper]:
            transact(
                router_contract.address,
                router_contract.abi,
                "setKeeper",
                keeper,
                True,
                sender=admin,
            )
    else:
        router_contract = BufferRouter.at(router_contract_address)

    ########### Get pool ###########

    if pool_address:
        pool = BufferBinaryPool.at(pool_address)
    else:
        pool = deploy_contract(
            pool_admin,
            network,
            BufferBinaryPool,
            [token_contract_address, lockupPeriod],
        )
        pool_address = pool.address

    ########### Get NFT ###########
    # if not nft_contract_address:
    #     nft_contract = deploy_contract(
    #         nft_deployer,
    #         network,
    #         TraderNFT,
    #         [nft_base_contract_address],
    #     )
    #     nft_contract_address = nft_contract.address
    # else:
    #     nft_contract = TraderNFT.at(nft_contract_address)

    option_storage = deploy_contract(admin, network, OptionStorage, [])

    ADMIN_ROLE = account_registrar.ADMIN_ROLE()

    transact(
        account_registrar.address,
        account_registrar.abi,
        "grantRole",
        ADMIN_ROLE,
        router_contract_address,
        sender=admin,
    )
    transact(
        account_registrar.address,
        account_registrar.abi,
        "grantRole",
        ADMIN_ROLE,
        admin.address,
        sender=admin,
    )

    all_options = []
    all_configs = []
    for asset_pair in asset_pairs:
        pair = asset_pair["token1"] + asset_pair["token2"]

        ########### Get Options Config ###########

        if option_config_address:
            option_config = OptionsConfig.at(option_config_address)
        else:
            option_config = deploy_contract(
                config_setter,
                network,
                OptionsConfig,
                [
                    pool_address,
                ],
            )
            transact(
                option_config.address,
                option_config.abi,
                "setSettlementFeeDisbursalContract",
                sfd,
                sender=config_setter,
            )
            transact(
                option_config.address,
                option_config.abi,
                "setBoosterContract",
                booster,
                sender=config_setter,
            )

            if asset_pair["asset_category"] != 1:
                transact(
                    option_config.address,
                    option_config.abi,
                    "setCreationWindowContract",
                    creation_window_address,
                    sender=config_setter,
                )

        ########### Deploy referral storage ###########
        referral_storage = None
        if referral_storage_address:
            referral_storage = ReferralStorage.at(referral_storage_address)
        else:
            referral_storage = deploy_contract(admin, network, ReferralStorage, [])
            referral_storage_address = referral_storage.address
            transact(
                referral_storage.address,
                referral_storage.abi,
                "setConfigure",
                referrerTierStep,
                referrerTierDiscount,
                sender=admin,
            )

        ########### Deploy Options ###########
        if options_address:
            options = BufferBinaryOptions.at(options_address)

        else:
            options = deploy_contract(
                admin,
                network,
                BufferBinaryOptions,
                [],
            )
            # save_flat(BufferBinaryOptions, "BufferBinaryOptions")
            # if is_testnet_token:
            #     transact(
            #         token_contract.address,
            #         token_contract.abi,
            #         "approveAddress",
            #         options.address,
            #         sender=admin,
            #     )

        # option_storage = deploy_contract(admin, network, OptionStorage, [])
        market_oi_config = deploy_contract(
            admin,
            network,
            MarketOIConfig,
            [
                asset_pair["max_market_oi"],
                asset_pair["max_trade_size"],
                options.address,
            ],
        )
        ########### Deploy Faucet ###########
        # if not faucet_address and network.show_active() != mainnet:
        #     faucet = deploy_contract(
        #         admin,
        #         network,
        #         Faucet,
        #         [token_contract_address, admin.address, 1683475200],
        #     )
        #     transact(
        #         token_contract.address,
        #         token_contract.abi,
        #         "transfer",
        #         faucet.address,
        #         int(1e12),
        #         sender=admin,
        #     )

        #     if is_testnet_token:
        #         transact(
        #             token_contract.address,
        #             token_contract.abi,
        #             "approveAddress",
        #             faucet.address,
        #             sender=admin,
        #         )
        #     faucet_address = faucet.address
        # elif network.show_active() != mainnet:
        #     faucet = Faucet.at(faucet_address)

        ########### Grant Roles ###########

        OPTION_ISSUER_ROLE = pool.OPTION_ISSUER_ROLE()
        ROUTER_ROLE = options.ROUTER_ROLE()
        UPDATOR_ROLE = pool_oi_storage.UPDATOR_ROLE()
        ADMIN_ROLE = account_registrar.ADMIN_ROLE()

        transact(
            pool.address,
            pool.abi,
            "grantRole",
            OPTION_ISSUER_ROLE,
            options.address,
            sender=pool_admin,
        )
        transact(
            options.address,
            options.abi,
            "grantRole",
            ROUTER_ROLE,
            router_contract_address,
            sender=admin,
        )

        transact(
            pool_oi_storage.address,
            pool_oi_storage.abi,
            "grantRole",
            UPDATOR_ROLE,
            options.address,
            sender=admin,
        )
        transact(
            router_contract.address,
            router_contract.abi,
            "setContractRegistry",
            options.address,
            True,
            sender=admin,
        )

        ########### Approve the max amount ###########

        transact(
            options.address,
            options.abi,
            "initialize",
            token_contract_address,
            pool_address,
            option_config.address,
            referral_storage_address,
            asset_pair["asset_category"],
            asset_pair["token1"],
            asset_pair["token2"],
            sender=admin,
        )

        transact(
            options.address,
            options.abi,
            "approvePoolToTransferTokenX",
            sender=admin,
        )

        ########### Setting configs ###########
        transact(
            option_config.address,
            option_config.abi,
            "setOptionStorageContract",
            option_storage.address,
            sender=config_setter,
        )
        transact(
            option_config.address,
            option_config.abi,
            "setPoolOIStorageContract",
            pool_oi_storage.address,
            sender=config_setter,
        )
        transact(
            option_config.address,
            option_config.abi,
            "setMarketOIConfigContract",
            market_oi_config.address,
            sender=config_setter,
        )
        transact(
            option_config.address,
            option_config.abi,
            "setPoolOIConfigContract",
            pool_oi_config.address,
            sender=config_setter,
        )
        all_options.append(options.address)
        all_configs.append(option_config.address)
        print(f"{Fore.YELLOW}Deployed {pair} at {options.address} {Style.RESET_ALL} ")

        transact(
            option_config.address,
            option_config.abi,
            "setMinFee",
            asset_pair["minFee"],
            sender=config_setter,
        )
        transact(
            option_config.address,
            option_config.abi,
            "setPlatformFee",
            asset_pair["platformFee"],
            sender=config_setter,
        )
        transact(
            option_config.address,
            option_config.abi,
            "setMinPeriod",
            asset_pair["minPeriod"],
            sender=config_setter,
        )
        transact(
            option_config.address,
            option_config.abi,
            "setMaxPeriod",
            asset_pair["maxPeriod"],
            sender=config_setter,
        )
        if asset_pair["is_early_close_allowed"]:
            transact(
                option_config.address,
                option_config.abi,
                "toggleEarlyClose",
                sender=config_setter,
            )
            transact(
                option_config.address,
                option_config.abi,
                "setEarlyCloseThreshold",
                asset_pair["early_close_threshold"],
                sender=config_setter,
            )

    option_data = []
    assets = [x["token1"] + x["token2"] for x in asset_pairs]
    for x, y in zip(all_options, all_configs):
        option_data.append({"option": x, "config": y})

    all_contracts = {
        "pool": pool.address,
        "options": dict(zip(assets, option_data)),
        "referral_storage": referral_storage.address,
        "meta": option_reader_address,
        # "faucet": faucet.address if network.show_active() != mainnet else "",
        "router": router_contract.address,
        "token": token_contract_address,
        "nft": nft_contract_address,
        "creation_window": creation_window_address,
        "sfd": sfd,
        "pool_oi_storage": pool_oi_storage.address,
        "pool_oi_config": pool_oi_config.address,
        # "market_oi_config": market_oi_config.address,
        "option_storage": option_storage.address,
        "account_registrar": account_registrar.address,
        "booster": booster,
    }

    # print(all_contracts)
    print(
        "##### Deployment Expenses: ",
        (initial_balance_admin - admin.balance()) / 1e18,
        (initial_balance_config_setter - config_setter.balance()) / 1e18,
    )
    return all_contracts


def deploy_arb(admin, config_setter, all_usdc_contracts):
    is_testnet_token = False

    router_contract_address = None
    nft_contract_address = None
    pool_address = None
    token_contract_address = None
    option_config_address = None
    options_address = None
    referral_storage_address = None
    faucet_address = None
    option_reader_address = None
    sfd = None
    creation_window_address = None
    max_pool_oi = 50000e18
    lockupPeriod = 600
    account_registrar_address = None
    pool_oi_config = None
    pool_oi_storage = None

    asset_pairs = [
        {
            "token1": "BTC",
            "token2": "USD",
            "full_name": "Bitcoin",
            "asset_category": 1,
            "minFee": int(5e18),
            "platformFee": int(1e17),
            "minPeriod": 60,
            "maxPeriod": 4 * 60 * 60,
            "max_trade_size": int(500e18),
            "max_market_oi": int(5000e18),
            "is_early_close_allowed": True,
            "early_close_threshold": 60,
        },
        {
            "token1": "ETH",
            "token2": "USD",
            "full_name": "Ethereum",
            "asset_category": 1,
            "minFee": int(5e18),
            "platformFee": int(1e17),
            "minPeriod": 60,
            "maxPeriod": 4 * 60 * 60,
            "max_trade_size": int(500e18),
            "max_market_oi": int(5000e18),
            "is_early_close_allowed": True,
            "early_close_threshold": 60,
        },
        {
            "token1": "EUR",
            "token2": "USD",
            "full_name": "Euro",
            "asset_category": 0,
            "minFee": int(5e18),
            "platformFee": int(1e17),
            "minPeriod": 60,
            "maxPeriod": 4 * 60 * 60,
            "max_trade_size": int(500e18),
            "max_market_oi": int(5000e18),
            "is_early_close_allowed": True,
            "early_close_threshold": 60,
        },
        {
            "token1": "GBP",
            "token2": "USD",
            "full_name": "Pound",
            "asset_category": 0,
            "minFee": int(5e18),
            "platformFee": int(1e17),
            "minPeriod": 60,
            "maxPeriod": 4 * 60 * 60,
            "max_trade_size": int(500e18),
            "max_market_oi": int(5000e18),
            "is_early_close_allowed": True,
            "early_close_threshold": 60,
        },
        {
            "token1": "XAU",
            "token2": "USD",
            "full_name": "Gold",
            "asset_category": 2,
            "minFee": int(5e18),
            "platformFee": int(1e17),
            "minPeriod": 10 * 60,
            "maxPeriod": 4 * 60 * 60,
            "max_trade_size": int(500e18),
            "max_market_oi": int(5000e18),
            "is_early_close_allowed": False,
            "early_close_threshold": 60,
        },
        {
            "token1": "XAG",
            "token2": "USD",
            "full_name": "Silver",
            "asset_category": 2,
            "minFee": int(5e18),
            "platformFee": int(1e17),
            "minPeriod": 10 * 60,
            "maxPeriod": 4 * 60 * 60,
            "max_trade_size": int(500e18),
            "max_market_oi": int(5000e18),
            "is_early_close_allowed": False,
            "early_close_threshold": 60,
        },
    ]
    # initialLiquidityForTestnet = int(499999.786093e18)
    # if network.show_active() == "development":
    #     allow_revert = True
    #     pool_admin = accounts.add()
    #     admin = accounts.add()
    #     publisher = accounts.add()
    #     sf_publisher = accounts.add()
    #     open_keeper = accounts[3].address
    #     sfd = accounts[4].address
    #     close_keeper = accounts[5].address
    #     nft_deployer = admin
    #     nft_contract_address = "0xf494F435cb2068559406C77b7271DD7d6aF5B860"

    #     accounts[0].transfer(admin, "10 ether")
    #     accounts[0].transfer(pool_admin, "10 ether")
    #     asset_pair = "ETH-BTC"
    #     is_testnet_token = True
    #     asset_category = 1
    # if network.show_active() in [
    #     "arb-goerli-fork",
    #     "arb-goerli",
    #     "arbitrum-test-nitro",
    # ]:
    #     allow_revert = True
    #     pool_admin = accounts.add(os.environ["POOL_PK"])
    #     admin = accounts.add(os.environ["BFR_PK"])
    #     sfd = "0x32A49a15F8eE598C1EeDc21138DEb23b391f425b"
    #     is_testnet_token = True
    #     pool_oi_storage = ""
    #     pool_oi_config = ""
    #     account_registrar_address = "0x03eA2B7eb5147981Ea12d8101A3fDd59fc02262F"
    #     booster = "0x5F26ABFC8049728A95eDCA2e29Af62385166Cf56"
    #     nft_contract_address = "0xf494F435cb2068559406C77b7271DD7d6aF5B860"
    #     router_contract_address = "0xeacA681888D0BDA1D055785596e00FDD2d7e0F4F"
    #     referral_storage_address = "0x38653C1d41b8aC02b2Ca2753452E1ad90E12A270"
    #     creation_window_address = "0x72b9de12C4FBBAc17f3394F7EA3aDE315d83C7c1"
    #     config_setter = accounts.add(os.environ["CONFIG_SETTER_PK"])

    # if network.show_active() == mainnet:
    allow_revert = True
    pool_admin = accounts.add(os.environ["POOL_PK"])
    # admin = accounts.add(os.environ["BFR_PK"])
    # config_setter = accounts.add(os.environ["CONFIG_SETTER_PK"])

    token_contract_address = "0x912CE59144191C1204E64559FE8253a0e49E6548"
    sfd = "0x8480AD5f92A4B4e3a891454e94505666B0cd1858"

    decimals = 6
    is_testnet_token = False
    # nft_contract_address = "0xf00bBb1Eb631CeE582D95664e341A95547A3491A"
    pool_address = "0xaE0628C88EC6C418B3F5C005f804E905f8123833"
    router_contract_address = all_usdc_contracts["router"]
    referral_storage_address = "0xFea57B9548cd72D8705e4BB0fa83AA35966D9c29"
    creation_window_address = all_usdc_contracts["creation_window"]
    account_registrar_address = all_usdc_contracts["account_registrar"]
    booster = all_usdc_contracts["booster"]

    print(pool_admin, admin)
    print(pool_admin.balance() / 1e18, admin.balance() / 1e18)

    initial_balance_admin = admin.balance()
    initial_balance_config_setter = config_setter.balance()

    # ########### Get TokenX ###########
    # if not token_contract_address:
    #     token_contract = deploy_contract(
    #         admin,
    #         network,
    #         FakeToken,
    #         [],
    #     )
    #     token_contract_address = token_contract.address
    # elif network.show_active() != mainnet:
    #     token_contract = FakeToken.at(token_contract_address)

    ####### Deploy Registrar #######
    if not account_registrar_address:
        account_registrar = deploy_contract(
            admin,
            network,
            AccountRegistrar,
            [],
        )
        account_registrar_address = account_registrar.address
    else:
        account_registrar = AccountRegistrar.at(account_registrar_address)
    if not pool_oi_storage:
        pool_oi_storage = deploy_contract(admin, network, PoolOIStorage, [])
    else:
        pool_oi_storage = PoolOIStorage.at(pool_oi_storage)

    if not pool_oi_config:
        pool_oi_config = deploy_contract(
            admin, network, PoolOIConfig, [max_pool_oi, pool_oi_storage.address]
        )
    else:
        pool_oi_config = PoolOIConfig.at(pool_oi_config)

    ########### Router ###########

    router_contract = BufferRouter.at(router_contract_address)
    # if is_testnet_token:
    #     transact(
    #         token_contract.address,
    #         token_contract.abi,
    #         "approveAddress",
    #         router_contract_address,
    #         sender=admin,
    #     )
    #     transact(
    #         token_contract.address,
    #         token_contract.abi,
    #         "approveAddress",
    #         admin.address,
    #         sender=admin,
    #     )
    #     transact(
    #         token_contract.address,
    #         token_contract.abi,
    #         "approveAddress",
    #         sfd,
    #         sender=admin,
    #     )

    ########### Get pool ###########

    if pool_address:
        pool = BufferBinaryPool.at(pool_address)
    else:
        pool = deploy_contract(
            pool_admin,
            network,
            BufferBinaryPool,
            [token_contract_address, lockupPeriod],
        )
        pool_address = pool.address
        # if is_testnet_token:
        #     transact(
        #         token_contract.address,
        #         token_contract.abi,
        #         "approveAddress",
        #         pool_address,
        #         sender=admin,
        #     )
        #     transact(
        #         token_contract.address,
        #         token_contract.abi,
        #         "approve",
        #         pool_address,
        #         initialLiquidityForTestnet,
        #         sender=admin,
        #     )
        #     transact(
        #         pool.address,
        #         pool.abi,
        #         "provide",
        #         initialLiquidityForTestnet,
        #         0,
        #         sender=admin,
        #     )
    option_storage = OptionStorage.at(all_usdc_contracts["option_storage"])

    # ADMIN_ROLE = account_registrar.ADMIN_ROLE()

    # transact(
    #     account_registrar.address,
    #     account_registrar.abi,
    #     "grantRole",
    #     ADMIN_ROLE,
    #     router_contract_address,
    #     sender=admin,
    # )
    # transact(
    #     account_registrar.address,
    #     account_registrar.abi,
    #     "grantRole",
    #     ADMIN_ROLE,
    #     admin.address,
    #     sender=admin,
    # )

    all_options = []
    all_configs = []
    for asset_pair in asset_pairs:
        pair = asset_pair["token1"] + asset_pair["token2"]

        ########### Get Options Config ###########

        if option_config_address:
            option_config = OptionsConfig.at(option_config_address)
        else:
            option_config = deploy_contract(
                config_setter,
                network,
                OptionsConfig,
                [
                    pool_address,
                ],
            )
            transact(
                option_config.address,
                option_config.abi,
                "setSettlementFeeDisbursalContract",
                sfd,
                sender=config_setter,
            )
            transact(
                option_config.address,
                option_config.abi,
                "setBoosterContract",
                booster,
                sender=config_setter,
            )

            if asset_pair["asset_category"] != 1:
                transact(
                    option_config.address,
                    option_config.abi,
                    "setCreationWindowContract",
                    creation_window_address,
                    sender=config_setter,
                )

        ########### Deploy Options ###########
        if options_address:
            options = BufferBinaryOptions.at(options_address)

        else:
            options = deploy_contract(
                admin,
                network,
                BufferBinaryOptions,
                [],
            )
            # save_flat(BufferBinaryOptions, "BufferBinaryOptions")
            # if is_testnet_token:
            #     transact(
            #         token_contract.address,
            #         token_contract.abi,
            #         "approveAddress",
            #         options.address,
            #         sender=admin,
            #     )
        market_oi_config = deploy_contract(
            admin,
            network,
            MarketOIConfig,
            [
                asset_pair["max_market_oi"],
                asset_pair["max_trade_size"],
                options.address,
            ],
        )
        ########### Deploy Faucet ###########
        # if not faucet_address and network.show_active() != mainnet:
        #     faucet = deploy_contract(
        #         admin,
        #         network,
        #         Faucet,
        #         [token_contract_address, admin.address, 1683475200],
        #     )

        #     # if is_testnet_token:
        #     #     transact(
        #     #         token_contract.address,
        #     #         token_contract.abi,
        #     #         "approveAddress",
        #     #         faucet.address,
        #     #         sender=admin,
        #     #     )
        #     faucet_address = faucet.address
        # elif network.show_active() != mainnet:
        #     faucet = Faucet.at(faucet_address)

        ########### Grant Roles ###########

        OPTION_ISSUER_ROLE = pool.OPTION_ISSUER_ROLE()
        ROUTER_ROLE = options.ROUTER_ROLE()
        UPDATOR_ROLE = pool_oi_storage.UPDATOR_ROLE()
        ADMIN_ROLE = account_registrar.ADMIN_ROLE()

        transact(
            pool.address,
            pool.abi,
            "grantRole",
            OPTION_ISSUER_ROLE,
            options.address,
            sender=pool_admin,
        )
        transact(
            options.address,
            options.abi,
            "grantRole",
            ROUTER_ROLE,
            router_contract_address,
            sender=admin,
        )

        transact(
            pool_oi_storage.address,
            pool_oi_storage.abi,
            "grantRole",
            UPDATOR_ROLE,
            options.address,
            sender=admin,
        )
        transact(
            router_contract.address,
            router_contract.abi,
            "setContractRegistry",
            options.address,
            True,
            sender=admin,
        )

        ########### Approve the max amount ###########

        transact(
            options.address,
            options.abi,
            "initialize",
            token_contract_address,
            pool_address,
            option_config.address,
            referral_storage_address,
            asset_pair["asset_category"],
            asset_pair["token1"],
            asset_pair["token2"],
            sender=admin,
        )

        transact(
            options.address,
            options.abi,
            "approvePoolToTransferTokenX",
            sender=admin,
        )

        ########### Setting configs ###########
        transact(
            option_config.address,
            option_config.abi,
            "setOptionStorageContract",
            option_storage.address,
            sender=config_setter,
        )
        transact(
            option_config.address,
            option_config.abi,
            "setPoolOIStorageContract",
            pool_oi_storage.address,
            sender=config_setter,
        )
        transact(
            option_config.address,
            option_config.abi,
            "setMarketOIConfigContract",
            market_oi_config.address,
            sender=config_setter,
        )
        transact(
            option_config.address,
            option_config.abi,
            "setPoolOIConfigContract",
            pool_oi_config.address,
            sender=config_setter,
        )
        all_options.append(options.address)
        all_configs.append(option_config.address)
        print(f"{Fore.YELLOW}Deployed {pair} at {options.address} {Style.RESET_ALL} ")
        transact(
            option_config.address,
            option_config.abi,
            "setMinFee",
            asset_pair["minFee"],
            sender=config_setter,
        )
        transact(
            option_config.address,
            option_config.abi,
            "setPlatformFee",
            asset_pair["platformFee"],
            sender=config_setter,
        )
        transact(
            option_config.address,
            option_config.abi,
            "setMinPeriod",
            asset_pair["minPeriod"],
            sender=config_setter,
        )
        transact(
            option_config.address,
            option_config.abi,
            "setMaxPeriod",
            asset_pair["maxPeriod"],
            sender=config_setter,
        )
        if asset_pair["is_early_close_allowed"]:
            transact(
                option_config.address,
                option_config.abi,
                "toggleEarlyClose",
                sender=config_setter,
            )
            transact(
                option_config.address,
                option_config.abi,
                "setEarlyCloseThreshold",
                asset_pair["early_close_threshold"],
                sender=config_setter,
            )

    option_data = []
    assets = [x["token1"] + x["token2"] for x in asset_pairs]
    for x, y in zip(all_options, all_configs):
        option_data.append({"option": x, "config": y})

    all_contracts = {
        "pool": pool.address,
        "options": dict(zip(assets, option_data)),
        "meta": option_reader_address,
        # "faucet": faucet.address if network.show_active() != mainnet else "",
        "router": router_contract.address,
        "token": token_contract_address,
        "nft": nft_contract_address,
        "creation_window": creation_window_address,
        "sfd": sfd,
        "pool_oi_storage": pool_oi_storage.address,
        "pool_oi_config": pool_oi_config.address,
        # "market_oi_config": market_oi_config.address,
        "option_storage": option_storage.address,
        "account_registrar": account_registrar.address,
        "booster": booster,
    }

    # print(all_contracts)
    print(
        "##### Deployment Expenses: ",
        (initial_balance_admin - admin.balance()) / 1e18,
        (initial_balance_config_setter - config_setter.balance()) / 1e18,
    )
    return all_contracts


def main():
    # all_accounts = create_accounts()
    all_accounts = {
        "open_keeper": {
            "pk": "0x4f2b62e846742a444addc49581dfc31c430be5e2d14fa378ad8e05ff65f5ddf7",
            "address": "0x131489B68FeB559Ede33A98646C92c1057BE506f",
            "balance": 1.0,
        },
        "close_keeper": {
            "pk": "0xb8fe56ac870471767e822c6f09eba7163a73533d5922e126059bce91d6a8f8b9",
            "address": "0x0C1c497355bf4557f2A71D36170751A9f8b53Bb3",
            "balance": 1.0,
        },
        "revoke_keeper": {
            "pk": "0xab47b775b50961ecf7b63ca708b84cfcc96e1a9201ab25c02c3f70ca2af9edbb",
            "address": "0xF7Dba515a8376a82eD9f081ad90dfcDa0Cd7e518",
            "balance": 1.0,
        },
        "early_close_keeper": {
            "pk": "0x0053b8d409e4e0fe5ee05b8ed4debdd885a469c9c83994be10af05e37152ca94",
            "address": "0x44c708C64CC47ace0a18610AE2BEa135d5488468",
            "balance": 1.0,
        },
        "sf_publisher": {
            "pk": "0x7179a0d74429fba05a7523f8a5de7dfa0928573eb45aab8615485b6ca30bd00d",
            "address": "0xad9176c65E4d2b98c0189a8d0E1a0A8082DC99de",
            "balance": 0.0,
        },
        "config_setter": {
            "pk": "0x4aba9cc2d8031a898cc17b69b6ff3766854427ebdcd6c6c86da7f9da2ea9c9eb",
            "address": "0xcB63C24407e87D3F48D3420E9dfFBc6D5b23a46D",
            "balance": 0.5,
        },
        "admin": {
            "pk": "0xdbeab862209b607af136fba14d16c63a5e2e47b306c3ed52d2f1e80b1af0cf14",
            "address": "0xe76c1719CcD0d4988E28a910eb801aDDB0366EA3",
            "balance": 1.0,
        },
    }

    all_usdc_contracts = deploy_usdc(
        admin=accounts.add(all_accounts["admin"]["pk"]),
        config_setter=accounts.add(all_accounts["config_setter"]["pk"]),
        sf_publisher=all_accounts["sf_publisher"]["address"],
        open_keeper=all_accounts["open_keeper"]["address"],
        close_keeper=all_accounts["close_keeper"]["address"],
        revoke_keeper=all_accounts["revoke_keeper"]["address"],
        early_close_keeper=all_accounts["early_close_keeper"]["address"],
    )
    all_arb_contracts = deploy_arb(
        admin=accounts.add(all_accounts["admin"]["pk"]),
        config_setter=accounts.add(all_accounts["config_setter"]["pk"]),
        all_usdc_contracts=all_usdc_contracts,
    )
    print("all_accounts")

    with open("all_accounts.json", "w") as outfile:
        json.dump(all_accounts, outfile, indent=4, sort_keys=True)

    print(
        all_accounts["config_setter"],
        all_accounts["sf_publisher"],
        all_accounts["open_keeper"],
        all_accounts["close_keeper"],
        all_accounts["revoke_keeper"],
        all_accounts["early_close_keeper"],
    )
    print("all_usdc_contracts")
    with open("all_usdc_contracts.json", "w") as outfile:
        json.dump(all_usdc_contracts, outfile, indent=4, sort_keys=True)

    print(all_usdc_contracts)

    print("all_arb_contracts")
    with open("all_arb_contracts.json", "w") as outfile:
        json.dump(all_arb_contracts, outfile, indent=4, sort_keys=True)

    print(all_arb_contracts)

    fe_config = {
        "referral_storage": all_usdc_contracts["referral_storage"],
        "router": all_usdc_contracts["router"],
        "creation_window": all_usdc_contracts["creation_window"],
        "signer_manager": all_usdc_contracts["account_registrar"],
        "booster": all_usdc_contracts["booster"],
        "poolsInfo": {
            all_usdc_contracts["pool"]: {
                "tokenAddress": all_usdc_contracts["token"],
                "faucet": None,
                "decimals": 6,
                "token": "USDC",
                "is_pol": False,
            },
            all_arb_contracts["pool"]: {
                "tokenAddress": all_arb_contracts["token"],
                "faucet": None,
                "decimals": 18,
                "token": "ARB",
                "is_pol": False,
            },
        },
    }

    # save fe_config as json

    print(json.dumps(fe_config, indent=4, sort_keys=True))

    with open("fe_config.json", "w") as outfile:
        json.dump(fe_config, outfile, indent=4, sort_keys=True)
