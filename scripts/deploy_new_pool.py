import os
import time

import brownie
from brownie import (
    FakeToken,
    BufferBinaryPool,
    BufferBinaryOptions,
    OptionsConfig,
    BufferRouter,
    TraderNFT,
    ReferralStorage,
    CreationWindow,
    ABDKMath64x64,
    OptionMath,
    Validator,
    PoolOIConfig,
    PoolOIStorage,
    OptionStorage,
    MarketOIConfig,
    Faucet,
    AccountRegistrar,
    Booster,
    accounts,
    network,
)
from colorama import Fore, Style
from eth_account import Account
from eth_account.messages import encode_defunct

from .utility import deploy_contract, save_flat, transact


def get_signature(timestamp, token, price, publisher):
    web3 = brownie.network.web3
    key = publisher.private_key
    msg_hash = web3.solidityKeccak(
        ["uint256", "address", "uint256"], [timestamp, token, int(price)]
    )
    signed_message = Account.sign_message(encode_defunct(msg_hash), key)

    def to_32byte_hex(val):
        return web3.toHex(web3.toBytes(val).rjust(32, b"\0"))

    return to_32byte_hex(signed_message.signature)


def main():
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
    mainnet = "arbitrum-main-fork"
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
    initialLiquidityForTestnet = int(499999.786093e18)
    if network.show_active() == "development":
        allow_revert = True
        pool_admin = accounts.add()
        admin = accounts.add()
        publisher = accounts.add()
        sf_publisher = accounts.add()
        open_keeper = accounts[3].address
        sfd = accounts[4].address
        close_keeper = accounts[5].address
        nft_deployer = admin
        nft_contract_address = "0xf494F435cb2068559406C77b7271DD7d6aF5B860"

        accounts[0].transfer(admin, "10 ether")
        accounts[0].transfer(pool_admin, "10 ether")
        asset_pair = "ETH-BTC"
        is_testnet_token = True
        asset_category = 1
    if network.show_active() in [
        "arb-goerli-fork",
        "arb-goerli",
        "arbitrum-test-nitro",
    ]:
        allow_revert = True
        pool_admin = accounts.add(os.environ["POOL_PK"])
        admin = accounts.add(os.environ["BFR_PK"])
        sfd = "0x32A49a15F8eE598C1EeDc21138DEb23b391f425b"
        is_testnet_token = True
        pool_oi_storage = ""
        pool_oi_config = ""
        account_registrar_address = "0x03eA2B7eb5147981Ea12d8101A3fDd59fc02262F"
        booster = "0x5F26ABFC8049728A95eDCA2e29Af62385166Cf56"
        nft_contract_address = "0xf494F435cb2068559406C77b7271DD7d6aF5B860"
        router_contract_address = "0xeacA681888D0BDA1D055785596e00FDD2d7e0F4F"
        referral_storage_address = "0x38653C1d41b8aC02b2Ca2753452E1ad90E12A270"
        creation_window_address = "0x72b9de12C4FBBAc17f3394F7EA3aDE315d83C7c1"
        config_setter = accounts.add(os.environ["CONFIG_SETTER_PK"])

    if network.show_active() == mainnet:
        allow_revert = True
        pool_admin = accounts.add(os.environ["POOL_PK"])
        admin = accounts.add(os.environ["BFR_PK"])
        config_setter = accounts.add(os.environ["CONFIG_SETTER_PK"])

        # print("Funding the keepers")
        # admin.transfer(open_keeper, "0.4 ether")
        # admin.transfer(close_keeper, "0.4 ether")

        token_contract_address = "0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8"
        sfd = "0x9652c3b904fA2f6b9EBFA0713E6DD0a2bF18e383"

        decimals = 6
        is_testnet_token = False
        nft_base_contract_address = "0x53bD6b734F50AC058091077249A40f5351629d05"
        nft_contract_address = "0xf00bBb1Eb631CeE582D95664e341A95547A3491A"
        pool_address = "0x6Ec7B10bF7331794adAaf235cb47a2A292cD9c7e"
        router_contract_address = "0x0e0A1241C9cE6649d5D30134a194BA3E24130305"
        referral_storage_address = "0xFea57B9548cd72D8705e4BB0fa83AA35966D9c29"
        creation_window_address = "0xFea57B9548cd72D8705e4BB0fa83AA35966D9c29"
        # account_registrar_address = "0xFea57B9548cd72D8705e4BB0fa83AA35966D9c29"
        booster = "0xFea57B9548cd72D8705e4BB0fa83AA35966D9c29"

    print(pool_admin, admin)
    print(pool_admin.balance() / 1e18, admin.balance() / 1e18)

    ########### Get TokenX ###########
    if not token_contract_address:
        token_contract = deploy_contract(
            admin,
            network,
            FakeToken,
            [],
        )
        token_contract_address = token_contract.address
    elif network.show_active() != mainnet:
        token_contract = FakeToken.at(token_contract_address)

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
    if is_testnet_token:
        transact(
            token_contract.address,
            token_contract.abi,
            "approveAddress",
            router_contract_address,
            sender=admin,
        )
        transact(
            token_contract.address,
            token_contract.abi,
            "approveAddress",
            admin.address,
            sender=admin,
        )
        transact(
            token_contract.address,
            token_contract.abi,
            "approveAddress",
            sfd,
            sender=admin,
        )

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
        if is_testnet_token:
            transact(
                token_contract.address,
                token_contract.abi,
                "approveAddress",
                pool_address,
                sender=admin,
            )
            transact(
                token_contract.address,
                token_contract.abi,
                "approve",
                pool_address,
                initialLiquidityForTestnet,
                sender=admin,
            )
            transact(
                pool.address,
                pool.abi,
                "provide",
                initialLiquidityForTestnet,
                0,
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
            if is_testnet_token:
                transact(
                    token_contract.address,
                    token_contract.abi,
                    "approveAddress",
                    options.address,
                    sender=admin,
                )
        option_storage = deploy_contract(admin, network, OptionStorage, [])
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
        if not faucet_address and network.show_active() != mainnet:
            faucet = deploy_contract(
                admin,
                network,
                Faucet,
                [token_contract_address, admin.address, 1683475200],
            )

            if is_testnet_token:
                transact(
                    token_contract.address,
                    token_contract.abi,
                    "approveAddress",
                    faucet.address,
                    sender=admin,
                )
            faucet_address = faucet.address
        elif network.show_active() != mainnet:
            faucet = Faucet.at(faucet_address)

        ########### Grant Roles ###########

        OPTION_ISSUER_ROLE = pool.OPTION_ISSUER_ROLE()
        ROUTER_ROLE = options.ROUTER_ROLE()
        UPDATOR_ROLE = pool_oi_storage.UPDATOR_ROLE()
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
            sender=config_setter,
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

    all_contractss = {
        "pool": pool.address,
        "options": dict(zip(assets, option_data)),
        "meta": option_reader_address,
        "faucet": faucet.address if network.show_active() != mainnet else "",
        "router": router_contract.address,
        "token": token_contract_address,
        "nft": nft_contract_address,
        "creation_window": creation_window_address,
        "sfd": sfd,
        "pool_oi_storage": pool_oi_storage.address,
        "pool_oi_config": pool_oi_config.address,
        "market_oi_config": market_oi_config.address,
        "option_storage": option_storage.address,
        "account_registrar": account_registrar.address,
        "booster": booster,
    }

    print(all_contractss)
