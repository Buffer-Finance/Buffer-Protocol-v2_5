from enum import IntEnum

import brownie
from brownie import BufferBinaryOptions, OptionsConfig, AccountRegistrar
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_account.messages import encode_structured_data

ONE_DAY = 86400

ADDRESS_0 = "0x0000000000000000000000000000000000000000"


def to_32byte_hex(val):
    web3 = brownie.network.web3
    return web3.toHex(web3.toBytes(val).rjust(32, b"\0"))


class BinaryOptionTesting(object):
    def __init__(
        self,
        accounts,
        binary_options,
        binary_pool,
        total_fee,
        chain,
        tokenX,
        liquidity,
        period,
        is_above,
        router,
        publisher,
        settlement_fee_disbursal,
        binary_options_config,
        referral_contract,
        trader_nft_contract,
        creation_window,
        sf_publisher,
        # validator,
        binary_options_2,
    ):
        self.binary_options_2 = binary_options_2
        self.settlement_fee_disbursal = settlement_fee_disbursal
        self.referral_contract = referral_contract
        self.trader_nft_contract = trader_nft_contract
        self.binary_options_config = binary_options_config
        self.publisher = publisher
        self.sf_publisher = sf_publisher
        self.binary_options = binary_options
        self.binary_pool = binary_pool
        self.total_fee = total_fee
        self.accounts = accounts
        self.owner = accounts[0]
        self.user_1 = accounts[1]
        self.user_2 = accounts[2]
        self.bot = accounts[4]
        self.liquidity = liquidity
        self.tokenX = tokenX
        self.chain = chain
        self.period = period
        self.is_above = is_above
        self.router = router
        self.strike = int(400e8)
        self.slippage = 100
        self.allow_partial_fill = True
        self.sf = 1500
        self.creation_window = creation_window
        self.registrar = AccountRegistrar.at(self.router.accountRegistrar())
        self.trade_params = [
            self.total_fee,
            self.period,
            self.binary_options.address,
            self.strike,
            self.slippage,
            self.allow_partial_fill,
            "",
            0,
            int(398e8),
            15e2,
        ]
        # self.validator = validator
        self.domain_type = [
            {"name": "name", "type": "string"},
            {"name": "version", "type": "string"},
            {"name": "chainId", "type": "uint256"},
            {"name": "verifyingContract", "type": "address"},
        ]
        self.domain = {
            "name": "Validator",
            "version": "1",
            "chainId": 1,
            "verifyingContract": self.router.address,
        }

    def enc(self, msg_params, key):
        encoded_msg = encode_structured_data(msg_params)
        signed_msg = brownie.web3.eth.account.sign_message(encoded_msg, key)
        return signed_msg.signature

    def enc_v2(self, msg_params, key):
        encoded_msg = encode_structured_data(msg_params)
        signed_msg = brownie.web3.eth.account.sign_message(encoded_msg, key)
        return signed_msg

    def init(self):
        self.tokenX.approve(
            self.binary_pool.address, self.liquidity, {"from": self.owner}
        )
        self.binary_pool.provide(self.liquidity, 0, {"from": self.owner})
        self.router.setContractRegistry(self.binary_options.address, True)
        self.router.setContractRegistry(self.binary_options_2.address, True)
        self.router.setInPrivateKeeperMode() if self.router.isInPrivateKeeperMode() else None

    def time_travel(self, day_of_week, hour, to_minute):
        # Get the current block timestamp
        current_timestamp = self.chain.time()

        # Calculate the timestamp for the specified day and hour
        current_day = ((current_timestamp / ONE_DAY) + 4) % 7
        if current_day < day_of_week:
            days_until_dow = day_of_week - current_day
        elif current_day > day_of_week:
            days_until_dow = 7 - current_day + day_of_week
        else:
            days_until_dow = 0
        target_timestamp = (
            current_timestamp
            + (days_until_dow * ONE_DAY)
            + (hour * 60 * 60)
            + (to_minute * 60)
        )
        # "Time travel" to the target timestamp
        self.chain.sleep(int(target_timestamp - current_timestamp))
        current_timestamp = self.chain.time()
        self.chain.mine(1)

    def check_trading_window(self, day, hour, min, period, expected):
        self.time_travel(day, hour, min)
        # print(self.chain.time())
        assert (
            self.creation_window.isInCreationWindow(period) == expected
        ), f"Should {'' if expected else 'not'} be in creation window on {day} {hour}:{min} for period {period}"

    def verify_option_states(
        self,
        option_id,
        user,
        strike,
        expected_amount,
        expected_premium,
        expected_option_type,
        expected_total_fee,
        expected_settlement_fee,
        pool_balance_diff,
        sfd_diff,
        txn,
    ):
        (
            _,
            strike,
            amount,
            locked_amount,
            premium,
            _,
            _is_above,
            fee,
            _,
        ) = self.binary_options.options(option_id)

        assert self.binary_options.ownerOf(option_id) == user, "Wrong owner"
        print("settlmenr fee", sfd_diff, expected_settlement_fee)
        assert (
            txn.events["Create"]["settlementFee"] == expected_settlement_fee
            and sfd_diff == expected_settlement_fee
        ), "Wrong settlementFee"

        assert strike == strike, "Wrong strike"
        print(sfd_diff)
        print(amount, locked_amount, expected_amount)
        assert (
            amount == locked_amount == expected_amount
        ), "Wrong amount or locked amount"
        assert premium == expected_premium, "Wrong premium"
        assert _is_above == expected_option_type, "Wrong option_type"
        assert (
            fee == expected_total_fee - self.binary_options_config.platformFee()
        ), "Wrong fee"
        assert (
            self.tokenX.balanceOf(self.binary_options.address)
            == self.tokenX.balanceOf(self.router.address)
            == 0
        ), "Wrong option balance"
        assert pool_balance_diff == expected_premium, "Wrong premium transferred"
        assert (
            self.binary_pool.lockedLiquidity(self.binary_options.address, option_id)[0]
            == locked_amount
        ), "Wrong liquidity locked"
        assert txn.events["Save"], "Save event not emitted"

    def get_signature(self, token, timestamp, price, publisher=None):
        web3 = brownie.network.web3
        key = self.publisher.private_key if not publisher else publisher.private_key
        msg_hash = web3.solidityKeccak(
            ["string", "uint256", "uint256"],
            [BufferBinaryOptions.at(token).assetPair(), timestamp, int(price)],
        )
        signed_message = Account.sign_message(encode_defunct(msg_hash), key)
        return to_32byte_hex(signed_message.signature)

    def get_sf_signature(self, token, timestamp, sf_publisher=None):
        web3 = brownie.network.web3
        key = (
            self.sf_publisher.private_key
            if not sf_publisher
            else sf_publisher.private_key
        )
        msgParams = {
            "types": {
                "EIP712Domain": self.domain_type,
                "SettlementFeeSignature": [
                    {"name": "assetPair", "type": "string"},
                    {"name": "expiryTimestamp", "type": "uint256"},
                    {"name": "settlementFee", "type": "uint256"},
                ],
            },
            "primaryType": "SettlementFeeSignature",
            "domain": self.domain,
            "message": {
                "assetPair": BufferBinaryOptions.at(token).assetPair(),
                "expiryTimestamp": timestamp,
                "settlementFee": self.sf,
            },
        }
        s = self.enc(msgParams, key)

        return s

    def get_close_signature(self, token, timestamp, optionId, key):
        msgParams = {
            "types": {
                "EIP712Domain": self.domain_type,
                "CloseAnytimeSignature": [
                    {"name": "assetPair", "type": "string"},
                    {"name": "timestamp", "type": "uint256"},
                    {"name": "optionId", "type": "uint256"},
                ],
            },
            "primaryType": "CloseAnytimeSignature",
            "domain": self.domain,
            "message": {
                "assetPair": BufferBinaryOptions.at(token).assetPair(),
                "timestamp": timestamp,
                "optionId": int(optionId),
            },
        }
        return self.enc(msgParams, key)

    def get_user_signature(self, params, user, key):
        signature_time = self.chain.time()
        msgParams = {
            "types": {
                "EIP712Domain": self.domain_type,
                "UserTradeSignatureWithSettlementFee": [
                    {"name": "user", "type": "address"},
                    {"name": "totalFee", "type": "uint256"},
                    {"name": "period", "type": "uint256"},
                    {"name": "targetContract", "type": "address"},
                    {"name": "strike", "type": "uint256"},
                    {"name": "slippage", "type": "uint256"},
                    {"name": "allowPartialFill", "type": "bool"},
                    {"name": "referralCode", "type": "string"},
                    {"name": "traderNFTId", "type": "uint256"},
                    {"name": "timestamp", "type": "uint256"},
                    {"name": "settlementFee", "type": "uint256"},
                ],
            },
            "primaryType": "UserTradeSignatureWithSettlementFee",
            "domain": self.domain,
            "message": {
                "user": user,
                "totalFee": params[0],
                "period": params[1],
                "targetContract": params[2],
                "strike": params[3],
                "slippage": params[4],
                "allowPartialFill": params[5],
                "referralCode": params[6],
                "traderNFTId": params[7],
                "timestamp": signature_time,
                "settlementFee": self.sf,
            },
        }
        s = self.enc(msgParams, key)
        return (s, signature_time)

    def get_lo_user_signature(self, params, user, key):
        web3 = brownie.network.web3
        signature_time = self.chain.time()
        msgParams = {
            "types": {
                "EIP712Domain": self.domain_type,
                "UserTradeSignature": [
                    {"name": "user", "type": "address"},
                    {"name": "totalFee", "type": "uint256"},
                    {"name": "period", "type": "uint256"},
                    {"name": "targetContract", "type": "address"},
                    {"name": "strike", "type": "uint256"},
                    {"name": "slippage", "type": "uint256"},
                    {"name": "allowPartialFill", "type": "bool"},
                    {"name": "referralCode", "type": "string"},
                    {"name": "traderNFTId", "type": "uint256"},
                    {"name": "timestamp", "type": "uint256"},
                ],
            },
            "primaryType": "UserTradeSignature",
            "domain": self.domain,
            "message": {
                "user": user,
                "totalFee": params[0],
                "period": params[1],
                "targetContract": params[2],
                "strike": params[3],
                "slippage": params[4],
                "allowPartialFill": params[5],
                "referralCode": params[6],
                "traderNFTId": params[7],
                "timestamp": signature_time,
            },
        }
        return (self.enc(msgParams, key), signature_time)

    def get_lo_user_signature_with_direction(
        self, params, is_above, user, signature_time, key
    ):
        msgParams = {
            "types": {
                "EIP712Domain": self.domain_type,
                "MarketDirectionSignature": [
                    {"name": "user", "type": "address"},
                    {"name": "totalFee", "type": "uint256"},
                    {"name": "period", "type": "uint256"},
                    {"name": "targetContract", "type": "address"},
                    {"name": "strike", "type": "uint256"},
                    {"name": "slippage", "type": "uint256"},
                    {"name": "allowPartialFill", "type": "bool"},
                    {"name": "referralCode", "type": "string"},
                    {"name": "traderNFTId", "type": "uint256"},
                    {"name": "isAbove", "type": "bool"},
                    {"name": "timestamp", "type": "uint256"},
                ],
            },
            "primaryType": "MarketDirectionSignature",
            "domain": self.domain,
            "message": {
                "user": user,
                "totalFee": params[0],
                "period": params[1],
                "targetContract": params[2],
                "strike": params[3],
                "slippage": params[4],
                "allowPartialFill": params[5],
                "referralCode": params[6],
                "traderNFTId": params[7],
                "isAbove": is_above,
                "timestamp": signature_time,
            },
        }
        return (self.enc(msgParams, key), signature_time)

    def get_user_signature_with_direction(
        self, params, is_above, user, signature_time, key
    ):
        msgParams = {
            "types": {
                "EIP712Domain": self.domain_type,
                "MarketDirectionSignatureWithSettlementFee": [
                    {"name": "user", "type": "address"},
                    {"name": "totalFee", "type": "uint256"},
                    {"name": "period", "type": "uint256"},
                    {"name": "targetContract", "type": "address"},
                    {"name": "strike", "type": "uint256"},
                    {"name": "slippage", "type": "uint256"},
                    {"name": "allowPartialFill", "type": "bool"},
                    {"name": "referralCode", "type": "string"},
                    {"name": "traderNFTId", "type": "uint256"},
                    {"name": "isAbove", "type": "bool"},
                    {"name": "timestamp", "type": "uint256"},
                    {"name": "settlementFee", "type": "uint256"},
                ],
            },
            "primaryType": "MarketDirectionSignatureWithSettlementFee",
            "domain": self.domain,
            "message": {
                "user": user,
                "totalFee": params[0],
                "period": params[1],
                "targetContract": params[2],
                "strike": params[3],
                "slippage": params[4],
                "allowPartialFill": params[5],
                "referralCode": params[6],
                "traderNFTId": params[7],
                "isAbove": is_above,
                "timestamp": signature_time,
                "settlementFee": self.sf,
            },
        }
        return (self.enc(msgParams, key), signature_time)

    def get_user_signature_for_close(self, params, user, key):
        web3 = brownie.network.web3
        signature_time = self.chain.time()
        msg_hash = web3.solidityKeccak(
            ["address", "uint256", "address", "uint256"],
            [user, *params, signature_time],
        )
        signed_message = Account.sign_message(encode_defunct(msg_hash), key)

        return (to_32byte_hex(signed_message.signature), signature_time)

    def get_register_signature(self, one_ct, user):
        web3 = brownie.network.web3
        key = user.private_key
        domain = {
            "name": "Validator",
            "version": "1",
            "chainId": 1,
            "verifyingContract": self.registrar.address,
        }
        msgParams = {
            "types": {
                "EIP712Domain": self.domain_type,
                "RegisterAccount": [
                    {"name": "oneCT", "type": "address"},
                    {"name": "user", "type": "address"},
                    {"name": "nonce", "type": "uint256"},
                ],
            },
            "primaryType": "RegisterAccount",
            "domain": domain,
            "message": {
                "oneCT": one_ct.address,
                "user": user.address,
                "nonce": self.registrar.accountMapping(user.address)[1],
            },
        }
        s = self.enc(msgParams, key)
        return s

    def get_deregister_signature(self, user):
        web3 = brownie.network.web3
        key = user.private_key

        domain = {
            "name": "Validator",
            "version": "1",
            "chainId": 1,
            "verifyingContract": self.registrar.address,
        }
        msgParams = {
            "types": {
                "EIP712Domain": self.domain_type,
                "DeregisterAccount": [
                    {"name": "user", "type": "address"},
                    {"name": "nonce", "type": "uint256"},
                ],
            },
            "primaryType": "DeregisterAccount",
            "domain": domain,
            "message": {
                "user": user.address,
                "nonce": self.registrar.accountMapping(user.address)[1],
            },
        }
        s = self.enc(msgParams, key)
        return s

    def get_permit(self, allowance, deadline, user):
        web3 = brownie.network.web3
        key = user.private_key
        domain = {
            "name": "Token",
            "version": "1",
            "chainId": 1,
            "verifyingContract": self.tokenX.address,
        }

        msgParams = {
            "types": {
                "EIP712Domain": self.domain_type,
                "Permit": [
                    {"name": "owner", "type": "address"},
                    {"name": "spender", "type": "address"},
                    {"name": "value", "type": "uint256"},
                    {"name": "nonce", "type": "uint256"},
                    {"name": "deadline", "type": "uint256"},
                ],
            },
            "primaryType": "Permit",
            "domain": domain,
            "message": {
                "owner": user.address,
                "spender": self.router.address,
                "value": allowance,
                "nonce": self.tokenX.nonces(user.address),
                "deadline": deadline,
            },
        }
        sig = self.enc_v2(msgParams, key)

        return sig.v, sig.r, sig.s

    def reregister(self, user, one_ct):
        ADMIN_ROLE = self.registrar.ADMIN_ROLE()
        self.registrar.grantRole(
            ADMIN_ROLE,
            self.accounts[0],
            {"from": self.accounts[0]},
        )

        nonce = self.registrar.accountMapping(user.address)[1]
        self.registrar.deregisterAccount(
            user.address, self.get_deregister_signature(user), {"from": self.owner}
        )
        assert self.registrar.accountMapping(user.address)[0] == ADDRESS_0
        assert self.registrar.accountMapping(user.address)[1] == nonce + 1
        txn = self.registrar.registerAccount(
            one_ct.address,
            user.address,
            self.get_register_signature(one_ct, user),
            {"from": self.owner},
        )

    def get_trade_params(
        self,
        user,
        one_ct,
        is_limit_order=False,
        params=None,
        queue_id=0,
        options_contact=None,
    ):
        params = params if params else self.trade_params
        sf_expiry = self.chain.time() + 100
        options_contact = (
            self.binary_options if not options_contact else options_contact
        )
        sf_signature = self.get_sf_signature(options_contact, sf_expiry)
        user_sign_info = (
            self.get_user_signature(
                params[:8],
                user.address,
                one_ct.private_key,
            )
            if not is_limit_order
            else self.get_lo_user_signature(
                params[:8], user.address, one_ct.private_key
            )
        )
        user_sign_info_for_execution = (
            self.get_user_signature_with_direction(
                params[:8],
                self.is_above,
                user.address,
                user_sign_info[1],
                one_ct.private_key,
            )
            if not is_limit_order
            else self.get_lo_user_signature_with_direction(
                params[:8],
                self.is_above,
                user.address,
                user_sign_info[1],
                one_ct.private_key,
            )
        )
        self.wrong_full_signature = (
            self.get_user_signature_with_direction(
                params[:8],
                not self.is_above,
                user.address,
                user_sign_info[1],
                one_ct.private_key,
            )
            if not is_limit_order
            else self.get_lo_user_signature_with_direction(
                params[:8],
                not self.is_above,
                user.address,
                user_sign_info[1],
                one_ct.private_key,
            )
        )

        lo_expiration = self.chain.time() + 30
        current_time = self.chain.time()
        trade_params = (
            [queue_id]
            + params
            + [is_limit_order, lo_expiration if is_limit_order else 0]
            + [
                [sf_signature, sf_expiry],
                user_sign_info,
                [
                    self.get_signature(options_contact, current_time, params[-2]),
                    current_time,
                ],
            ]
        )
        register_params = [
            one_ct.address,
            self.get_register_signature(
                one_ct,
                user,
            ),
            True,
        ]
        deadline = self.chain.time() + 50
        allowance = int(5e6)
        permit = [
            allowance,
            deadline,
            *self.get_permit(allowance, deadline, user),
            True,
        ]

        return (
            [trade_params, register_params, permit, user.address],
            user_sign_info_for_execution,
        )

    def create(
        self,
        user,
        one_ct,
        is_limit_order=False,
        params=None,
        queue_id=0,
        options_contact=None,
    ):
        options_contact = (
            self.binary_options if not options_contact else options_contact
        )
        expected_option_id = options_contact.nextTokenId()
        params = params if params else self.trade_params
        trade_params = self.get_trade_params(
            user,
            one_ct,
            is_limit_order,
            params,
            queue_id=queue_id,
            options_contact=options_contact,
        )
        txn = self.router.openTrades([*trade_params[:-1]], {"from": self.bot})
        # print(txn.events)
        optionId = txn.events["OpenTrade"]["optionId"]
        queueId = txn.events["OpenTrade"]["queueId"]
        assert optionId == expected_option_id

        print(options_contact.options(optionId), optionId)
        return optionId, queueId, trade_params, txn

    def unlock_options(self, options):
        params = []
        for option in options:
            option_data = self.binary_options.options(option[0])
            close_params = (self.binary_options.address, option_data[5], option[1])
            params.append(
                (
                    option[0],
                    *close_params,
                    self.get_signature(
                        *close_params,
                    ),
                )
            )
        txn = self.router.unlockOptions(
            params,
            {"from": self.bot},
        )
        return txn


def utility(contracts, accounts, chain):
    tokenX = contracts["tokenX"]
    binary_pool = contracts["binary_pool_atm"]
    router = contracts["router"]
    binary_options_config = contracts["binary_options_config_atm"]
    binary_options = contracts["binary_european_options_atm"]
    binary_options_2 = contracts["binary_european_options_atm_2"]
    publisher = contracts["publisher"]
    sf_publisher = contracts["sf_publisher"]
    settlement_fee_disbursal = contracts["settlement_fee_disbursal"]
    referral_contract = contracts["referral_contract"]
    trader_nft_contract = contracts["trader_nft_contract"]
    creation_window = contracts["creation_window"]
    # validator = contracts["validator"]
    total_fee = int(1e6)
    liquidity = int(1000000 * 1e6)
    period = 86300
    isAbove = False

    option = BinaryOptionTesting(
        accounts,
        binary_options,
        binary_pool,
        total_fee,
        chain,
        tokenX,
        liquidity,
        period,
        isAbove,
        router,
        publisher,
        settlement_fee_disbursal,
        binary_options_config,
        referral_contract,
        trader_nft_contract,
        creation_window,
        sf_publisher,
        # validator,
        binary_options_2,
    )
    option.init()

    return option
