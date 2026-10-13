"""
Bot de Trading Algorítmico Multiactivo basado en el patrón Banderín (Pennant).
Utiliza MetaTrader5 para la ejecución de órdenes.
"""

import sys
import time

import MetaTrader5 as mt5
import pandas as pd
import numpy as np


class MultiSymbolPennantBot:
    """Clase principal del bot de trading que opera sobre MT5."""

    # pylint: disable=too-many-instance-attributes
    def __init__(self, symbols, timeframe, lot_size=0.1, magic_number=999111):
        self.symbols = symbols
        self.tf = timeframe
        self.lot_size = lot_size
        self.magic = magic_number

        # --- Hard Rules de Gestión ---
        self.max_sl_pips = 5.0
        self.rr_ratio = 2.0
        self.body_solidity_threshold = 0.6
        self.swing_window = 3

        # Conexión al Broker
        if not mt5.initialize():
            print("❌ Fallo al inicializar MT5. "
                  "Asegúrate de tener la plataforma abierta.")
            sys.exit(1)

        print("✅ Conectado a MetaTrader 5.")

        # Validación de Símbolos en el Market Watch
        self.active_symbols = []
        for sym in self.symbols:
            if mt5.symbol_select(sym, True):
                self.active_symbols.append(sym)
            else:
                print(f"⚠️ El símbolo {sym} no existe en tu broker. "
                      "Omitiendo...")

        if not self.active_symbols:
            print("❌ Ningún símbolo válido encontrado. Deteniendo bot.")
            mt5.shutdown()
            sys.exit(1)

        print(f"🚀 Escáner iniciado para: {', '.join(self.active_symbols)}")

    # pylint: disable=too-many-return-statements
    def get_pip_value(self, symbol):
        """Calcula el valor de 1 Pip dependiendo del activo."""
        info = mt5.symbol_info(symbol)
        if info is None:
            return 0.0001

        sym_upper = symbol.upper()
        if 'JPY' in sym_upper:
            return 0.01
        if 'XAU' in sym_upper or 'GOLD' in sym_upper:
            return 0.1
        if 'BTC' in sym_upper or 'BITCOIN' in sym_upper:
            return 1.0
        if info.digits in (5, 4):
            return 0.0001
        if info.digits in (3, 2):
            return 0.01

        return info.point

    def get_data(self, symbol, num_bars=150):
        """Descarga las últimas velas y calcula los Swing Highs/Lows."""
        rates = mt5.copy_rates_from_pos(symbol, self.tf, 0, num_bars)
        if rates is None or len(rates) == 0:
            return None

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')

        # Ventana deslizante para Swings (sin errores ni repintado)
        window = self.swing_window
        rolling_window = 2 * window + 1

        df['local_max'] = df['high'].rolling(
            window=rolling_window,
            center=True,
            min_periods=rolling_window).max()
        df['local_min'] = df['low'].rolling(
            window=rolling_window,
            center=True,
            min_periods=rolling_window).min()

        df['SwingHigh'] = np.where(
            df['high'] == df['local_max'], df['high'], np.nan)
        df['SwingLow'] = np.where(
            df['low'] == df['local_min'], df['low'], np.nan)

        return df

    def check_setup(self, df):
        """Evalúa Secuencia 3D: Base -> Mástil -> Banderín (Contracción)."""
        if df is None or df.empty:
            return 0

        highs = df['SwingHigh'].dropna().values
        lows = df['SwingLow'].dropna().values

        if len(highs) < 3 or len(lows) < 3:
            return 0

        # h1 = H1, h2 = H2, h3 = H3
        # l1 = L1, l2 = L2, l3 = L3
        h1, h2, h3 = highs[-3], highs[-2], highs[-1]
        l1, l2, l3 = lows[-3], lows[-2], lows[-1]

        # Bullish Pennant
        if h1 < h2 and h3 < h2 and l1 < l2 < l3:
            return 1
        # Bearish Pennant
        if h2 < h1 and h2 < h3 and l3 < l2 < l1:
            return -1

        return 0

    # pylint: disable=too-many-return-statements
    def check_breakout(self, df, direction):
        """Verifica quiebre con vela sólida a favor de la tendencia."""
        if df is None or len(df) < 2:
            return False

        last_candle = df.iloc[-2]
        candle_size = last_candle['high'] - last_candle['low']
        if candle_size == 0:
            return False

        body_size = abs(last_candle['close'] - last_candle['open'])
        solidity = body_size / candle_size

        if solidity < self.body_solidity_threshold:
            return False

        highs = df['SwingHigh'].dropna().values
        lows = df['SwingLow'].dropna().values

        if len(highs) == 0 or len(lows) == 0:
            return False

        h3 = highs[-1]
        l3 = lows[-1]

        if direction == 1:
            if last_candle['open'] <= h3 < last_candle['close']:
                return True
            return False

        if direction == -1:
            if last_candle['close'] < l3 <= last_candle['open']:
                return True
            return False

        return False

    def get_open_positions(self, symbol):
        """Devuelve las posiciones abiertas por este bot en este símbolo."""
        positions = mt5.positions_get(symbol=symbol)
        if positions is None:
            return []
        return [p for p in positions if p.magic == self.magic]

    def _get_filling_mode(self, info):
        """Obtiene el modo de llenado soportado por el broker dinámicamente."""
        filling_modes = info.filling_mode
        if filling_modes & mt5.SYMBOL_FILLING_IOC:
            return mt5.ORDER_FILLING_IOC
        if filling_modes & mt5.SYMBOL_FILLING_FOK:
            return mt5.ORDER_FILLING_FOK

        return mt5.ORDER_FILLING_RETURN

    # pylint: disable=too-many-locals
    def execute_trade(self, symbol, direction, df):
        """Calcula el riesgo y envía la orden a MT5 si cumple las reglas."""
        info = mt5.symbol_info(symbol)
        if info is None:
            return

        digits = info.digits
        pip_val = self.get_pip_value(symbol)
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return

        spread = tick.ask - tick.bid

        lows = df['SwingLow'].dropna().values
        highs = df['SwingHigh'].dropna().values

        if len(lows) == 0 or len(highs) == 0:
            return

        last_swing_low = lows[-1]
        last_swing_high = highs[-1]

        if direction == 1:
            entry_price = tick.ask
            sl_price = last_swing_low - spread
            order_type = mt5.ORDER_TYPE_BUY
        else:
            entry_price = tick.bid
            sl_price = last_swing_high + spread
            order_type = mt5.ORDER_TYPE_SELL

        sl_distance = abs(entry_price - sl_price)
        if sl_distance <= 0:
            return

        sl_pips = sl_distance / pip_val

        # Filtro de Riesgo Máximo
        if sl_pips > self.max_sl_pips:
            print(f"[{symbol}] ⚠️ Rechazado: El Riesgo de SL "
                  f"({sl_pips:.1f} pips) > límite de {self.max_sl_pips} pips.")
            return

        tp_distance = sl_distance * self.rr_ratio
        if direction == 1:
            tp_price = entry_price + tp_distance
        else:
            tp_price = entry_price - tp_distance

        # Normalización matemática obligatoria para MT5
        entry_price = round(entry_price, digits)
        sl_price = round(sl_price, digits)
        tp_price = round(tp_price, digits)

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(self.lot_size),
            "type": order_type,
            "price": entry_price,
            "sl": sl_price,
            "tp": tp_price,
            "deviation": 5,
            "magic": self.magic,
            "comment": f"Pennant {sl_pips:.1f}p",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": self._get_filling_mode(info),
        }

        result = mt5.order_send(request)
        if result is None:
            print(f"[{symbol}] ❌ Error crítico de MT5. "
                  f"Código: {mt5.last_error()}")
            return

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"[{symbol}] ❌ Orden Rechazada: {result.comment}")
        else:
            print(f"[{symbol}] 🔥 ORDEN EJECUTADA! "
                  f"{'COMPRA' if direction == 1 else 'VENTA'} | "
                  f"SL: {sl_price} | TP: {tp_price}")

    def manage_positions(self, symbol):
        """Trailing Step: Mueve a Break Even cuando alcanza 1:1 a favor."""
        positions = self.get_open_positions(symbol)
        if not positions:
            return

        pip_val = self.get_pip_value(symbol)
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return

        for pos in positions:
            entry = pos.price_open
            sl_actual = pos.sl

            if pos.type == mt5.POSITION_TYPE_BUY:
                if sl_actual >= entry:
                    continue

                current_profit_pips = (tick.bid - entry) / pip_val
                riesgo_inicial_pips = (entry - sl_actual) / pip_val

                if 0 < riesgo_inicial_pips <= current_profit_pips:
                    self.modify_sl(pos, entry, "Move BE")

            elif pos.type == mt5.POSITION_TYPE_SELL:
                if sl_actual <= entry and sl_actual != 0:
                    continue

                current_profit_pips = (entry - tick.ask) / pip_val
                riesgo_inicial_pips = (sl_actual - entry) / pip_val

                if 0 < riesgo_inicial_pips <= current_profit_pips:
                    self.modify_sl(pos, entry, "Move BE")

    def modify_sl(self, pos, new_sl, comment=""):
        """Envía la solicitud de modificación de Stop Loss a MT5."""
        info = mt5.symbol_info(pos.symbol)
        digits = info.digits if info else 5

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": pos.symbol,
            "position": pos.ticket,
            "sl": round(float(new_sl), digits),
            "tp": round(float(pos.tp), digits),
            "magic": self.magic,
            "comment": comment
        }

        result = mt5.order_send(request)
        if result is not None and result.retcode == mt5.TRADE_RETCODE_DONE:
            print(
                f"[{pos.symbol}] 🛡️ Trailing Step a Break Even Activado "
                "(Riesgo Cero).")

    def run_iteration(self):
        """Ejecuta una iteración del bucle principal del bot."""
        for symbol in self.active_symbols:
            # 1. Vigila el Break Even de cualquier orden abierta
            self.manage_positions(symbol)

            # 2. Solo busca entradas si no hay órdenes en curso para ese
            # símbolo
            if len(self.get_open_positions(symbol)) == 0:
                df = self.get_data(symbol, num_bars=150)

                if df is not None and not df.empty:
                    direction = self.check_setup(df)

                    if direction != 0:
                        if self.check_breakout(df, direction):
                            self.execute_trade(symbol, direction, df)

    def run(self):
        """Bucle principal de ejecución del bot."""
        print("⏳ Monitoreando el mercado en tiempo real... "
              "(Presiona Ctrl+C para detener)")
        try:
            while True:
                self.run_iteration()
                # Pausa para no abrumar la conexión al broker
                time.sleep(1)

        except KeyboardInterrupt:
            print("\n🛑 Apagando el Bot. Desconectando de MT5...")
            mt5.shutdown()
        # pylint: disable=broad-except
        except Exception as e:
            print(f"\n❌ Error General (Protegido): {e}")
            mt5.shutdown()


if __name__ == "__main__":
    # --- CONFIGURACIÓN DE PORTAFOLIO ---
    # Nota: Si tu broker tiene sufijos (ej. EURUSD.r), colócalo tal cual.
    SYMBOLS_TO_TRADE = ["EURUSD", "XAUUSD", "BTCUSD"]

    # Temporalidad (M1) necesaria matemáticamente para lograr el límite de
    # riesgo de 5 pips
    TIMEFRAME = mt5.TIMEFRAME_M1

    bot = MultiSymbolPennantBot(
        symbols=SYMBOLS_TO_TRADE,
        timeframe=TIMEFRAME,
        lot_size=0.1)
    bot.run()
