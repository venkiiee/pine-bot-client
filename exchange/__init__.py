# coding=utf-8

from logging import getLogger
log = getLogger(__name__)

from copy import deepcopy

import ccxt
from ccxt.base.errors import ExchangeError
from ccxt.base.errors import NotSupported

import exchange.cryptowatch as cryptowatch

from util.dict_merge import dict_merge
from util.parameters import sanitize_parameters

class Exchange (object):

    def __init__ (self, name, ccxt_obj, options):
        self.name = name
        self.ccxt = ccxt_obj
        self.options = options
        # test net
        if options.get('test', False):
            self._swith_to_testnet()
        # market info
        self._initialize_markets()

    def _swith_to_testnet (self):
        if 'test' not in self.ccxt.urls:
            raise NotSupported('testnet is not supported')
        self.ccxt.urls['api'] = self.ccxt.urls['test']

    def _initialize_markets (self):
        self.markets = {}
        self.market_alias = {}
        for name, m in self.ccxt.load_markets().items():
            alias = self.market_alias.setdefault(m['id'], [])
            for n in (name, m['id'], m['symbol']):
                self.markets[n] = m
                self.markets[n.upper()] = m
                self.markets[n.lower()] = m
                alias += (n, n.upper(), n.lower())


class CCXTOHLCVProvider (object):

    def __init__ (self, ccxt_obj, symbol):
        self.ccxt_obj = ccxt_obj
        self.symbol = symbol

    def resolutions (self):
        return [self._to_min(t) for t in self.ccxt_obj.timeframes.keys()]

    def _to_min (self, tf_str):
        num = int(tf_str[:-1])
        sfx = tf_str[-1]
        if sfx == 'm':
            pass
        elif sfx == 'h':
            num *= 60
        elif sfx == 'd':
            num *= 60 * 24
        elif sfx == 'w':
            num *= 60 * 24 * 7
        else:
            raise NotSupported(f'unknown timeframe string: {tf_str}')
        return num


class Market (object):

    def __init__ (self, exchange, symbol, options):
        self.exchange = exchange
        self.symbol_ = symbol
        self.market = exchange.markets[symbol.lower()]
        self.symbol = self.market['symbol']
        self.options = options
        # ohlcv provider
        self._initialize_ohlcv_provider()

    def _initialize_ohlcv_provider (self):
        provider = None
        # cryptowatch?
        for a in self.exchange.market_alias[self.market['id']]:
            xchg_name = self.exchange.name.lower()
            if cryptowatch.supports(xchg_name, a):
                provider = cryptowatch.OHLCVProvider(xchg_name, a)
                break

        # ccxt
        if provider is None:
            support = self.exchange.ccxt.has['fetchOHLCV']
            if support and support != 'emulated':
                provider = CCXTOHLCVProvider(self.exchange.ccxt, self.symbol)

        if provider is None:
            name = self.exchange.name
            symbol = self.symbol_
            raise NotSupported(f'market does not support OHLCV API: {name}:{symbol}')
                
        self.ohlcv_provider = provider

## Factory
def get_exchange (name, params):
    name_ = name.lower()
    if name_ not in ccxt.exchanges:
        raise ExchangeError(f'Unsupported exchange: {name}')

    options = deepcopy(params.get('ccxt', {}))
    dict_merge(options, params.get(name, {}))
    dict_merge(options, params.get(name_, {}))
    # Tweak options
    if 'enableRateLimit' not in options:
        options['enableRateLimit'] = True

    ccxt_cls = getattr(ccxt, name_)
    ccxt_obj = ccxt_cls(options)
    
    options_ = sanitize_parameters(deepcopy(options))
    log.info(f'Initialize exchange: {name}: {options_}')
    
    return Exchange(name, ccxt_obj, options_)

def get_market (exchange, symbol, params):
    exchange = get_exchange(exchange, params)
    if symbol not in exchange.markets:
        raise ExchangeError(f'market not found: {symbol}')
    return Market(exchange, symbol, params)


if __name__ == '__main__':
    import sys
    import logging
    logging.basicConfig(level=logging.INFO)
    cryptowatch.initialize()
    market = get_market(sys.argv[1], sys.argv[2], {})
    print(market)
    print(market.ohlcv_provider)
    print(market.ohlcv_provider.resolutions())