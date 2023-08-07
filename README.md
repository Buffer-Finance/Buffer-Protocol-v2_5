# Buffer v2.5 Audit Report

### Reviewed by: 0x52 (@IAm0x52)

### Review Dates: 7/26/23 - 7/30/23

# Scope

The [Buffer V2.5](https://github.com/Buffer-Finance/Buffer-Protocol-v2_5/) repo was reviewed at hash [84b6060b44](https://github.com/Buffer-Finance/Buffer-Protocol-v2_5/blob/84b6060b4447b2550de595202e8820c7f515988b)

In-Scope Contracts

-   contracts/core/AccountRegistrar.sol
-   contracts/core/Booster.sol
-   contracts/core/BufferBinaryOptions.sol
-   contracts/core/BufferBinaryPool.sol
-   contracts/core/BufferRouter.sol
-   contracts/core/CreationWindow.sol
-   contracts/core/OptionMath.sol
-   contracts/core/OptionConfig.sol
-   contracts/core/Validator.sol

Deployment Chain(s)

-   Arbitrum One Mainnet

# Summary of Findings

| Identifier | Title                                                                             | Severity | Fixed |
| ---------- | --------------------------------------------------------------------------------- | -------- | ----- |
| [H-01]     | Payments for coupons to Booster are irretrievable                                 | High     | TBF   |
| [H-02]     | BufferBinaryPool can permanently lock funds on early exercise                     | High     | TBF   |
| [H-03]     | Market direction signature can be abused if privateKeeperMode is disabled         | High     | X     |
| [H-04]     | closeAnytime timestamp is never validated against current timestamp               | High     | X     |
| [H-05]     | closeAnyTime timestamp is never validated against pricing timestamp               | High     | X     |
| [H-06]     | Settlement fee isn't applied correctly in BufferBinaryOptions#createFromRouter    | High     | TBD   |
| [M-01]     | booster#buy fails to apply discount                                               | Medium   | TBF   |
| [M-02]     | Transferred options can only be closed early by previous owner                    | Medium   | TBF   |
| [M-03]     | Platform fee is methodology is incompatible with the use of multiple vaults       | Medium   | X     |
| [L-01]     | Users can buy coupons for options that don't exist                                | Low      | X     |
| [L-02]     | Using a single IV value is restrictive and can unfairly price option payouts      | Low      | X     |
| [L-03]     | registerAccount sub-call in BufferRouter#openTrades can revert entire transaction | Low      | TBF   |
| [I-01]     | Booster#buy should support buying multiple boosts at a time                       | Info     | TBF   |
| [I-02]     | OptionMath#\_decay is never used                                                  | Info     | TBF   |

## [H-01] Payments for coupons to Booster are irretrievable

### Details

[Booster.sol#L92-L99](https://github.com/Buffer-Finance/Buffer-Protocol-v2_5/blob/84b6060b4447b2550de595202e8820c7f515988b/contracts/core/Booster.sol#L92-L99)

        uint256 price = couponPrice - discount;
        require(token.balanceOf(user) >= price, "Not enough balance");


        token.safeTransferFrom(user, address(this), couponPrice); <- @audit tokens transferred to this
        userBoostTrades[tokenAddress][user]
            .totalBoostTrades += MAX_TRADES_PER_BOOST;


        emit BuyCoupon(tokenAddress, user, couponPrice);

Booster#buy transfers tokens to itself but has no way to recover these tokens, causing them to be permanently trapped in this contract.

### Lines of Code

[Booster.sol#L80-L100](https://github.com/Buffer-Finance/Buffer-Protocol-v2_5/blob/84b6060b4447b2550de595202e8820c7f515988b/contracts/core/Booster.sol#L80-L100)

### Recommendation

Transfer fees to a configurable address such as admin

## [H-02] BufferBinaryPool can permanently lock funds on early exercise

### Details

[BufferBinaryOptions.sol#L380-L395](https://github.com/Buffer-Finance/Buffer-Protocol-v2_5/blob/84b6060b4447b2550de595202e8820c7f515988b/contracts/core/BufferBinaryOptions.sol#L380-L395)

        if (option.expiration > closingTime) {
            profit =
                (option.lockedAmount *
                    OptionMath.blackScholesPriceBinary(
                        config.iv(),
                        option.strike,
                        closingPrice,
                        option.expiration - closingTime,
                        true,
                        isAbove
                    )) /
                1e8;
        } else {
            profit = option.lockedAmount;
        }
        pool.send(optionID, user, profit);

When exercising an option early, it is possible to receive a partial payout depending on the factors such as when the contract is unlocked and the current asset price. This will cause the contract to send only a portion of the locked amount.

[BufferBinaryPool.sol#L200-L207](https://github.com/Buffer-Finance/Buffer-Protocol-v2_5/blob/84b6060b4447b2550de595202e8820c7f515988b/contracts/core/BufferBinaryPool.sol#L200-L207)

        uint256 transferTokenXAmount = tokenXAmount > ll.amount
            ? ll.amount
            : tokenXAmount;


        ll.locked = false;
        lockedPremium = lockedPremium - ll.premium;
        lockedAmount = lockedAmount - transferTokenXAmount;
        tokenX.safeTransfer(to, transferTokenXAmount);

This is problematic since the amount of tokens sent is also the amount unlocked. This will leave the remainder of the fees perpetually locked in the BufferBinaryPool contract.

Example:
A user opens an option that locks 100 USDC. After some time they decide to exercise early. Due to current pricing factors their option is exercised for only 50 USDC. This unlocks 50 USDC leaving the other 50 USDC permanently locked, which means they can never be withdrawn by LPs

### Lines of Code

[BufferBinaryPool.sol#L191-L212](https://github.com/Buffer-Finance/Buffer-Protocol-v2_5/blob/84b6060b4447b2550de595202e8820c7f515988b/contracts/core/BufferBinaryPool.sol#L191-L212)

### Recommendation

BufferBinaryPool#send should always unlock the entire option amount not just the amount sent.

## [H-03] Market direction signature can be abused if privateKeeperMode is disabled

### Details

https://github.com/Buffer-Finance/Buffer-Protocol-v2_5/blob/84b6060b4447b2550de595202e8820c7f515988b/contracts/core/BufferRouter.sol#L233-L246

            if (
                !Validator.verifyMarketDirection(
                    params,
                    queuedTrade,
                    optionInfo.signer
                )
            ) {
                emit FailUnlock(
                    params.optionId,
                    params.targetContract,
                    "Router: Wrong market direction"
                );
                continue;
            }

When options are exercised, the market direction is revealed via a signature provided by the opener. This can cause 2 significant issues if privateKeeperMode is disabled:

1. User can change the direction of their trade after to guarantee they win
2. User can open trade and withhold direction signature to indefinitely lock LP funds

### Lines of Code

[BufferRouter.sol#L233-L246](https://github.com/Buffer-Finance/Buffer-Protocol-v2_5/blob/84b6060b4447b2550de595202e8820c7f515988b/contracts/core/BufferRouter.sol#L233-L246)

[BufferRouter.sol#L300-L313](https://github.com/Buffer-Finance/Buffer-Protocol-v2_5/blob/84b6060b4447b2550de595202e8820c7f515988b/contracts/core/BufferRouter.sol#L300-L313)

### Recommendation

Instead of using a signature at exercise, consider instead concatenating the direction with a salt then hashing storing that hash with the queued trade. Upon closure the salt and direction can be provided and the hash checked against the stored hash.

## [H-04] closeAnytime timestamp is never validated against current timestamp

### Details

[BufferRouter.sol#L248-L258](https://github.com/Buffer-Finance/Buffer-Protocol-v2_5/blob/84b6060b4447b2550de595202e8820c7f515988b/contracts/core/BufferRouter.sol#L248-L258)

            try
                optionsContract.unlock(
                    params.optionId,
                    params.closingPrice,
                    publisherSignInfo.timestamp,
                    params.isAbove
                )
            {} catch Error(string memory reason) {
                emit FailUnlock(params.optionId, params.targetContract, reason);
                continue;
            }

When exercising early, the timestamp used for unlocking is extremely important. The current implementation doesn't ever validate the current timestamp is anywhere near the current timestamp. If private keeper mode is disabled, a user could exercise their option in the past when they would get a better payoff.

### Lines of Code

[BufferRouter.sol#L167-L260](https://github.com/Buffer-Finance/Buffer-Protocol-v2_5/blob/84b6060b4447b2550de595202e8820c7f515988b/contracts/core/BufferRouter.sol#L167-L260)

### Recommendation

Validate that exercise timestamp is within some margin of the current timestamp

## [H-05] closeAnyTime timestamp is never validated against pricing timestamp

### Details

[BufferRouter.sol#L248-L258](https://github.com/Buffer-Finance/Buffer-Protocol-v2_5/blob/84b6060b4447b2550de595202e8820c7f515988b/contracts/core/BufferRouter.sol#L248-L258)

            try
                optionsContract.unlock(
                    params.optionId,
                    params.closingPrice,
                    publisherSignInfo.timestamp,
                    params.isAbove
                )
            {} catch Error(string memory reason) {
                emit FailUnlock(params.optionId, params.targetContract, reason);
                continue;
            }

When an option is exercised early, it uses the timestamp of the pricing data without ever checking the timestamp of the closeAnytime signature. This can lead to 2 potential issues:

1. The user may receive less than expected due to the actual exercise timestamp being different than when they signed
2. If private keeper mode is disabled then transactions may be intercepted and the signature used by someone else to close the position with a much different timestamp

### Lines of Code

[BufferRouter.sol#L167-L260](https://github.com/Buffer-Finance/Buffer-Protocol-v2_5/blob/84b6060b4447b2550de595202e8820c7f515988b/contracts/core/BufferRouter.sol#L167-L260)

### Recommendation

Pricing data timestamp and closeAnytime timestamp should be required to match

## [H-06] Settlement fee isn't applied correctly in BufferBinaryOptions#createFromRouter

### Details

[BufferBinaryOptions.sol#L119-L144](https://github.com/Buffer-Finance/Buffer-Protocol-v2_5/blob/84b6060b4447b2550de595202e8820c7f515988b/contracts/core/BufferBinaryOptions.sol#L119-L144)

        Option memory option = Option(
            State.Active,
            optionParams.strike,
            optionParams.amount,
            optionParams.amount,
            optionParams.amount / 2,
            queuedTime + optionParams.period,
            optionParams.totalFee,
            queuedTime
        );
        optionID = _generateTokenId();
        userOptionIds[optionParams.user].push(optionID);
        options[optionID] = option;
        _mint(optionParams.user, optionID);


        uint256 referrerFee = _processReferralRebate(
            optionParams.user,
            optionParams.totalFee,
            optionParams.amount,
            optionParams.referralCode,
            optionParams.baseSettlementFeePercentage
        );


        uint256 settlementFee = optionParams.totalFee -
            option.premium -
            referrerFee;

Premium and settlementFee are still hardcoded as with the previous version instead of being dynamic as it is supposed to be. This leads to LPs or referrers receiving less than intended.

### Lines of Code

[BufferBinaryOptions.sol#L115-L174](https://github.com/Buffer-Finance/Buffer-Protocol-v2_5/blob/84b6060b4447b2550de595202e8820c7f515988b/contracts/core/BufferBinaryOptions.sol#L115-L174)

### Recommendation

Settlement fee should be applied dynamically instead of being hardcoded

## [M-01] booster#buy fails to apply discount

### Details

[Booster.sol#L92-L95](https://github.com/Buffer-Finance/Buffer-Protocol-v2_5/blob/84b6060b4447b2550de595202e8820c7f515988b/contracts/core/Booster.sol#L92-L95)

        uint256 price = couponPrice - discount;
        require(token.balanceOf(user) >= price, "Not enough balance");

        token.safeTransferFrom(user, address(this), couponPrice); <- @audit transfers couponPrice rather than price

When buying boosts the contract mistakenly transfers couponPrice rather than price which is reduced by discount. Additionally the event also emits this incorrect value.

### Lines of Code

[Booster.sol#L80-L100](https://github.com/Buffer-Finance/Buffer-Protocol-v2_5/blob/84b6060b4447b2550de595202e8820c7f515988b/contracts/core/Booster.sol#L80-L100)

### Recommendation

Transfer price rather than couponPrice

## [M-02] Transferred options can only be closed early by previous owner

### Details

[BufferRouter.sol#L197-L205](https://github.com/Buffer-Finance/Buffer-Protocol-v2_5/blob/84b6060b4447b2550de595202e8820c7f515988b/contracts/core/BufferRouter.sol#L197-L205)

            (address signer, ) = getAccountMapping(queuedTrade.user);

            bool isUserSignValid = Validator.verifyCloseAnytime(
                optionsContract.assetPair(),
                closeParam.userSignInfo.timestamp,
                params.optionId,
                closeParam.userSignInfo.signature,
                signer
            );

Options are minted as NFTs allowing options to be transferred to other users. This allows users to potentially sell/transfer their options to other user. This cause 2 issues:

1. The previous owner can close the option early to cause damage to the new owner
2. The new owner cannot close their option early by themselves

### Lines of Code

[BufferRouter.sol#L167-L260](https://github.com/Buffer-Finance/Buffer-Protocol-v2_5/blob/84b6060b4447b2550de595202e8820c7f515988b/contracts/core/BufferRouter.sol#L167-L260)

### Recommendation

NFT functionality should be removed or closeAnytime should determine the signer based on the owner of the option NFT

## [M-03] Platform fee is methodology is incompatible with the use of multiple vaults

### Details

[BufferRouter.sol#L476-L478](https://github.com/Buffer-Finance/Buffer-Protocol-v2_5/blob/84b6060b4447b2550de595202e8820c7f515988b/contracts/core/BufferRouter.sol#L476-L478)

        ERC20 tokenX = ERC20(optionsContract.tokenX());

        tokenX.safeTransferFrom(user, admin, platformFee);

BufferRouter#\_openTrade always transfers a flat fee from the user opening the option. This is problematic since tokenX can have a variety of decimals and values. As an example transferring 1e18 ARB is a few dollars while 1e18 USDC is trillions of dollars.

### Lines of Code

[BufferRouter.sol#L440-L513](https://github.com/Buffer-Finance/Buffer-Protocol-v2_5/blob/84b6060b4447b2550de595202e8820c7f515988b/contracts/core/BufferRouter.sol#L440-L513)

### Recommendation

Platform fee mechanism should be redesigned with this in mind

## [L-01] Users can buy coupons for options that don't exist

### Details

Booster#buy allows users to buy boosts for any tokens, which means that user can pay for and buy useless boost for tokens that aren't listed.

### Lines of Code

[Booster.sol#L80-L100](https://github.com/Buffer-Finance/Buffer-Protocol-v2_5/blob/84b6060b4447b2550de595202e8820c7f515988b/contracts/core/Booster.sol#L80-L100)

### Recommendation

Consider limiting boost purchases to only tokens currently listed for better UX

## [L-02] Using a single IV value is restrictive and can unfairly price option payouts

### Details

https://github.com/Buffer-Finance/Buffer-Protocol-v2_5/blob/84b6060b4447b2550de595202e8820c7f515988b/contracts/core/BufferBinaryOptions.sol#L381-L391

            profit =
                (option.lockedAmount *
                    OptionMath.blackScholesPriceBinary(
                        config.iv(),
                        option.strike,
                        closingPrice,
                        option.expiration - closingTime,
                        true,
                        isAbove
                    )) /
                1e8;

When determining profit the calculation always uses the same implied volatility. This is sub-optimal since a token like BTC will have much lower volatility than something like DOGE, causing them to be priced the same when they should be priced differently.

### Lines of Code

[BufferBinaryOptions.sol#L372-L401](https://github.com/Buffer-Finance/Buffer-Protocol-v2_5/blob/84b6060b4447b2550de595202e8820c7f515988b/contracts/core/BufferBinaryOptions.sol#L372-L401)

### Recommendation

Set the IV separately for each asset

## [L-03] registerAccount sub-call in BufferRouter#openTrades can revert entire transaction

### Details

[BufferRouter.sol#L144-L150](https://github.com/Buffer-Finance/Buffer-Protocol-v2_5/blob/84b6060b4447b2550de595202e8820c7f515988b/contracts/core/BufferRouter.sol#L144-L150)

            if (params[index].register.shouldRegister) {
                accountRegistrar.registerAccount(
                    params[index].register.oneCT,
                    user,
                    params[index].register.signature
                );
            }

The openTrades function has been designed to prevent it from reverting under almost every circumstance. The exception to this is that accountRegistrar.registerAccount can revert the entire transaction.

### Lines of Code

[BufferRouter.sol#L107-L165](https://github.com/Buffer-Finance/Buffer-Protocol-v2_5/blob/84b6060b4447b2550de595202e8820c7f515988b/contracts/core/BufferRouter.sol#L107-L165)

### Recommendation

Consider using a try-catch block to prevent it from reverting

## [I-01] Booster#buy should support buying multiple boosts at a time

### Details

Booster#buy only allows the purchase of one boost at a time. Consider allowing users to bulk buy boosts to save transactions and gas.

### Lines of Code

[Booster.sol#L80-L100](https://github.com/Buffer-Finance/Buffer-Protocol-v2_5/blob/84b6060b4447b2550de595202e8820c7f515988b/contracts/core/Booster.sol#L80-L100)

### Recommendation

Consider allowing multiple boosts to be purchased in a single transaction

## [I-02] OptionMath#\_decay is never used

### Details

OptionMath#\_decay is never used and should be removed

### Lines of Code

[OptionMath.sol#L24-L32](https://github.com/Buffer-Finance/Buffer-Protocol-v2_5/blob/84b6060b4447b2550de595202e8820c7f515988b/contracts/core/OptionMath.sol#L24-L32)

### Recommendation

OptionMath#\_decay should be removed
