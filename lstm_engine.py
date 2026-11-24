import time
import numpy as np
import torch
import torch.nn as nn
from sklearn.preprocessing import MinMaxScaler

torch.set_num_threads(1)


class SalesLSTMModel(nn.Module):
    def __init__(self, input_size: int = 1, hidden_size: int = 16, num_layers: int = 1):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
        )
        self.fc = nn.Linear(hidden_size, 1)

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])


class FastLSTMForecaster:
    def __init__(self, lookback: int = 7):
        self.lookback = lookback
        self._cache = {}

    def _create_sequences(self, scaled_data: np.ndarray):
        X, y = [], []
        for i in range(self.lookback, len(scaled_data)):
            X.append(scaled_data[i - self.lookback : i, 0])
            y.append(scaled_data[i, 0])
        X = np.array(X, dtype=np.float32).reshape(-1, self.lookback, 1)
        y = np.array(y, dtype=np.float32).reshape(-1, 1)
        return torch.from_numpy(X), torch.from_numpy(y)

    def forecast(self, product_id: int, sales_history: list[float], current_stock: int) -> dict:
        start_time = time.perf_counter()
        history_key = (product_id, tuple(sales_history))

        if len(sales_history) <= self.lookback:
            next_day = float(np.mean(sales_history)) if sales_history else 5.0
            week_curve = [round(next_day, 1)] * 7
            engine_status = "Moving Average Warmup (<8 days data)"
        else:
            if history_key in self._cache:
                model, scaler, scaled_data = self._cache[history_key]
                engine_status = "PyTorch LSTM (Cached Weights)"
            else:
                scaler = MinMaxScaler(feature_range=(0, 1))
                raw = np.array(sales_history, dtype=np.float32).reshape(-1, 1)
                scaled_data = scaler.fit_transform(raw)

                X_train, y_train = self._create_sequences(scaled_data)
                model = SalesLSTMModel(hidden_size=16, num_layers=1)
                criterion = nn.MSELoss()
                optimizer = torch.optim.Adam(model.parameters(), lr=0.03)

                model.train()
                for _ in range(15):
                    optimizer.zero_grad()
                    loss = criterion(model(X_train), y_train)
                    loss.backward()
                    optimizer.step()

                model.eval()
                self._cache[history_key] = (model, scaler, scaled_data)
                engine_status = "PyTorch LSTM (Trained)"

            window = scaled_data[-self.lookback :].copy()
            week_curve = []
            with torch.no_grad():
                for _ in range(7):
                    inp = torch.from_numpy(window.reshape(1, self.lookback, 1)).float()
                    pred_scaled = model(inp).numpy()
                    pred_actual = float(scaler.inverse_transform(pred_scaled)[0][0])
                    week_curve.append(max(0.0, round(pred_actual, 1)))
                    window = np.roll(window, -1)
                    window[-1] = pred_scaled[0][0]

            next_day = week_curve[0]

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        days_left = round(current_stock / max(next_day, 0.1), 1)
        three_day_buffer = round(sum(week_curve[:3]))
        suggested_restock = max(0, three_day_buffer - current_stock)

        return {
            "predicted_tomorrow_units": next_day,
            "next_7_days_forecast": week_curve,
            "current_stock": current_stock,
            "estimated_days_until_stockout": days_left,
            "low_stock_alert": current_stock <= three_day_buffer * 0.6,
            "suggested_restock_units": suggested_restock,
            "inference_time_ms": latency_ms,
            "engine": engine_status,
        }
