//+------------------------------------------------------------------+
//|                                     PennantAlgoTrader_Native.mq5 |
//|                                           Desarrollador Quant    |
//+------------------------------------------------------------------+
#property copyright "Desarrollador Quant"
#property link      ""
#property version   "1.00"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\SymbolInfo.mqh>

input double   InpLotSize              = 0.1;      // Tamaño del Lote
input double   InpMaxSLPips            = 5.0;      // SL Máximo (Pips)
input double   InpRRRatio              = 2.0;      // Ratio Riesgo/Beneficio (1:X)
input double   InpBodySolidityThreshold= 0.6;      // Solidez de Vela (0.6 = 60%)
input int      InpSwingWindow          = 3;        // Velas para formar un Swing
input ulong    InpMagicNumber          = 999111;   // Magic Number

CTrade         trade;
CPositionInfo  m_position;
CSymbolInfo    m_symbol;

double         m_pip_value;
double         m_pip_multiplier; // Factor para convertir Pips a Puntos (Points)

// Estructuras para almacenar Swings
struct SwingPoint
{
   double price;
   int    index; // Índice de la vela (0 es la actual)
};

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
  {
   if(!m_symbol.Name(Symbol()))
      return(INIT_FAILED);

   trade.SetExpertMagicNumber(InpMagicNumber);

   // Determinar multiplicador de Pip basado en el activo
   DeterminePipMultiplier();

   Print("✅ Bot inicializado en ", Symbol(), " - Multiplicador de Pips: ", m_pip_multiplier);

   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   Print("🛑 Bot detenido.");
  }

//+------------------------------------------------------------------+
//| Determina el tamaño de 1 pip para el símbolo actual              |
//+------------------------------------------------------------------+
void DeterminePipMultiplier()
{
    string sym = Symbol();
    StringToUpper(sym);

    int digits = (int)SymbolInfoInteger(Symbol(), SYMBOL_DIGITS);
    double point = SymbolInfoDouble(Symbol(), SYMBOL_POINT);

    // Configuración para Forex JPY
    if(StringFind(sym, "JPY") >= 0)
    {
        m_pip_multiplier = 0.01;
    }
    // Configuración para ORO (XAUUSD)
    else if(StringFind(sym, "XAU") >= 0 || StringFind(sym, "GOLD") >= 0)
    {
        m_pip_multiplier = 0.1; // 1 pip = 0.1 en oro típicamente, o 1.0 dependiendo del broker
        // Ajuste fino para oro
        if(digits == 2) m_pip_multiplier = 0.1;
        if(digits == 3) m_pip_multiplier = 0.1;
    }
    // Configuración para Cripto (BTCUSD)
    else if(StringFind(sym, "BTC") >= 0 || StringFind(sym, "BITCOIN") >= 0)
    {
        m_pip_multiplier = 1.0;
    }
    // Forex Estandar
    else if(digits == 5 || digits == 4)
    {
        m_pip_multiplier = 0.0001;
    }
    else
    {
        m_pip_multiplier = point * 10.0; // Fallback
    }
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
  {
   if(!m_symbol.RefreshRates())
      return;

   // 1. Gestionar posiciones abiertas (Trailing Step a BE)
   ManagePositions();

   // 2. Ejecutar lógica de entrada SOLO en la apertura de una nueva vela (para no re-calcular en cada tick)
   // En MQL5, típicamente evaluamos al cerrar la vela [1]
   static datetime last_time = 0;
   datetime current_time = iTime(Symbol(), PERIOD_CURRENT, 0);

   if(current_time != last_time)
     {
      last_time = current_time;

      // Si no tenemos posiciones abiertas de este bot
      if(PositionsTotalByMagic() == 0)
        {
         // Evaluar mercado
         AnalyzeMarket();
        }
     }
  }

//+------------------------------------------------------------------+
//| Cuenta las posiciones abiertas por el EA                         |
//+------------------------------------------------------------------+
int PositionsTotalByMagic()
{
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(m_position.SelectByIndex(i))
         if(m_position.Symbol() == Symbol() && m_position.Magic() == InpMagicNumber)
            count++;
     }
   return count;
}

//+------------------------------------------------------------------+
//| Gestiona el Trailing Stop a Break Even                           |
//+------------------------------------------------------------------+
void ManagePositions()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(m_position.SelectByIndex(i))
        {
         if(m_position.Symbol() == Symbol() && m_position.Magic() == InpMagicNumber)
           {
            double entry_price = m_position.PriceOpen();
            double current_sl = m_position.StopLoss();
            double current_tp = m_position.TakeProfit();
            long pos_type = m_position.PositionType();

            double current_profit_pips = 0;
            double risk_initial_pips = 0;

            if(pos_type == POSITION_TYPE_BUY)
              {
               if(current_sl >= entry_price) continue; // Ya está en BE

               current_profit_pips = (m_symbol.Bid() - entry_price) / m_pip_multiplier;
               risk_initial_pips = (entry_price - current_sl) / m_pip_multiplier;

               // Si ganamos lo mismo que arriesgamos (1:1), movemos a BE
               if(risk_initial_pips > 0 && current_profit_pips >= risk_initial_pips)
                 {
                  trade.PositionModify(m_position.Ticket(), entry_price, current_tp);
                  Print("🛡️ [COMPRA] Trailing Step a Break Even Activado.");
                 }
              }
            else if(pos_type == POSITION_TYPE_SELL)
              {
               if(current_sl <= entry_price && current_sl != 0.0) continue; // Ya está en BE

               current_profit_pips = (entry_price - m_symbol.Ask()) / m_pip_multiplier;
               risk_initial_pips = (current_sl - entry_price) / m_pip_multiplier;

               if(risk_initial_pips > 0 && current_profit_pips >= risk_initial_pips)
                 {
                  trade.PositionModify(m_position.Ticket(), entry_price, current_tp);
                  Print("🛡️ [VENTA] Trailing Step a Break Even Activado.");
                 }
              }
           }
        }
     }
}

//+------------------------------------------------------------------+
//| Analiza el mercado en busca de Banderines                        |
//+------------------------------------------------------------------+
void AnalyzeMarket()
{
   int bars_to_check = 150;
   int window = InpSwingWindow;
   int rolling_window = 2 * window + 1;

   double high[], low[], close[], open[];
   ArraySetAsSeries(high, true);
   ArraySetAsSeries(low, true);
   ArraySetAsSeries(close, true);
   ArraySetAsSeries(open, true);

   if(CopyHigh(Symbol(), PERIOD_CURRENT, 0, bars_to_check, high) < bars_to_check) return;
   if(CopyLow(Symbol(), PERIOD_CURRENT, 0, bars_to_check, low) < bars_to_check) return;
   if(CopyClose(Symbol(), PERIOD_CURRENT, 0, bars_to_check, close) < bars_to_check) return;
   if(CopyOpen(Symbol(), PERIOD_CURRENT, 0, bars_to_check, open) < bars_to_check) return;

   SwingPoint swingHighs[];
   SwingPoint swingLows[];

   // Encontrar Swings (empezamos desde 1 para ignorar la vela formándose)
   for(int i = 1; i < bars_to_check - window; i++)
   {
      bool isHigh = true;
      bool isLow = true;

      for(int j = 1; j <= window; j++)
      {
         if(i-j >= 0 && high[i] <= high[i-j]) isHigh = false;
         if(i+j < bars_to_check && high[i] < high[i+j]) isHigh = false;

         if(i-j >= 0 && low[i] >= low[i-j]) isLow = false;
         if(i+j < bars_to_check && low[i] > low[i+j]) isLow = false;
      }

      if(isHigh)
      {
         int size = ArraySize(swingHighs);
         ArrayResize(swingHighs, size + 1);
         swingHighs[size].price = high[i];
         swingHighs[size].index = i;
      }
      if(isLow)
      {
         int size = ArraySize(swingLows);
         ArrayResize(swingLows, size + 1);
         swingLows[size].price = low[i];
         swingLows[size].index = i;
      }
   }

   // Necesitamos al menos 3 swings recientes
   int sh_count = ArraySize(swingHighs);
   int sl_count = ArraySize(swingLows);

   if(sh_count < 3 || sl_count < 3) return;

   // Los arrays se llenaron de vela [1] hacia atrás.
   // Así que [0] es el swing más reciente, [1] el anterior, [2] el previo a ese.
   // h3 = [0], h2 = [1], h1 = [2]
   double h1 = swingHighs[2].price;
   double h2 = swingHighs[1].price;
   double h3 = swingHighs[0].price;

   double l1 = swingLows[2].price;
   double l2 = swingLows[1].price;
   double l3 = swingLows[0].price;

   int direction = 0;

   // Bullish Pennant
   if(h1 < h2 && h3 < h2 && l1 < l2 && l2 < l3) direction = 1;
   // Bearish Pennant
   else if(h2 < h1 && h2 < h3 && l3 < l2 && l2 < l1) direction = -1;

   if(direction != 0)
   {
      // Validar Breakout en la vela anterior (la que acaba de cerrar, index 1)
      double candle_size = high[1] - low[1];
      if(candle_size == 0) return;

      double body_size = MathAbs(close[1] - open[1]);
      double solidity = body_size / candle_size;

      if(solidity < InpBodySolidityThreshold) return;

      bool breakout = false;

      if(direction == 1)
      {
         if(open[1] <= h3 && close[1] > h3) breakout = true;
      }
      else if(direction == -1)
      {
         if(close[1] < l3 && open[1] >= l3) breakout = true;
      }

      if(breakout)
      {
         ExecuteTrade(direction, swingHighs[0].price, swingLows[0].price);
      }
   }
}

//+------------------------------------------------------------------+
//| Ejecuta la orden tras validar el riesgo                          |
//+------------------------------------------------------------------+
void ExecuteTrade(int direction, double last_swing_high, double last_swing_low)
{
   double spread = m_symbol.Ask() - m_symbol.Bid();
   double entry_price = 0.0;
   double sl_price = 0.0;

   if(direction == 1)
   {
      entry_price = m_symbol.Ask();
      sl_price = last_swing_low - spread;
   }
   else
   {
      entry_price = m_symbol.Bid();
      sl_price = last_swing_high + spread;
   }

   double sl_distance = MathAbs(entry_price - sl_price);
   if(sl_distance <= 0) return;

   double sl_pips = sl_distance / m_pip_multiplier;

   // HARD RULE: Máximo SL
   if(sl_pips > InpMaxSLPips)
   {
      PrintFormat("⚠️ Rechazado: Riesgo de SL (%.1f pips) supera el límite de %.1f pips.", sl_pips, InpMaxSLPips);
      return;
   }

   double tp_distance = sl_distance * InpRRRatio;
   double tp_price = 0.0;

   if(direction == 1) tp_price = entry_price + tp_distance;
   else               tp_price = entry_price - tp_distance;

   // Normalizar precios a los dígitos del broker
   int digits = m_symbol.Digits();
   entry_price = NormalizeDouble(entry_price, digits);
   sl_price = NormalizeDouble(sl_price, digits);
   tp_price = NormalizeDouble(tp_price, digits);

   if(direction == 1)
   {
      if(trade.Buy(InpLotSize, Symbol(), entry_price, sl_price, tp_price, "Pennant Buy"))
      {
         Print("🔥 COMPRA EJECUTADA! SL: ", sl_price, " TP: ", tp_price);
      }
      else
      {
         Print("❌ Error ejecutando COMPRA: ", trade.ResultRetcodeDescription());
      }
   }
   else
   {
      if(trade.Sell(InpLotSize, Symbol(), entry_price, sl_price, tp_price, "Pennant Sell"))
      {
         Print("🔥 VENTA EJECUTADA! SL: ", sl_price, " TP: ", tp_price);
      }
      else
      {
         Print("❌ Error ejecutando VENTA: ", trade.ResultRetcodeDescription());
      }
   }
}
//+------------------------------------------------------------------+
