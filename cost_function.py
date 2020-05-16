import pandas as pd
import numpy as np


def calculate_moving_average(length, records):
    moving_average = pd.Series(records).rolling(window=length).mean().iloc[length - 1:].values
    moving_average = np.insert(moving_average, 0, [0] * (length - 1))
    return moving_average


def cost_function(length_short, length_long, records):
    mean_short = calculate_moving_average(length_short, records)  # policzenie krótkiej średniej
    mean_long = calculate_moving_average(length_long, records)  # policzenie długiej średniej
    sign = np.sign(
        mean_short - mean_long)  # wyznaczenie gdzie krótka jest wyżej od długiej (1 dla krótkiej większej od długiej, -1 dla długiej większej od krótkiej)
    signals = np.sign(sign[:-1] - sign[1:])  # wyznaczenie punktów przecięcia
    signals = np.insert(signals, 0, 0)
    buy_signals = np.where(signals == -1, -signals, 0)  # rozdzielenie sygnałów kupna
    sell_signals = np.where(signals == 1, signals, 0)  # rozdzielenie sygnałów sprzedaży
    buy_prices = buy_signals * records
    sell_prices = sell_signals * records
    buy_prices = buy_prices[buy_prices != 0]
    sell_prices = sell_prices[sell_prices != 0]
    total = 0
    pairs = list(zip(buy_prices, sell_prices))
    for (buy, sell) in pairs[1:]:
        total += sell - buy

    return total

    # fig = plt.figure()
    # ax = fig.add_subplot(111)
    # ax.scatter(range(0, len(buy_signals)), np.abs(buy_signals) * mean_short, marker="+", color="red")
    # ax.scatter(range(0, len(buy_signals)), sell_signals * mean_long, marker="*", color="yellow")
    # ax.plot(records)
    # ax.plot(mean_short)
    # ax.plot(mean_long)
    # plt.show()
