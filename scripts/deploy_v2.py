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
    max_pool_oi = 100000e6
    mainnet = "arbitrum-main-fork"
    referrerTierStep = [4, 10, 16]
    referrerTierDiscount = [int(25e3), int(50e3), int(75e3)]
    nftTierStep = [5, 10, 16, 24]
    lockupPeriod = 600
    account_registrar_address = None
    pool_oi_storage = None
    pool_oi_config = None

    asset_pairs = [
        {
            "token1": "BTC",
            "token2": "USD",
            "full_name": "Bitcoin",
            "asset_category": 1,
            "minFee": int(1e6),
            "platformFee": int(1e5),
            "minPeriod": 3 * 60,
            "maxPeriod": 4 * 60 * 60,
            "max_trade_size": int(1000e6),
            "max_market_oi": int(50000e6),
            "is_early_close_allowed": True,
            "early_close_threshold": 60,
        },
        {
            "token1": "ETH",
            "token2": "USD",
            "full_name": "Ethereum",
            "asset_category": 1,
            "minFee": int(1e6),
            "platformFee": int(1e5),
            "minPeriod": 3 * 60,
            "maxPeriod": 4 * 60 * 60,
            "max_trade_size": int(1000e6),
            "max_market_oi": int(50000e6),
            "is_early_close_allowed": True,
            "early_close_threshold": 60,
        },
        {
            "token1": "EUR",
            "token2": "USD",
            "full_name": "Euro",
            "asset_category": 0,
            "minFee": int(1e6),
            "platformFee": int(1e5),
            "minPeriod": 3 * 60,
            "maxPeriod": 4 * 60 * 60,
            "max_trade_size": int(1000e6),
            "max_market_oi": int(50000e6),
            "is_early_close_allowed": True,
            "early_close_threshold": 60,
        },
        {
            "token1": "GBP",
            "token2": "USD",
            "full_name": "Pound",
            "asset_category": 0,
            "minFee": int(1e6),
            "platformFee": int(1e5),
            "minPeriod": 3 * 60,
            "maxPeriod": 4 * 60 * 60,
            "max_trade_size": int(1000e6),
            "max_market_oi": int(50000e6),
            "is_early_close_allowed": True,
            "early_close_threshold": 60,
        },
        {
            "token1": "XAU",
            "token2": "USD",
            "full_name": "Gold",
            "asset_category": 2,
            "minFee": int(1e6),
            "platformFee": int(1e5),
            "minPeriod": 3 * 60,
            "maxPeriod": 4 * 60 * 60,
            "max_trade_size": int(1000e6),
            "max_market_oi": int(50000e6),
            "is_early_close_allowed": True,
            "early_close_threshold": 60,
        },
        {
            "token1": "XAG",
            "token2": "USD",
            "full_name": "Silver",
            "asset_category": 2,
            "minFee": int(1e6),
            "platformFee": int(1e5),
            "minPeriod": 3 * 60,
            "maxPeriod": 4 * 60 * 60,
            "max_trade_size": int(1000e6),
            "max_market_oi": int(50000e6),
            "is_early_close_allowed": True,
            "early_close_threshold": 60,
        },
    ]
    initialLiquidityForTestnet = int(499999.786093e6)
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
        nft_deployer = admin = accounts.add(os.environ["NFT_DEPLOYER_PRIVATE_KEY"])
        publisher = "0x2156972c36088AA94fAeF84359C75FB4Bb83c745"
        sf_publisher = "0xFbEA9559AE33214a080c03c68EcF1D3AF0f58A7D"
        open_keeper = "0x11E7d4D9a78DF6A70D45CFEc6002bA18868b93eB"
        close_keeper = "0x9CDAA8483c75D332796448f0a3062c45151Bc1AC"
        revoke_keeper = ""
        early_close_keeper = ""
        sfd = "0x32A49a15F8eE598C1EeDc21138DEb23b391f425b"
        decimals = 6
        is_testnet_token = True
        nft_base_contract_address = ""
        # pool_oi_storage = "0x69fEC5e3500F161739c428355caeFa09Cf13f4Ae"
        # pool_oi_config = "0x9b308eabe572D5c9132B035476E2ecD5802319ac"
        # account_registrar_address = "0xF93545296A467C50d05eC1A4F356A3415dc20268"
        booster = "0x374E20a66836fC3A0357cC6ecD5B12686f81Db84"
        nft_contract_address = "0xf494F435cb2068559406C77b7271DD7d6aF5B860"
        # token_contract_address = "0x50E345c95a3c1E5085AE886FF4AF05Efa2403c90"
        # pool_address = "0x55Ded741F9c097A95F117a08334D1fBb70A5B05D"
        # router_contract_address = "0x8Fd65D9c94c1cA9ffE48D412Fc2637Ae0176BB03"
        referral_storage_address = "0x7Fd89bE6309Dcb7E147D172E73F04b52cee6313a"
        # option_reader_address = "0x2C1D6877f6C9B31124D803c5Aa9D0518313A042A"
        # faucet_address = "0x8097Fecbb9081191A81DE5295d1D68344EA783fF"
        creation_window_address = "0x72b9de12C4FBBAc17f3394F7EA3aDE315d83C7c1"
        # option_config_address = "0x5f207f0097a794faDD99024370e4D12616A277d1"
        # options_address = "0x68aA6D8e947993Ff2647Ad83ca51dc471478b610"  # ETH-BTC

    if network.show_active() == mainnet:
        allow_revert = True
        pool_admin = accounts.add(os.environ["POOL_PK"])
        admin = accounts.add(os.environ["BFR_PK"])
        nft_deployer = accounts.add(os.environ["NFT_DEPLOYER_PRIVATE_KEY"])
        publisher = "0x2156972c36088AA94fAeF84359C75FB4Bb83c745"

        open_keeper = "0x1A5A1e1683F304500AC03b0FA14Eb5987f6734d6"
        close_keeper = "0xc660D7126cA88bef96e65373B3d10368Cb683B46"
        revoke_keeper = ""
        early_close_keeper = ""

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
        option_reader_address = "0xd43eBDeA4efEDFa14024F9894169fad8896728A4"

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

    ####### Deploy Creation window #######
    if not creation_window_address:
        creation_window = deploy_contract(
            admin,
            network,
            CreationWindow,
            [1682269200, 1682701200],
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
    if not booster and network.show_active() != mainnet:
        booster = deploy_contract(
            admin,
            network,
            Booster,
            [nft_contract_address],
        )
        transact(
            booster.address,
            booster.abi,
            "setConfigure",
            [20, 40, 60, 80],
            sender=admin,
        )
        transact(
            booster.address,
            booster.abi,
            "setPrice",
            int(1e6),
            sender=admin,
        )
        transact(
            booster.address,
            booster.abi,
            "setBoostPercentage",
            100,
            sender=admin,
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

        # router_contract_address = "0xB1be98504D40d3644ef069A2543536a8Eb11dD87"
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
            # save_flat(BufferRouter, "BufferRouter")

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

    # transact(
    #     pool.address,
    #     pool.abi,
    #     "setMaxLiquidity",
    #     maxLiquidity,
    #     sender=pool_admin,
    # )

    ########### Get NFT ###########
    if not nft_contract_address:
        nft_contract = deploy_contract(
            nft_deployer,
            network,
            TraderNFT,
            [nft_base_contract_address],
        )
        nft_contract_address = nft_contract.address
    # else:
    #     nft_contract = TraderNFT.at(nft_contract_address)

    all_options = []
    all_configs = []
    for asset_pair in asset_pairs:
        pair = asset_pair["token1"] + asset_pair["token2"]

        ########### Get Options Config ###########

        if option_config_address:
            option_config = OptionsConfig.at(option_config_address)
        else:
            option_config = deploy_contract(
                admin,
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
                sender=admin,
            )
            transact(
                option_config.address,
                option_config.abi,
                "setBoosterContract",
                booster,
                sender=admin,
            )

            if asset_pair["asset_category"] != 1:
                transact(
                    option_config.address,
                    option_config.abi,
                    "setCreationWindowContract",
                    creation_window_address,
                    sender=admin,
                )

        ########### Deploy referral storage ###########

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
            transact(
                token_contract.address,
                token_contract.abi,
                "transfer",
                faucet.address,
                int(1e12),
                sender=admin,
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
            sender=admin,
        )
        transact(
            option_config.address,
            option_config.abi,
            "setPoolOIStorageContract",
            pool_oi_storage.address,
            sender=admin,
        )
        transact(
            option_config.address,
            option_config.abi,
            "setMarketOIConfigContract",
            market_oi_config.address,
            sender=admin,
        )
        transact(
            option_config.address,
            option_config.abi,
            "setPoolOIConfigContract",
            pool_oi_config.address,
            sender=admin,
        )
        all_options.append(options.address)
        all_configs.append(option_config.address)
        print(f"{Fore.YELLOW}Deployed {pair} at {options.address} {Style.RESET_ALL} ")

        transact(
            option_config.address,
            option_config.abi,
            "setMinFee",
            asset_pair["minFee"],
            sender=admin,
        )
        transact(
            option_config.address,
            option_config.abi,
            "setPlatformFee",
            asset_pair["platformFee"],
            sender=admin,
        )
        transact(
            option_config.address,
            option_config.abi,
            "setMinPeriod",
            asset_pair["minPeriod"],
            sender=admin,
        )
        transact(
            option_config.address,
            option_config.abi,
            "setMaxPeriod",
            asset_pair["maxPeriod"],
            sender=admin,
        )
        if asset_pair["is_early_close_allowed"]:
            transact(
                option_config.address,
                option_config.abi,
                "toggleEarlyClose",
                sender=admin,
            )
            if asset_pair["early_close_threshold"] != 60:
                transact(
                    option_config.address,
                    option_config.abi,
                    "setEarlyCloseThreshold",
                    asset_pair["early_close_threshold"],
                    sender=admin,
                )

    option_data = []
    assets = [x["token1"] + x["token2"] for x in asset_pairs]
    for x, y in zip(all_options, all_configs):
        option_data.append({"option": x, "config": y})

    all_contractss = {
        "pool": pool.address,
        "options": dict(zip(assets, option_data)),
        "referral_storage": referral_storage.address,
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
