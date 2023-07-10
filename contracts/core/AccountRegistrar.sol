// SPDX-License-Identifier: BUSL-1.1

pragma solidity 0.8.4;

import "../interfaces/Interfaces.sol";

/**
 * @author Heisenberg
 * @notice Buffer Options Router Contract
 */
contract AccountRegistrar is IAccountRegistrar {
    mapping(address => AccountMapping) public override accountMapping;

    function registerAccount(address oneCT) external {
        accountMapping[msg.sender].oneCT = oneCT;
        emit RegisterAccount(msg.sender, oneCT);
    }

    function deregisterAccount() external {
        accountMapping[msg.sender] = AccountMapping({
            nonce: accountMapping[msg.sender].nonce + 1,
            oneCT: address(0)
        });
    }
}
