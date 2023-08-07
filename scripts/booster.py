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

    market_times = [
        (17, 0, 23, 59),
        (0, 0, 23, 59),
        (0, 0, 23, 59),
        (0, 0, 23, 59),
        (0, 0, 23, 59),
        (0, 0, 15, 59),
        (0, 0, 0, 0),
    ]

    asset_pairs = [
        {
            "token1": "BTC",
            "token2": "USD",
            "full_name": "Bitcoin",
            "asset_category": 1,
            "payout": 65,
            "minFee": int(1e6),
            "platformFee": int(1e5),
            "minPeriod": 3 * 60,
            "maxPeriod": 4 * 60 * 60,
            "max_trade_size": int(1000e6),
            "max_market_oi": int(50000e6),
        },
        {
            "token1": "ETH",
            "token2": "USD",
            "full_name": "Ethereum",
            "asset_category": 1,
            "payout": 65,
            "minFee": int(1e6),
            "platformFee": int(1e5),
            "minPeriod": 3 * 60,
            "maxPeriod": 4 * 60 * 60,
            "max_trade_size": int(1000e6),
            "max_market_oi": int(50000e6),
        },
        {
            "token1": "EUR",
            "token2": "USD",
            "full_name": "Euro",
            "asset_category": 0,
            "payout": 65,
            "minFee": int(1e6),
            "platformFee": int(1e5),
            "minPeriod": 3 * 60,
            "maxPeriod": 4 * 60 * 60,
            "max_trade_size": int(1000e6),
            "max_market_oi": int(50000e6),
        },
        {
            "token1": "GBP",
            "token2": "USD",
            "full_name": "Pound",
            "asset_category": 0,
            "payout": 65,
            "minFee": int(1e6),
            "platformFee": int(1e5),
            "minPeriod": 3 * 60,
            "maxPeriod": 4 * 60 * 60,
            "max_trade_size": int(1000e6),
            "max_market_oi": int(50000e6),
        },
        {
            "token1": "XAU",
            "token2": "USD",
            "full_name": "Gold",
            "asset_category": 2,
            "payout": 65,
            "minFee": int(1e6),
            "platformFee": int(1e5),
            "minPeriod": 3 * 60,
            "maxPeriod": 4 * 60 * 60,
            "max_trade_size": int(1000e6),
            "max_market_oi": int(50000e6),
        },
        {
            "token1": "XAG",
            "token2": "USD",
            "full_name": "Silver",
            "asset_category": 2,
            "payout": 65,
            "minFee": int(1e6),
            "platformFee": int(1e5),
            "minPeriod": 3 * 60,
            "maxPeriod": 4 * 60 * 60,
            "max_trade_size": int(1000e6),
            "max_market_oi": int(50000e6),
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
        sfd = "0x32A49a15F8eE598C1EeDc21138DEb23b391f425b"
        decimals = 6
        is_testnet_token = True
        nft_base_contract_address = ""
        # pool_oi_storage = "0x69fEC5e3500F161739c428355caeFa09Cf13f4Ae"
        # pool_oi_config = "0x9b308eabe572D5c9132B035476E2ecD5802319ac"
        # account_registrar_address = "0xF93545296A467C50d05eC1A4F356A3415dc20268"
        booster = "0x58E66d360d65Da8d7907768f826D86F411d0f849"
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

    ####### Deploy Booster #######
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

    addresses = [
        {
            "configContract": {
                "address": "0x16d8e3670791e8eb4372889fad426bff35b988be",
                "maxFee": "0",
                "maxPeriod": "14400",
                "minFee": "1000000",
                "minPeriod": "180",
                "platformFee": "100000",
                "earlyCloseThreshold": "60",
                "isEarlyCloseEnabled": True,
            },
            "address": "0x578d08cf15b08296043a0968b98fb408dbe0ff9d",
            "poolContract": "0x6efabb45b781b62979600444775113516220d992",
            "isPaused": False,
            "category": 1,
            "asset": "ETHUSD",
        },
        {
            "configContract": {
                "address": "0x3d729530851dd1a1573d3cd1638cc935d801936d",
                "maxFee": "0",
                "maxPeriod": "14400",
                "minFee": "1000000",
                "minPeriod": "180",
                "platformFee": "100000",
                "earlyCloseThreshold": "60",
                "isEarlyCloseEnabled": True,
            },
            "address": "0x67985caf7551191feabdc7f15289bfb45680d74e",
            "poolContract": "0x6efabb45b781b62979600444775113516220d992",
            "isPaused": False,
            "category": 2,
            "asset": "XAUUSD",
        },
        {
            "configContract": {
                "address": "0x2f52d5695786c58b5fbfcd81267ad48a59578d15",
                "maxFee": "0",
                "maxPeriod": "14400",
                "minFee": "1000000",
                "minPeriod": "180",
                "platformFee": "100000",
                "earlyCloseThreshold": "60",
                "isEarlyCloseEnabled": True,
            },
            "address": "0x6f34dee136314b2a610566ac8091a4e9e7ed4e9e",
            "poolContract": "0x6efabb45b781b62979600444775113516220d992",
            "isPaused": False,
            "category": 1,
            "asset": "BTCUSD",
        },
        {
            "configContract": {
                "address": "0x4be39a1a8a02b9c0895628841e84a93440bcec16",
                "maxFee": "0",
                "maxPeriod": "14400",
                "minFee": "1000000",
                "minPeriod": "180",
                "platformFee": "100000",
                "earlyCloseThreshold": "60",
                "isEarlyCloseEnabled": True,
            },
            "address": "0x92d2dbfe34c2527780d9d4897cada3aef153a1fd",
            "poolContract": "0x6efabb45b781b62979600444775113516220d992",
            "isPaused": False,
            "category": 0,
            "asset": "EURUSD",
        },
        {
            "configContract": {
                "address": "0x52b9eeb12aca9d5bd4c12735e8f6d7b94d1c5035",
                "maxFee": "0",
                "maxPeriod": "14400",
                "minFee": "1000000",
                "minPeriod": "180",
                "platformFee": "100000",
                "earlyCloseThreshold": "60",
                "isEarlyCloseEnabled": True,
            },
            "address": "0xe23a3c592b80c7416538a607acecc76c2ff83e69",
            "poolContract": "0x6efabb45b781b62979600444775113516220d992",
            "isPaused": False,
            "category": 0,
            "asset": "GBPUSD",
        },
        {
            "configContract": {
                "address": "0x1599601770f48aefc5cc3bcf5ec9d3012995a6d3",
                "maxFee": "0",
                "maxPeriod": "14400",
                "minFee": "1000000",
                "minPeriod": "180",
                "platformFee": "100000",
                "earlyCloseThreshold": "60",
                "isEarlyCloseEnabled": True,
            },
            "address": "0xe457b8313c3e71e9f458ab473d329d795f48669d",
            "poolContract": "0x6efabb45b781b62979600444775113516220d992",
            "isPaused": False,
            "category": 2,
            "asset": "XAGUSD",
        },
        {
            "configContract": {
                "address": "0x91be1704eafd42449d13b151f9aaa15982c340cc",
                "maxFee": "0",
                "maxPeriod": "14400",
                "minFee": "1000000",
                "minPeriod": "180",
                "platformFee": "100000",
                "earlyCloseThreshold": "60",
                "isEarlyCloseEnabled": True,
                "marketOIaddress": "0x20d44cee731c877b30c3d4d1020be2f0c1d7aee5",
            },
            "address": "0x0135fd2979266662942c9f4717b97c9f56bb4368",
            "poolContract": "0xb04abea1152bfcdbb35edcb3a5c9b1929cd789d4",
            "isPaused": False,
            "category": 0,
            "asset": "EURUSD",
        },
        {
            "configContract": {
                "address": "0xdefdecb1336fb449808443479c55c550e4594cc1",
                "maxFee": "0",
                "maxPeriod": "14400",
                "minFee": "1000000",
                "minPeriod": "180",
                "platformFee": "100000",
                "earlyCloseThreshold": "60",
                "isEarlyCloseEnabled": True,
                "marketOIaddress": "0x0fa722efb09cba2cd383c381c879557111c80cef",
            },
            "address": "0x09e1020329ec624205e16bcd51633328828e4914",
            "poolContract": "0xb04abea1152bfcdbb35edcb3a5c9b1929cd789d4",
            "isPaused": False,
            "category": 2,
            "asset": "XAGUSD",
        },
        {
            "configContract": {
                "address": "0x0bb6898f472342dee466156873c76a95fd21e792",
                "maxFee": "0",
                "maxPeriod": "14400",
                "minFee": "1000000",
                "minPeriod": "180",
                "platformFee": "100000",
                "earlyCloseThreshold": "60",
                "isEarlyCloseEnabled": True,
                "marketOIaddress": "0x0d061ea39406f1188435f2ef59c6c2e855bdb382",
            },
            "address": "0x286ae6e965d13f4027b745d16616bf50728f479d",
            "poolContract": "0xb04abea1152bfcdbb35edcb3a5c9b1929cd789d4",
            "isPaused": False,
            "category": 0,
            "asset": "GBPUSD",
        },
        {
            "configContract": {
                "address": "0xd935c81e6bd2fc89db1556aad0db08aa95bfdfa9",
                "maxFee": "0",
                "maxPeriod": "14400",
                "minFee": "1000000",
                "minPeriod": "180",
                "platformFee": "100000",
                "earlyCloseThreshold": "60",
                "isEarlyCloseEnabled": True,
                "marketOIaddress": "0x9b995f8d00de769154c4bc51f863b44aebed8ef0",
            },
            "address": "0x2995a7a89aad6c8a20be72f13c6f47433506c46f",
            "poolContract": "0xb04abea1152bfcdbb35edcb3a5c9b1929cd789d4",
            "isPaused": False,
            "category": 2,
            "asset": "XAUUSD",
        },
        {
            "configContract": {
                "address": "0xfbdd0396a81620f75b07878e62047174fef94932",
                "maxFee": "0",
                "maxPeriod": "14400",
                "minFee": "1000000000000000000",
                "minPeriod": "180",
                "platformFee": "100000000000000000",
                "earlyCloseThreshold": "60",
                "isEarlyCloseEnabled": True,
                "marketOIaddress": "0x941735bf7e22284757a31718ba6daecb6c9693c8",
            },
            "address": "0x441bd7f41affa3df0bb75601eff3f804b286e918",
            "poolContract": "0x70e29d7f07bbb83253de57f73543f5cb8f3a267a",
            "isPaused": False,
            "category": 0,
            "asset": "EURUSD",
        },
        {
            "configContract": {
                "address": "0x07b95dcf6418ed2de79e84d804094e42b76b4124",
                "maxFee": "0",
                "maxPeriod": "14400",
                "minFee": "1000000",
                "minPeriod": "180",
                "platformFee": "100000",
                "earlyCloseThreshold": "60",
                "isEarlyCloseEnabled": True,
                "marketOIaddress": "0x057c1b161af11c753d7eb6dde45e2e63000bf5dd",
            },
            "address": "0x6a24170caaf5d1e47de1069583fec9555e86f462",
            "poolContract": "0xb04abea1152bfcdbb35edcb3a5c9b1929cd789d4",
            "isPaused": False,
            "category": 1,
            "asset": "BTCUSD",
        },
        {
            "configContract": {
                "address": "0xf8203d818a35f4484e6e240980e9b112faaecd13",
                "maxFee": "0",
                "maxPeriod": "14400",
                "minFee": "1000000000000000000",
                "minPeriod": "180",
                "platformFee": "100000000000000000",
                "earlyCloseThreshold": "60",
                "isEarlyCloseEnabled": True,
                "marketOIaddress": "0xf72c8924759c459e0cddd536270d4433918a13bb",
            },
            "address": "0x6b03b8c9426b351e934d2271fd5b498fef079dbd",
            "poolContract": "0x70e29d7f07bbb83253de57f73543f5cb8f3a267a",
            "isPaused": False,
            "category": 2,
            "asset": "XAGUSD",
        },
        {
            "configContract": {
                "address": "0x3d6177469f7574d761705c9b3e78118908aabe58",
                "maxFee": "0",
                "maxPeriod": "14400",
                "minFee": "1000000",
                "minPeriod": "180",
                "platformFee": "100000",
                "earlyCloseThreshold": "60",
                "isEarlyCloseEnabled": True,
                "marketOIaddress": "0x10c48532c549e1c4a86e6547d3653c7457ffdede",
            },
            "address": "0x6f7cd28814973d7000143968e7f6c72f8c907b34",
            "poolContract": "0xb04abea1152bfcdbb35edcb3a5c9b1929cd789d4",
            "isPaused": False,
            "category": 1,
            "asset": "ETHUSD",
        },
        {
            "configContract": {
                "address": "0x98e99f5695a62c21c9940141092aa791901aca82",
                "maxFee": "0",
                "maxPeriod": "14400",
                "minFee": "1000000000000000000",
                "minPeriod": "180",
                "platformFee": "100000000000000000",
                "earlyCloseThreshold": "60",
                "isEarlyCloseEnabled": True,
                "marketOIaddress": "0x88dcca7d2ecfe55b8043edd74d73802c8e1508bb",
            },
            "address": "0x807e61346a9898c35b5954f82ba70efecdf86171",
            "poolContract": "0x70e29d7f07bbb83253de57f73543f5cb8f3a267a",
            "isPaused": False,
            "category": 2,
            "asset": "XAUUSD",
        },
        {
            "configContract": {
                "address": "0x49ecc7f3b104df685fd317bbad13dbf5c6351e95",
                "maxFee": "0",
                "maxPeriod": "14400",
                "minFee": "1000000000000000000",
                "minPeriod": "180",
                "platformFee": "100000000000000000",
                "earlyCloseThreshold": "60",
                "isEarlyCloseEnabled": True,
                "marketOIaddress": "0xd51d23dea9931e8a765949648ee2d4fb317d9164",
            },
            "address": "0x8d8b172022250f89f80307b37f6f0c6b0150c236",
            "poolContract": "0x70e29d7f07bbb83253de57f73543f5cb8f3a267a",
            "isPaused": False,
            "category": 0,
            "asset": "GBPUSD",
        },
        {
            "configContract": {
                "address": "0xbb69d65cf3e12ae2ad37f713ded76c111c30e63d",
                "maxFee": "0",
                "maxPeriod": "14400",
                "minFee": "1000000000000000000",
                "minPeriod": "180",
                "platformFee": "100000000000000000",
                "earlyCloseThreshold": "60",
                "isEarlyCloseEnabled": True,
                "marketOIaddress": "0x380a7031632558b8949f3527bff236a679f8fdcf",
            },
            "address": "0xda7860922c12113ef53f9e43fc287f221fedb6d3",
            "poolContract": "0x70e29d7f07bbb83253de57f73543f5cb8f3a267a",
            "isPaused": False,
            "category": 1,
            "asset": "BTCUSD",
        },
        {
            "configContract": {
                "address": "0x44a6d1f57b5c534e95a01d3b2ff8f4e227817aab",
                "maxFee": "0",
                "maxPeriod": "14400",
                "minFee": "1000000000000000000",
                "minPeriod": "180",
                "platformFee": "100000000000000000",
                "earlyCloseThreshold": "60",
                "isEarlyCloseEnabled": True,
                "marketOIaddress": "0x8b2c2ba628484f1129c3992568db059795d7c73f",
            },
            "address": "0xe38d57b47745b076a7b50a6581e5279a89a0199c",
            "poolContract": "0x70e29d7f07bbb83253de57f73543f5cb8f3a267a",
            "isPaused": False,
            "category": 1,
            "asset": "ETHUSD",
        },
    ]

    for d in addresses:
        option_config = OptionsConfig.at(d["configContract"]["address"])
        transact(
            option_config.address,
            option_config.abi,
            "setBoosterContract",
            booster,
            sender=admin,
        )
