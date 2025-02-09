import random

from config import ETH_PRICE, TOKENS_PER_CHAIN, LAYERZERO_WRAPED_NETWORKS, LAYERZERO_NETWORKS_DATA, \
    TOKENS_PER_CHAIN2
from modules import Logger, Aggregator
from general_settings import GLOBAL_NETWORK, AMOUNT_PERCENT_WRAPS
from settings import OKX_BALANCE_WANTED, STARGATE_CHAINS, STARGATE_TOKENS, \
    MEMCOIN_AMOUNT, MERKLY_ATTACK_REFUEL, L2PASS_ATTACK_REFUEL, L2PASS_ATTACK_NFT, ZERIUS_ATTACK_REFUEL, \
    ZERIUS_ATTACK_NFT, SHUFFLE_ATTACK
from utils.tools import helper, gas_checker, sleep


class Custom(Logger, Aggregator):
    def __init__(self, client):
        Logger.__init__(self)
        Aggregator.__init__(self, client)

    async def swap(self):
        pass

    async def collect_eth_util(self):
        from functions import swap_odos, swap_oneinch, swap_openocean, swap_xyfinance, swap_rango, swap_avnu

        self.logger_msg(*self.client.acc_info, msg=f"Stark collecting tokens to ETH")

        func = {
            3: [swap_odos, swap_oneinch, swap_openocean, swap_xyfinance],
            4: [swap_rango, swap_openocean, swap_xyfinance],
            8: [swap_openocean, swap_xyfinance],
            9: [swap_avnu],
            11: [swap_openocean, swap_xyfinance, swap_odos, swap_oneinch]
        }[GLOBAL_NETWORK]

        wallet_balance = {k: await self.client.get_token_balance(k, False)
                          for k, v in TOKENS_PER_CHAIN[self.client.network.name].items()}
        valid_wallet_balance = {k: v[1] for k, v in wallet_balance.items() if v[0] != 0}
        eth_price = ETH_PRICE

        if 'ETH' in valid_wallet_balance:
            valid_wallet_balance['ETH'] = valid_wallet_balance['ETH'] * eth_price

        if valid_wallet_balance['ETH'] < 0.5:
            self.logger_msg(*self.client.acc_info, msg=f'Account has not enough ETH for swap', type_msg='warning')
            return True

        if len(valid_wallet_balance.values()) > 1:

            for token_name, token_balance in valid_wallet_balance.items():
                if token_name != 'ETH':
                    amount_in_wei = wallet_balance[token_name][0]
                    amount = float(f"{(amount_in_wei / 10 ** await self.client.get_decimals(token_name)):.6f}")
                    amount_in_usd = valid_wallet_balance[token_name]
                    if amount_in_usd > 1:
                        from_token_name, to_token_name = token_name, 'ETH'
                        data = from_token_name, to_token_name, amount, amount_in_wei
                        counter = 0
                        while True:
                            result = False
                            module_func = random.choice(func)
                            try:
                                self.logger_msg(*self.client.acc_info, msg=f'Launching swap module', type_msg='warning')
                                result = await module_func(self.client.account_name, self.client.private_key,
                                                           self.client.network, self.client.proxy_init, swapdata=data)
                            except:
                                counter += 1
                                pass
                            if result or counter == 3:
                                break
                    else:
                        self.logger_msg(*self.client.acc_info, msg=f"{token_name} balance < 1$")

            return True
        else:
            raise RuntimeError('Account balance already in ETH!')

    @helper
    @gas_checker
    async def collect_eth(self):
        await self.collect_eth_util()

    @helper
    @gas_checker
    async def balance_average(self):
        from functions import okx_withdraw

        self.logger_msg(*self.client.acc_info, msg=f"Stark check all balance to make average")

        amount = OKX_BALANCE_WANTED
        wanted_amount_in_usd = float(f'{amount * ETH_PRICE:.2f}')

        wallet_balance = {k: await self.client.get_token_balance(k, False)
                          for k, v in TOKENS_PER_CHAIN[self.client.network.name].items()}
        valid_wallet_balance = {k: v[1] for k, v in wallet_balance.items() if v[0] != 0}
        eth_price = ETH_PRICE

        if 'ETH' in valid_wallet_balance:
            valid_wallet_balance['ETH'] = valid_wallet_balance['ETH'] * eth_price

        valid_wallet_balance = {k: round(v, 7) for k, v in valid_wallet_balance.items()}

        sum_balance_in_usd = sum(valid_wallet_balance.values())

        if wanted_amount_in_usd > sum_balance_in_usd:
            need_to_withdraw = float(f"{(wanted_amount_in_usd - sum_balance_in_usd) / eth_price:.6f}")

            self.logger_msg(*self.client.acc_info, msg=f"Not enough balance on account, start OKX withdraw module")

            return await okx_withdraw(self.client.account_name, self.client.private_key, self.client.network,
                                      self.client.proxy_init, want_balance=need_to_withdraw)
        raise RuntimeError('Account has enough tokens on balance!')

    @helper
    @gas_checker
    async def wraps_abuser(self):
        from functions import swap_odos, swap_oneinch, swap_xyfinance, swap_avnu

        func = {
            3: [swap_odos, swap_oneinch, swap_xyfinance],
            4: [swap_xyfinance],
            8: [swap_xyfinance],
            9: [swap_avnu],
            11: [swap_oneinch, swap_xyfinance]
        }[GLOBAL_NETWORK]

        current_tokens = list(TOKENS_PER_CHAIN[self.client.network.name].items())[:2]

        wallet_balance = {k: await self.client.get_token_balance(k, False) for k, v in current_tokens}
        valid_wallet_balance = {k: v[1] for k, v in wallet_balance.items() if v[0] != 0}
        eth_price = ETH_PRICE

        if 'ETH' in valid_wallet_balance:
            valid_wallet_balance['ETH'] = valid_wallet_balance['ETH'] * eth_price

        if 'WETH' in valid_wallet_balance:
            valid_wallet_balance['WETH'] = valid_wallet_balance['WETH'] * eth_price

        max_token = max(valid_wallet_balance, key=lambda x: valid_wallet_balance[x])
        percent = round(random.uniform(*AMOUNT_PERCENT_WRAPS), 9) / 100 if max_token == 'ETH' else 1
        amount_in_wei = int(wallet_balance[max_token][0] * percent)
        amount = float(f"{amount_in_wei / 10 ** 18:.6f}")

        if max_token == 'ETH':
            msg = f'Wrap {amount:.6f} ETH'
            from_token_name, to_token_name = 'ETH', 'WETH'
        else:
            msg = f'Unwrap {amount:.6f} WETH'
            from_token_name, to_token_name = 'WETH', 'ETH'

        self.logger_msg(*self.client.acc_info, msg=msg)

        if (max_token == 'ETH' and valid_wallet_balance[max_token] > 1
                or max_token == 'WETH' and valid_wallet_balance[max_token] != 0):
            data = from_token_name, to_token_name, amount, amount_in_wei
            counter = 0
            result = False
            while True:
                module_func = random.choice(func)
                try:
                    result = await module_func(self.client.account_name, self.client.private_key,
                                               self.client.network, self.client.proxy_init, swapdata=data)

                except:
                    pass
                if result or counter == 3:
                    break

        else:
            self.logger_msg(*self.client.acc_info, msg=f"{from_token_name} balance is too low (lower 1$)")

        return True

    async def smart_swap_stargate(self):
        from functions import swap_stargate

        chain1, chain2 = STARGATE_CHAINS
        token1, token2 = STARGATE_TOKENS
        rpc_by_id = LAYERZERO_WRAPED_NETWORKS

        client_chain1 = await self.client.new_client(rpc_by_id[chain1])
        client_chain2 = await self.client.new_client(rpc_by_id[chain2])

        balance_chain1, _, _ = await client_chain1.get_token_balance(omnicheck=True, token_name=token1,
                                                                     check_symbol=False)
        balance_chain2, _, _ = await client_chain2.get_token_balance(omnicheck=True, token_name=token2,
                                                                     check_symbol=False)

        if balance_chain2 == 0 and balance_chain1 == 0:
            raise RuntimeError('Insufficient balances on both networks!')
        elif balance_chain2 > balance_chain1:
            current_client = client_chain2
            from_token_name, to_token_name = token2, token1
            amount_in_wei = balance_chain2 if from_token_name != 'ETH' else await client_chain2.client.get_smart_amount()
            src_chain_name, dst_chain_name = client_chain2.network.name, client_chain1.network.name
            dst_chain_id = LAYERZERO_NETWORKS_DATA[chain1][1]
            contract = client_chain2.get_contract(TOKENS_PER_CHAIN2[client_chain2.network.name][from_token_name])
            decimals = await contract.functions.decimals().call()
        else:
            current_client = client_chain1
            from_token_name, to_token_name = token1, token2
            amount_in_wei = balance_chain1 if from_token_name != 'ETH' else await client_chain1.client.get_smart_amount()
            src_chain_name, dst_chain_name = client_chain1.network.name, client_chain2.network.name
            dst_chain_id = LAYERZERO_NETWORKS_DATA[chain2][1]
            contract = client_chain1.get_contract(TOKENS_PER_CHAIN2[client_chain1.network.name][from_token_name])
            decimals = await contract.functions.decimals().call()

        amount = f"{amount_in_wei / 10 ** decimals:.3f}"

        swapdata = dst_chain_id, dst_chain_name, src_chain_name, from_token_name, to_token_name, amount, amount_in_wei

        return await swap_stargate(current_client, swapdata=swapdata)

    @helper
    async def mint_token_avnu(self):
        from functions import swap_avnu

        amount, amount_in_wei = MEMCOIN_AMOUNT, int(MEMCOIN_AMOUNT * 10 ** 18)
        data = 'ETH', 'MEMCOIN', amount, amount_in_wei

        return await swap_avnu(self.client.account_name, self.client.private_key,
                               self.client.network, self.client.proxy_init, swapdata=data)

    @helper
    async def mint_token_jediswap(self):
        from functions import swap_jediswap

        amount, amount_in_wei = MEMCOIN_AMOUNT, int(MEMCOIN_AMOUNT * 10 ** 18)
        data = 'ETH', 'MEMCOIN', amount, amount_in_wei

        return await swap_jediswap(self.client.account_name, self.client.private_key,
                                   self.client.network, self.client.proxy_init, swapdata=data)

    @helper
    async def swap_bridged_usdc(self):
        from functions import swap_woofi

        amount_in_wei, amount, _ = await self.client.get_token_balance('USDC')
        data = 'USDC', 'USDC.e', amount, amount_in_wei

        if amount_in_wei == 0:
            raise RuntimeError("Insufficient USDC balances")

        return await swap_woofi(self.client.account_name, self.client.private_key,
                                self.client.network, self.client.proxy_init, swapdata=data)

    @helper
    async def merkly_attack(self):
        from functions import merkly_for_refuel_attack

        if SHUFFLE_ATTACK:
            random.shuffle(MERKLY_ATTACK_REFUEL)

        for chain_id_from, chain_id_to, amount in MERKLY_ATTACK_REFUEL:
            refuel_data = {
                chain_id_to: (amount, round(amount * 1.1, 7))
            }

            chain_id_from = LAYERZERO_WRAPED_NETWORKS[chain_id_from]

            await merkly_for_refuel_attack(self.client.account_name, self.client.private_key,
                                           self.client.network, self.client.proxy_init, chain_id_from,
                                           attack_mode=True, attack_data=refuel_data)

            await sleep(self)

        return True

    @helper
    async def l2pass_attack(self):
        from functions import l2pass_for_refuel_attack

        if SHUFFLE_ATTACK:
            random.shuffle(L2PASS_ATTACK_REFUEL)

        for chain_id_from, chain_id_to, amount in L2PASS_ATTACK_REFUEL:
            refuel_data = {
                chain_id_to: (amount, round(amount * 1.1, 7))
            }

            chain_id_from = LAYERZERO_WRAPED_NETWORKS[chain_id_from]

            await l2pass_for_refuel_attack(self.client.account_name, self.client.private_key,
                                           self.client.network, self.client.proxy_init, chain_id_from,
                                           attack_mode=True, attack_data=refuel_data)

            await sleep(self)

        return True

    @helper
    async def l2pass_nft_attack(self):
        from functions import l2pass_for_nft_attack

        if SHUFFLE_ATTACK:
            random.shuffle(L2PASS_ATTACK_NFT)

        for chain_id_from, chain_id_to in L2PASS_ATTACK_NFT:

            chain_id_from = LAYERZERO_WRAPED_NETWORKS[chain_id_from]

            await l2pass_for_nft_attack(self.client.account_name, self.client.private_key,
                                        self.client.network, self.client.proxy_init, chain_id_from,
                                        attack_mode=True, attack_data=chain_id_to)

            await sleep(self)

        return True

    @helper
    async def zerius_attack(self):
        from functions import zerius_for_refuel_attack

        if SHUFFLE_ATTACK:
            random.shuffle(ZERIUS_ATTACK_REFUEL)

        for chain_id_from, chain_id_to, amount in ZERIUS_ATTACK_REFUEL:
            refuel_data = {
                chain_id_to: (amount, round(amount * 1.1, 7))
            }

            chain_id_from = LAYERZERO_WRAPED_NETWORKS[chain_id_from]

            await zerius_for_refuel_attack(self.client.account_name, self.client.private_key,
                                           self.client.network, self.client.proxy_init, chain_id_from,
                                           attack_mode=True, attack_data=refuel_data)

            await sleep(self)

        return True

    @helper
    async def zerius_nft_attack(self):
        from functions import zerius_for_nft_attack

        if SHUFFLE_ATTACK:
            random.shuffle(ZERIUS_ATTACK_NFT)

        for chain_id_from, chain_id_to in ZERIUS_ATTACK_NFT:
            chain_id_from = LAYERZERO_WRAPED_NETWORKS[chain_id_from]

            await zerius_for_nft_attack(self.client.account_name, self.client.private_key,
                                        self.client.network, self.client.proxy_init, chain_id_from,
                                        attack_mode=True, attack_data=chain_id_to)

            await sleep(self)

        return True
