pragma solidity 0.8.4;

import "./interfaces/Interfaces.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract MarketOIConfig is Ownable {
    uint256 private _maxMarketOI;
    uint256 private _maxTradeSize;
    IBufferBinaryOptions private _marketContract;

    constructor(
        uint256 maxMarketOI,
        uint256 maxTradeSize,
        IBufferBinaryOptions marketContract
    ) {
        _maxMarketOI = maxMarketOI;
        _maxTradeSize = maxTradeSize;
        _marketContract = marketContract;
    }

    function setMaxMarketOI(uint256 maxMarketOI) external onlyOwner {
        _maxMarketOI = maxMarketOI;
    }

    function setMaxTradeSize(uint256 maxTradeSize) external onlyOwner {
        _maxTradeSize = maxTradeSize;
    }

    function getMaxMarketOI(
        uint256 currentMarketOI
    ) external view returns (uint256) {
        uint256 remainingOI = _maxMarketOI - currentMarketOI;
        return remainingOI < _maxTradeSize ? remainingOI : _maxTradeSize;
    }

    function getMarketOICap() external view returns (uint256) {
        return _maxMarketOI;
    }
}
