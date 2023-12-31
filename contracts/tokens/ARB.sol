// SPDX-License-Identifier: BUSL-1.1

pragma solidity 0.8.4;

import "@openzeppelin/contracts/utils/Address.sol";
import "@openzeppelin/contracts/token/ERC20/ERC20.sol";

contract ARB is ERC20("ARB", "ARB") {
    constructor() {
        uint256 INITIAL_SUPPLY = 1000 * 10 ** 6 * 10 ** decimals();
        _mint(msg.sender, INITIAL_SUPPLY);
    }

    function decimals() public view virtual override returns (uint8) {
        return 18;
    }
}
