// SPDX-License-Identifier: BUSL-1.1

pragma solidity 0.8.4;

import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "./interfaces/Interfaces.sol";

/**
 * @author Heisenberg
 * @title Buffer SettlementFeeDistributor
 * @notice Distributes the SettlementFee Collected by the Buffer Protocol
 */

contract SettlementFeeDistributor {
    using SafeERC20 for ERC20;

    address public shareHolder1;
    address public shareHolder2;
    address public shareHolder3;
    uint256 public shareHolderPercent1;
    uint256 public shareHolderPercent2;
    ERC20 public tokenX;

    event SetShareholderDetails(
        address shareHolder1,
        address shareHolder2,
        address shareHolder3,
        uint256 shareHolderPercent1,
        uint256 shareHolderPercent2,
        uint256 shareHolderPercent3
    );

    // All percentages are with a factor of e2

    constructor(
        ERC20 _tokenX,
        address _shareHolder1,
        address _shareHolder2,
        address _shareHolder3,
        uint256 _shareHolderPercent1,
        uint256 _shareHolderPercent2
    ) {
        tokenX = _tokenX;
        shareHolder1 = _shareHolder1;
        shareHolder2 = _shareHolder2;
        shareHolder3 = _shareHolder3;
        shareHolderPercent1 = _shareHolderPercent1;
        shareHolderPercent2 = _shareHolderPercent2;
        emit SetShareholderDetails(
            shareHolder1,
            shareHolder2,
            shareHolder3,
            shareHolderPercent1,
            shareHolderPercent2,
            10000 - shareHolderPercent1 - shareHolderPercent2
        );
    }

    function distribute() external {
        uint256 contractBalance = tokenX.balanceOf(address(this));
        if (contractBalance > 10 * (10 ** tokenX.decimals())) {
            uint256 amount1 = (contractBalance * shareHolderPercent1) / 10000;
            uint256 amount2 = (contractBalance * shareHolderPercent2) / 10000;
            uint256 amount3 = contractBalance - amount1 - amount2;
            tokenX.safeTransfer(shareHolder1, amount1);
            tokenX.safeTransfer(shareHolder2, amount2);
            tokenX.safeTransfer(shareHolder3, amount3);
        }
    }
}
