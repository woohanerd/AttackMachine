import random

from settings import DST_CHAIN_ZERIUS_NFT, DST_CHAIN_ZERIUS_REFUEL
from config import ZERIUS_CONTRACT_PER_CHAINS, ZERIUS_ABI, ZERO_ADDRESS, LAYERZERO_NETWORKS_DATA
from utils.tools import gas_checker, helper, sleep
from eth_abi import encode
from modules import Minter, Logger


class Zerius(Minter, Logger):
    def __init__(self, client, chain_from_id):
        Logger.__init__(self)
        self.client = client

        self.chain_from_id = chain_from_id
        self.network = self.client.network.name
        self.onft_contract = self.client.get_contract(
            ZERIUS_CONTRACT_PER_CHAINS[chain_from_id]['ONFT'],
            ZERIUS_ABI['ONFT'])
        self.refuel_contract = self.client.get_contract(
            ZERIUS_CONTRACT_PER_CHAINS[chain_from_id]['refuel'],
            ZERIUS_ABI['refuel'])

    async def get_nft_id(self):
        balance_nft = await self.onft_contract.functions.balanceOf(self.client.address).call()
        nft_ids = []
        for i in range(balance_nft):
            nft_ids.append(await self.onft_contract.functions.tokenOfOwnerByIndex(self.client.address, i).call())
        if nft_ids:
            return nft_ids[-1]
        return False

    async def get_estimate_send_fee(self, adapter_params, dst_chain_id, nft_id):

        estimate_send_fee = (await self.onft_contract.functions.estimateSendFee(
            dst_chain_id,
            self.client.address,
            nft_id,
            False,
            adapter_params
        ).call())[0]

        return estimate_send_fee

    @helper
    @gas_checker
    async def mint(self):
        mint_price = await self.onft_contract.functions.mintFee().call()

        self.logger_msg(
            *self.client.acc_info, msg=f"Mint Zerius NFT on {self.network}. "
                                       f"Mint Price: {(mint_price / 10 ** 18):.5f} {self.client.network.token}")

        tx_params = await self.client.prepare_transaction(value=mint_price)

        transaction = await self.onft_contract.functions.mint(
            '0x000000a679C2FB345dDEfbaE3c42beE92c0Fb7A5'
        ).build_transaction(tx_params)

        return await self.client.send_transaction(transaction)

    @helper
    @gas_checker
    async def bridge(self, attack_mode:bool = False, attack_data:dict = False):
        if not attack_mode:
            dst_chain = random.choice(DST_CHAIN_ZERIUS_NFT)
        else:
            dst_chain = attack_data

        dst_chain_name, dst_chain_id, _, _ = LAYERZERO_NETWORKS_DATA[dst_chain]

        nft_id = await self.get_nft_id()

        if not nft_id:
            await self.mint()
            nft_id = await self.get_nft_id()

        self.logger_msg(
            *self.client.acc_info,
            msg=f"Bridge Zerius NFT from {self.network} to {dst_chain_name}. ID: {nft_id}")

        await sleep(self, 5, 10)

        version, gas_limit = 1, await self.onft_contract.functions.minDstGasLookup(dst_chain_id, 1).call()

        adapter_params = encode(["uint16", "uint256"],
                                [version, gas_limit])

        adapter_params = self.client.w3.to_hex(adapter_params[30:]) + self.client.address[2:].lower()

        base_bridge_fee = await self.onft_contract.functions.bridgeFee().call()
        estimate_send_fee = await self.get_estimate_send_fee(adapter_params, dst_chain_id, nft_id)

        tx_params = await self.client.prepare_transaction(value=estimate_send_fee + base_bridge_fee)

        transaction = await self.onft_contract.functions.sendFrom(
            self.client.address,
            dst_chain_id,
            self.client.address,
            nft_id,
            self.client.address,
            ZERO_ADDRESS,
            adapter_params
        ).build_transaction(tx_params)

        return await self.client.send_transaction(transaction)

    @helper
    @gas_checker
    async def refuel(self, attack_mode:bool = False, attack_data:dict = False):
        if not attack_mode:
            dst_data = random.choice(list(DST_CHAIN_ZERIUS_REFUEL.items()))
        else:
            dst_data = random.choice(list(attack_data.items()))

        dst_chain_name, dst_chain_id, dst_native_name, dst_native_api_name = LAYERZERO_NETWORKS_DATA[dst_data[0]]
        dst_amount = self.client.round_amount(*dst_data[1])

        refuel_info = f'{dst_amount} {dst_native_name} to {dst_chain_name}'
        self.logger_msg(*self.client.acc_info, msg=f'Refuel on Zerius: {refuel_info}')

        dst_native_gas_amount = int(dst_amount * 10 ** 18)
        dst_contract_address = ZERIUS_CONTRACT_PER_CHAINS[self.chain_from_id]['refuel']

        gas_limit = await self.refuel_contract.functions.minDstGasLookup(dst_chain_id, 0).call()

        adapter_params = encode(["uint16", "uint64", "uint256"],
                                [2, gas_limit, dst_native_gas_amount])

        adapter_params = self.client.w3.to_hex(adapter_params[30:]) + self.client.address[2:].lower()

        estimate_send_fee = (await self.refuel_contract.functions.estimateSendFee(
            dst_chain_id,
            dst_contract_address,
            adapter_params
        ).call())[0]

        tx_params = await self.client.prepare_transaction(value=estimate_send_fee)

        transaction = await self.refuel_contract.functions.refuel(
            dst_chain_id,
            dst_contract_address,
            adapter_params
        ).build_transaction(tx_params)

        tx_hash = await self.client.send_transaction(transaction, need_hash=True)

        return await self.client.wait_for_l0_received(tx_hash)
