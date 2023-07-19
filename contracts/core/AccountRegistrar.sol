// SPDX-License-Identifier: BUSL-1.1

pragma solidity 0.8.4;

import "../interfaces/Interfaces.sol";
import "../Libraries/Validator.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @author Heisenberg
 * @notice Buffer Options Router Contract
 */
contract AccountRegistrar is IAccountRegistrar, Ownable {
    mapping(address => AccountMapping) public override accountMapping;
    IBufferRouter public router;

    function setRouter(address _router) external onlyOwner {
        router = IBufferRouter(_router);
    }

    function registerAccount(
        address oneCT,
        address user,
        bytes memory signature
    ) external override onlyRouter {
        if (accountMapping[user].oneCT == oneCT) {
            return;
        }
        uint256 nonce = accountMapping[user].nonce;
        require(
            Validator.verifyUserRegistration(oneCT, user, nonce, signature),
            "AccountRegistrar: Invalid signature"
        );
        accountMapping[user].oneCT = oneCT;
        emit RegisterAccount(user, accountMapping[user].oneCT, nonce);
    }

    function deregisterAccount(
        address user,
        bytes memory signature
    ) external onlyRouter {
        if (accountMapping[user].oneCT == address(0)) {
            return;
        }
        uint256 nonce = accountMapping[user].nonce;
        require(
            Validator.verifyUserDeregistration(user, nonce, signature),
            "AccountRegistrar: Invalid signature"
        );
        accountMapping[msg.sender] = AccountMapping({
            nonce: nonce + 1,
            oneCT: address(0)
        });
    }

    modifier onlyRouter() {
        require(msg.sender == address(router));
        _;
    }
}
