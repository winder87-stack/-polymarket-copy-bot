"""
Mock Web3 provider for testing blockchain interactions.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Union

logger = logging.getLogger(__name__)


class Web3MockProvider:
    """Mock Web3 provider for testing blockchain interactions."""

    def __init__(self):
        self.connected = True
        self.current_block = 50000000
        self.gas_price = 50000000000  # 50 gwei
        self.chain_id = 137  # Polygon

        # Mock blockchain state
        self.blocks: Dict[int, Dict[str, Any]] = {}
        self.transactions: Dict[str, Dict[str, Any]] = {}
        self.contracts: Dict[str, Dict[str, Any]] = {}
        self.balances: Dict[str, int] = {}
        self.logs: List[Dict[str, Any]] = []

        # Error simulation
        self.should_fail = False
        self.fail_with_exception = None
        self.delay_responses = False
        self.response_delay = 0.05

        self._setup_default_data()

    def _setup_default_data(self):
        """Set up default mock blockchain data."""
        # Default balances (in wei)
        self.balances = {
            "0x742d35Cc6634C0532925a3b844Bc454e4438f44e": 1000000000000000000000,  # 1000 ETH
            "0x2791bca1f2de4661ed88a30c99a7a9449aa84174": 1000000000000000000000000,  # 1M USDC (contract)
        }

        # Default contracts
        self.contracts = {
            "0x2791bca1f2de4661ed88a30c99a7a9449aa84174": {  # USDC on Polygon
                "address": "0x2791bca1f2de4661ed88a30c99a7a9449aa84174",
                "abi": self._get_erc20_abi(),
                "name": "USD Coin",
            },
            "0x42f5d81136d8b8c6e2e5f5abd46a5f9be4457b3a": {  # Polymarket AMM
                "address": "0x42f5d81136d8b8c6e2e5f5abd46a5f9be4457b3a",
                "abi": [],  # Would contain actual ABI
                "name": "Polymarket AMM",
            },
        }

        # Create some default blocks
        for i in range(10):
            block_num = self.current_block - i
            self.blocks[block_num] = self._create_mock_block(block_num)

    def _get_erc20_abi(self) -> List[Dict[str, Any]]:
        """Get ERC20 ABI for testing."""
        return [
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function",
            },
            {
                "constant": True,
                "inputs": [],
                "name": "decimals",
                "outputs": [{"name": "", "type": "uint8"}],
                "type": "function",
            },
            {
                "constant": True,
                "inputs": [],
                "name": "symbol",
                "outputs": [{"name": "", "type": "string"}],
                "type": "function",
            },
        ]

    def _create_mock_block(self, block_number: int) -> Dict[str, Any]:
        """Create a mock block for testing."""
        return {
            "number": block_number,
            "hash": f"0xblock{block_number:064x}",
            "parentHash": f"0xblock{block_number-1:064x}",
            "timestamp": int((datetime.now() - timedelta(minutes=block_number)).timestamp()),
            "transactions": [
                f"0xtx{block_number}_{i:064x}" for i in range(min(5, block_number % 10))
            ],
            "gasUsed": "0x123456",
            "gasLimit": "0x1c9c380",
        }

    def _create_mock_transaction(self, tx_hash: str) -> Dict[str, Any]:
        """Create a mock transaction."""
        return {
            "hash": tx_hash,
            "blockNumber": self.current_block,
            "from": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
            "to": "0x42f5d81136d8b8c6e2e5f5abd46a5f9be4457b3a",
            "value": "0x0",
            "gas": "0x493e0",
            "gasPrice": hex(self.gas_price),
            "input": "0x1234567890abcdef",
            "nonce": "0x1",
            "v": "0x1b",
            "r": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            "s": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        }

    # Web3 interface methods
    def is_connected(self) -> bool:
        """Check if connected to blockchain."""
        if self.should_fail:
            return False
        return self.connected

    def eth_block_number(self) -> int:
        """Get current block number."""
        if self.should_fail and self.fail_with_exception:
            raise self.fail_with_exception
        return self.current_block

    def eth_gas_price(self) -> int:
        """Get current gas price."""
        if self.should_fail and self.fail_with_exception:
            raise self.fail_with_exception
        return self.gas_price

    def eth_get_block(
        self, block_number: Union[int, str], full_transactions: bool = False
    ) -> Dict[str, Any]:
        """Get block by number."""
        if self.should_fail and self.fail_with_exception:
            raise self.fail_with_exception

        if isinstance(block_number, str):
            if block_number == "latest":
                block_number = self.current_block
            elif block_number.startswith("0x"):
                block_number = int(block_number, 16)

        block = self.blocks.get(int(block_number))
        if not block:
            raise Exception(f"Block {block_number} not found")

        if full_transactions:
            # Return full transaction objects
            block = block.copy()
            block["transactions"] = [
                self._create_mock_transaction(tx_hash) for tx_hash in block["transactions"]
            ]

        return block

    def eth_get_transaction(self, tx_hash: str) -> Dict[str, Any]:
        """Get transaction by hash."""
        if self.should_fail and self.fail_with_exception:
            raise self.fail_with_exception

        return self.transactions.get(tx_hash, self._create_mock_transaction(tx_hash))

    def eth_call(self, transaction: Dict[str, Any], block_identifier: str = "latest") -> str:
        """Execute eth_call."""
        if self.should_fail and self.fail_with_exception:
            raise self.fail_with_exception

        # Simulate contract calls
        to_address = transaction.get("to", "").lower()

        if to_address == "0x2791bca1f2de4661ed88a30c99a7a9449aa84174":  # USDC contract
            # Mock balanceOf call
            if transaction.get("data", "").startswith("0x70a08231"):  # balanceOf selector
                owner = transaction["data"][34:74]  # Extract address from call data
                balance = self.balances.get(f"0x{owner}", 0)
                return hex(balance)[2:].zfill(64)  # Return as 32-byte hex

        return "0x"

    def eth_estimate_gas(self, transaction: Dict[str, Any]) -> int:
        """Estimate gas for transaction."""
        if self.should_fail and self.fail_with_exception:
            raise self.fail_with_exception
        return 250000  # Default gas estimate

    # Test control methods
    def set_should_fail(self, should_fail: bool, exception: Exception = None):
        """Set failure mode for testing."""
        self.should_fail = should_fail
        self.fail_with_exception = exception

    def set_response_delay(self, delay: float):
        """Set response delay for testing."""
        self.delay_responses = True
        self.response_delay = delay

    def reset_delays(self):
        """Reset response delays."""
        self.delay_responses = False
        self.response_delay = 0.05

    def advance_block(self, blocks: int = 1):
        """Advance the current block number."""
        self.current_block += blocks
        # Add new blocks
        for i in range(blocks):
            block_num = self.current_block - blocks + i + 1
            self.blocks[block_num] = self._create_mock_block(block_num)

    def set_gas_price(self, gas_price: int):
        """Set the gas price for testing."""
        self.gas_price = gas_price

    def set_balance(self, address: str, balance: int):
        """Set balance for an address."""
        self.balances[address.lower()] = balance

    def add_transaction(self, tx_hash: str, transaction: Dict[str, Any]):
        """Add a transaction to the mock state."""
        self.transactions[tx_hash] = transaction

    def add_contract(self, address: str, abi: List[Dict[str, Any]], name: str = ""):
        """Add a contract to the mock state."""
        self.contracts[address.lower()] = {"address": address, "abi": abi, "name": name}

    def clear_state(self):
        """Clear all mock state."""
        self.blocks.clear()
        self.transactions.clear()
        self.contracts.clear()
        self.balances.clear()
        self.logs.clear()
        self._setup_default_data()


class MockWeb3:
    """Mock Web3 instance that mimics the web3.py interface."""

    def __init__(self, provider: Web3MockProvider = None):
        self.provider = provider or Web3MockProvider()
        self.eth = self  # Web3.eth is the same object

    def is_connected(self) -> bool:
        """Check connection status."""
        return self.provider.is_connected()

    @property
    def block_number(self) -> int:
        """Get current block number."""
        return self.provider.eth_block_number()

    @property
    def gas_price(self) -> int:
        """Get current gas price."""
        return self.provider.eth_gas_price()

    def get_block(
        self, block_number: Union[int, str], full_transactions: bool = False
    ) -> Dict[str, Any]:
        """Get block by number."""
        return self.provider.eth_get_block(block_number, full_transactions)

    def get_transaction(self, tx_hash: str) -> Dict[str, Any]:
        """Get transaction by hash."""
        return self.provider.eth_get_transaction(tx_hash)

    def call(self, transaction: Dict[str, Any], block_identifier: str = "latest") -> str:
        """Execute call."""
        return self.provider.eth_call(transaction, block_identifier)

    def estimate_gas(self, transaction: Dict[str, Any]) -> int:
        """Estimate gas."""
        return self.provider.eth_estimate_gas(transaction)

    def to_checksum_address(self, address: str) -> str:
        """Convert to checksum address."""
        return address  # Simplified for testing

    def from_wei(self, value: int, unit: str) -> Union[int, float]:
        """Convert from wei."""
        if unit == "ether":
            return value / 10**18
        elif unit == "gwei":
            return value / 10**9
        return value

    def to_wei(self, value: Union[int, float, str], unit: str) -> int:
        """Convert to wei."""
        if unit == "ether":
            return int(float(value) * 10**18)
        elif unit == "gwei":
            return int(float(value) * 10**9)
        return int(value)


class MockContract:
    """Mock contract for testing contract interactions."""

    def __init__(self, web3_mock: MockWeb3, address: str, abi: List[Dict[str, Any]]):
        self.web3 = web3_mock
        self.address = address
        self.abi = abi
        self.functions = MockContractFunctions(self)

    def __getitem__(self, key):
        """Allow dictionary-style access."""
        return getattr(self, key, None)


class MockContractFunctions:
    """Mock contract functions."""

    def __init__(self, contract: MockContract):
        self.contract = contract

    def balanceOf(self, address: str) -> "MockContractCall":
        """Mock balanceOf function."""
        return MockContractCall(self.contract, "balanceOf", [address])


class MockContractCall:
    """Mock contract call."""

    def __init__(self, contract: MockContract, function_name: str, args: List[Any]):
        self.contract = contract
        self.function_name = function_name
        self.args = args

    def call(self) -> Any:
        """Execute the contract call."""
        if self.function_name == "balanceOf":
            address = self.args[0]
            # Return balance from mock provider
            return self.contract.web3.provider.balances.get(address.lower(), 0)
        return 0


# Factory functions for easy testing
def create_mock_web3() -> MockWeb3:
    """Create a mock Web3 instance for testing."""
    return MockWeb3()


def create_web3_with_custom_state(
    balances: Dict[str, int] = None, gas_price: int = None
) -> MockWeb3:
    """Create Web3 mock with custom state."""
    provider = Web3MockProvider()

    if balances:
        provider.balances.update(balances)

    if gas_price:
        provider.gas_price = gas_price

    return MockWeb3(provider)


def create_mock_contract(web3: MockWeb3, address: str) -> MockContract:
    """Create a mock contract for testing."""
    abi = Web3MockProvider()._get_erc20_abi()
    return MockContract(web3, address, abi)


if __name__ == "__main__":
    # Example usage
    web3 = create_mock_web3()

    print(f"Connected: {web3.is_connected()}")
    print(f"Block number: {web3.block_number}")
    print(f"Gas price: {web3.gas_price}")

    # Test contract interaction
    usdc_address = "0x2791bca1f2de4661ed88a30c99a7a9449aa84174"
    contract = create_mock_contract(web3, usdc_address)

    balance = contract.functions.balanceOf("0x742d35Cc6634C0532925a3b844Bc454e4438f44e").call()
    print(f"USDC Balance: {balance}")
