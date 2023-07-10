// SPDX-License-Identifier: BUSL-1.1

pragma solidity 0.8.4;

import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "../interfaces/Interfaces.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import "../Libraries/Validator.sol";

/**
 * @author Heisenberg
 * @notice Buffer Options Router Contract
 */
contract BufferRouter is AccessControl, IBufferRouter {
    using SafeERC20 for ERC20;
    uint16 public MAX_DELAY_FOR_OPEN_TRADE = 1 minutes;
    uint16 public MAX_DELAY_FOR_ASSET_PRICE = 1 minutes;

    address public publisher;
    address public sfPublisher;
    address public admin;
    bool public isInPrivateKeeperMode = true;
    IAccountRegistrar public accountRegistrar;

    mapping(uint256 => QueuedTrade) public queuedTrades;
    mapping(address => bool) public contractRegistry;
    mapping(address => bool) public isKeeper;
    mapping(bytes => bool) public prevSignature;
    mapping(address => mapping(uint256 => uint256)) public optionIdMapping;

    constructor(
        address _publisher,
        address _sfPublisher,
        address _admin,
        address _accountRegistrar
    ) {
        publisher = _publisher;
        sfPublisher = _sfPublisher;
        admin = _admin;
        accountRegistrar = IAccountRegistrar(_accountRegistrar);

        _setupRole(DEFAULT_ADMIN_ROLE, msg.sender);
    }

    /************************************************
     *  ADMIN ONLY FUNCTIONS
     ***********************************************/

    function setContractRegistry(
        address targetContract,
        bool register
    ) external onlyRole(DEFAULT_ADMIN_ROLE) {
        contractRegistry[targetContract] = register;

        emit ContractRegistryUpdated(targetContract, register);
    }

    function setKeeper(
        address _keeper,
        bool _isActive
    ) external onlyRole(DEFAULT_ADMIN_ROLE) {
        isKeeper[_keeper] = _isActive;
    }

    function setInPrivateKeeperMode() external onlyRole(DEFAULT_ADMIN_ROLE) {
        isInPrivateKeeperMode = !isInPrivateKeeperMode;
    }

    /************************************************
     *  KEEPER ONLY FUNCTIONS
     ***********************************************/

    function openTrades(TradeParams[] calldata params) external {
        _validateKeeper();
        for (uint32 index = 0; index < params.length; index++) {
            TradeParams memory currentParams = params[index];
            (bool isValid, string memory errorResaon) = verifyTrade(
                currentParams
            );
            if (!isValid) {
                emit FailResolve(currentParams.queueId, errorResaon);
                continue;
            }
            _openTrade(currentParams);
        }
    }

    function closeAnytime(CloseAnytimeParams[] memory closeParams) external {
        _validateKeeper();
        // TODO: add validation to check if the user signed this
        for (uint32 index = 0; index < closeParams.length; index++) {
            SignInfo memory userSignInfo = closeParams[index].userSignInfo;
            CloseTradeParams memory params = closeParams[index]
                .closeTradeParams;
            uint256 queueId = optionIdMapping[params.targetContract][
                params.optionId
            ];
            IBufferBinaryOptions optionsContract = IBufferBinaryOptions(
                params.targetContract
            );
            IBufferRouter.SignInfo memory publisherSignInfo = params
                .publisherSignInfo;
            QueuedTrade memory queuedTrade = queuedTrades[queueId];
            (, , , , , , , uint256 createdAt) = optionsContract.options(
                params.optionId
            );
            if (
                !queuedTrade.isEarlyCloseAllowed ||
                (block.timestamp - createdAt <
                    IOptionsConfig(optionsContract.config())
                        .earlyCloseThreshold())
            ) {
                emit FailUnlock(
                    params.optionId,
                    params.targetContract,
                    "Router: Early close is not allowed"
                );
                continue;
            }
            bool isUserSignValid = Validator.verifyCloseAnytime(
                optionsContract.assetPair(),
                publisherSignInfo.timestamp,
                params.optionId,
                userSignInfo.signature,
                getAccountMapping(queuedTrade.user)
            );

            bool isSignerVerifed = Validator.verifyPublisher(
                optionsContract.assetPair(),
                publisherSignInfo.timestamp,
                params.closingPrice,
                publisherSignInfo.signature,
                publisher
            );

            // Silently fail if the signature doesn't match
            if (!isSignerVerifed) {
                emit FailUnlock(
                    params.optionId,
                    params.targetContract,
                    "Router: Publisher signature didn't match"
                );
                continue;
            }
            if (!isUserSignValid) {
                emit FailUnlock(
                    params.optionId,
                    params.targetContract,
                    "Router: User signature didn't match"
                );
                continue;
            }

            if (
                !Validator.verifyMarketDirection(
                    params,
                    queuedTrade,
                    getAccountMapping(queuedTrade.user)
                )
            ) {
                emit FailUnlock(
                    params.optionId,
                    params.targetContract,
                    "Router: Wrong market direction"
                );
                continue;
            }

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
        }
    }

    function executeOptions(CloseTradeParams[] calldata optionData) external {
        _validateKeeper();

        uint32 arrayLength = uint32(optionData.length);
        for (uint32 i = 0; i < arrayLength; i++) {
            CloseTradeParams memory params = optionData[i];
            uint256 queueId = optionIdMapping[params.targetContract][
                params.optionId
            ];
            IBufferBinaryOptions optionsContract = IBufferBinaryOptions(
                params.targetContract
            );
            (, , , , , uint256 expiration, , ) = optionsContract.options(
                params.optionId
            );
            IBufferRouter.SignInfo memory signInfo = params.publisherSignInfo;

            bool isSignerVerifed = Validator.verifyPublisher(
                optionsContract.assetPair(),
                signInfo.timestamp,
                params.closingPrice,
                signInfo.signature,
                publisher
            );

            // Silently fail if the signature doesn't match
            if (!isSignerVerifed) {
                emit FailUnlock(
                    params.optionId,
                    params.targetContract,
                    "Router: Signature didn't match"
                );
                continue;
            }

            QueuedTrade memory queuedTrade = queuedTrades[queueId];

            if (
                !Validator.verifyMarketDirection(
                    params,
                    queuedTrade,
                    getAccountMapping(queuedTrade.user)
                )
            ) {
                emit FailUnlock(
                    params.optionId,
                    params.targetContract,
                    "Router: Wrong market direction"
                );
                continue;
            }

            // Silently fail if the timestamp of the signature is wrong
            if (expiration != signInfo.timestamp) {
                emit FailUnlock(
                    params.optionId,
                    params.targetContract,
                    "Router: Wrong price"
                );
                continue;
            } else if (expiration > block.timestamp) {
                emit FailUnlock(
                    params.optionId,
                    params.targetContract,
                    "Router: Wrong closing time"
                );
                continue;
            }

            try
                optionsContract.unlock(
                    params.optionId,
                    params.closingPrice,
                    expiration,
                    params.isAbove
                )
            {} catch Error(string memory reason) {
                emit FailUnlock(params.optionId, params.targetContract, reason);
                continue;
            }
        }
    }

    /************************************************
     *  INTERNAL FUNCTIONS
     ***********************************************/
    function _validateKeeper() private view {
        require(
            !isInPrivateKeeperMode || isKeeper[msg.sender],
            "Keeper: forbidden"
        );
    }

    function getAccountMapping(address user) public view returns (address) {
        (address oneCT, ) = accountRegistrar.accountMapping(user);
        return oneCT;
    }

    function verifyTrade(
        TradeParams memory params
    ) public view returns (bool, string memory) {
        IBufferBinaryOptions optionsContract = IBufferBinaryOptions(
            params.targetContract
        );
        SignInfo memory settlementFeeSignInfo = params.settlementFeeSignInfo;
        SignInfo memory publisherSignInfo = params.publisherSignInfo;
        SignInfo memory userSignInfo = params.userSignInfo;

        if (!contractRegistry[params.targetContract]) {
            return (false, "Router: Unauthorized contract");
        }
        if (queuedTrades[params.queueId].isTradeResolved) {
            return (false, "Router: Trade has already been opened");
        }
        if (prevSignature[userSignInfo.signature]) {
            return (false, "Router: Signature already used");
        }
        if (
            !Validator.verifyUserTradeParams(
                params,
                getAccountMapping(params.user)
            )
        ) {
            return (false, "Router: User signature didn't match");
        }
        if (
            !Validator.verifySettlementFee(
                optionsContract.assetPair(),
                params.settlementFee,
                settlementFeeSignInfo.timestamp,
                settlementFeeSignInfo.signature,
                sfPublisher
            )
        ) {
            return (false, "Router: Wrong settlement fee");
        }
        if (
            !Validator.verifyPublisher(
                optionsContract.assetPair(),
                publisherSignInfo.timestamp,
                params.price,
                publisherSignInfo.signature,
                publisher
            )
        ) {
            return (false, "Router: Publisher signature didn't match");
        }
        if (settlementFeeSignInfo.timestamp < block.timestamp) {
            return (false, "Router: Settlement fee has expired");
        }
        if (!params.isLimitOrder) {
            if (
                block.timestamp - userSignInfo.timestamp >
                MAX_DELAY_FOR_OPEN_TRADE
            ) {
                return (false, "Router: Invalid user signature timestamp");
            }
        } else {
            if (block.timestamp > params.limitOrderExpiry) {
                return (false, "Router: Limit order has already expired");
            }
        }
        if (
            block.timestamp - publisherSignInfo.timestamp >
            MAX_DELAY_FOR_ASSET_PRICE
        ) {
            return (false, "Router: Invalid publisher signature timestamp");
        }
        if (
            !optionsContract.isStrikeValid(
                params.slippage,
                params.price,
                params.strike
            )
        ) {
            return (false, "Router: Slippage limit exceeds");
        }
        return (true, "");
    }

    function _openTrade(TradeParams memory params) internal {
        IBufferBinaryOptions optionsContract = IBufferBinaryOptions(
            params.targetContract
        );
        SignInfo memory publisherSignInfo = params.publisherSignInfo;
        SignInfo memory userSignInfo = params.userSignInfo;
        IOptionsConfig config = IOptionsConfig(optionsContract.config());
        uint256 platformFee = config.platformFee();

        // Check all the parameters and compute the amount and revised fee
        uint256 amount;
        uint256 revisedFee;
        IBufferBinaryOptions.OptionParams
            memory optionParams = IBufferBinaryOptions.OptionParams(
                params.strike,
                0,
                params.period,
                params.allowPartialFill,
                params.totalFee - platformFee,
                params.user,
                params.referralCode,
                params.settlementFee
            );

        try
            optionsContract.evaluateParams(optionParams, params.slippage)
        returns (uint256 _amount, uint256 _revisedFee) {
            (amount, revisedFee) = (_amount, _revisedFee);
        } catch Error(string memory reason) {
            emit CancelTrade(params.user, params.queueId, reason);
            return;
        }

        // Transfer the fee specified from the user to options contract.
        // User has to approve first inorder to execute this function
        ERC20 tokenX = ERC20(optionsContract.tokenX());

        tokenX.safeTransferFrom(params.user, admin, platformFee);
        tokenX.safeTransferFrom(params.user, params.targetContract, revisedFee);

        optionParams.strike = params.price;
        optionParams.amount = amount;

        uint256 optionId = optionsContract.createFromRouter(
            optionParams,
            publisherSignInfo.timestamp
        );
        queuedTrades[params.queueId] = QueuedTrade({
            user: params.user,
            targetContract: params.targetContract,
            strike: params.strike,
            slippage: params.slippage,
            period: params.period,
            allowPartialFill: params.allowPartialFill,
            totalFee: params.totalFee,
            referralCode: params.referralCode,
            traderNFTId: params.traderNFTId,
            settlementFee: params.settlementFee,
            isLimitOrder: params.isLimitOrder,
            isTradeResolved: true,
            optionId: optionId,
            isEarlyCloseAllowed: config.isEarlyCloseAllowed()
        });
        optionIdMapping[params.targetContract][optionId] = params.queueId;
        prevSignature[userSignInfo.signature] = true;

        emit OpenTrade(
            params.user,
            params.queueId,
            optionId,
            params.targetContract
        );
    }

    // TODO: remove later
    function verifySF(
        string memory assetPair,
        uint256 settlementFee,
        uint256 expiryTimestamp,
        bytes memory signature,
        address signer
    ) public view returns (bool) {
        return
            Validator.verifySettlementFee(
                assetPair,
                settlementFee,
                expiryTimestamp,
                signature,
                signer
            );
    }
}
