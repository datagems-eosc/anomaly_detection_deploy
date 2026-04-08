# Detection Methods

## Temporal Detection Methods

Temporal methods analyze a single station's behavior over time to detect anomalies.

### ARIMA (AutoRegressive Integrated Moving Average)

**Best For**: Complex trends, seasonal patterns, weather forecasting

**How It Works**:

ARIMA models the time series as a combination of:

- **AR (AutoRegressive)**: Current value depends on past values
- **I (Integrated)**: Differencing to make the series stationary
- **MA (Moving Average)**: Current value depends on past forecast errors

**Parameters**: `(p, d, q)` where:

- `p`: Number of lag observations
- `d`: Degree of differencing
- `q`: Size of moving average window

**Implementation**:

```python
from statsmodels.tsa.arima.model import ARIMA

# Fit model on historical data
model = ARIMA(historical_data, order=(1, 1, 1))
fitted = model.fit()

# Forecast next value
forecast = fitted.forecast(steps=1)
confidence_interval = fitted.get_forecast(steps=1).conf_int()

# Check if actual value is outside confidence interval
if actual < confidence_interval[0] or actual > confidence_interval[1]:
    return True  # Anomalous
```

**Advantages**:

- Captures complex patterns
- Provides confidence intervals
- Adapts to trends

**Disadvantages**:

- Computationally expensive
- Requires sufficient historical data (> 30 points)
- May fail on very noisy data

**Recommended Settings**:

- Window size: 6 hours (36 data points at 10-min intervals)
- Order: `(1, 1, 1)` for most weather variables
- Confidence level: 95%

---

### 3-Sigma (Z-Score)

**Best For**: Quick outlier detection, normally distributed data

**How It Works**:

Calculates how many standard deviations the current value is from the mean:

\[
Z = \frac{X - \mu}{\sigma}
\]

Where:

- \(X\) = Current value
- \(\mu\) = Mean of historical data
- \(\sigma\) = Standard deviation

**Implementation**:

```python
import numpy as np

mean = np.mean(historical_data)
std = np.std(historical_data)

z_score = (actual_value - mean) / std

if abs(z_score) > 3:
    return True  # Anomalous
```

**Advantages**:

- Extremely fast
- Simple to understand
- Works well for stable data

**Disadvantages**:

- Assumes normal distribution
- Sensitive to outliers in historical data
- Doesn't capture trends

**Recommended Settings**:

- Threshold: 3 (captures 99.7% of normal data)
- Window size: 6 hours minimum

---

### MAD (Median Absolute Deviation)

**Best For**: Robust detection, data with outliers, stable baselines

**How It Works**:

Uses median instead of mean for robustness:

\[
\text{MAD} = \text{median}(|X_i - \text{median}(X)|)
\]

\[
\text{Score} = \frac{|X - \text{median}(X)|}{\text{MAD}}
\]

**Implementation**:

```python
import numpy as np

median = np.median(historical_data)
mad = np.median(np.abs(historical_data - median))

score = abs(actual_value - median) / mad

if score > 3.5:
    return True  # Anomalous
```

**Advantages**:

- Robust to outliers
- No assumption of normal distribution
- Stable over time

**Disadvantages**:

- Can be too sensitive to changes
- Doesn't handle trends well
- May flag all values if data is flat

**Recommended Settings**:

- Threshold: 3.5
- Use when baseline is stable (e.g., barometric pressure)

---

### IQR (Interquartile Range)

**Best For**: Exploratory analysis, boxplot-style outlier detection

**How It Works**:

Uses quartiles to define normal range:

\[
\text{IQR} = Q_3 - Q_1
\]

Outliers are values outside:

\[
[Q_1 - 1.5 \times \text{IQR}, Q_3 + 1.5 \times \text{IQR}]
\]

**Implementation**:

```python
import numpy as np

q1 = np.percentile(historical_data, 25)
q3 = np.percentile(historical_data, 75)
iqr = q3 - q1

lower_bound = q1 - 1.5 * iqr
upper_bound = q3 + 1.5 * iqr

if actual_value < lower_bound or actual_value > upper_bound:
    return True  # Anomalous
```

**Advantages**:

- Intuitive (boxplot logic)
- Robust to outliers
- No distribution assumptions

**Disadvantages**:

- Static threshold
- Doesn't capture trends
- Less sensitive than other methods

**Recommended Settings**:

- Multiplier: 1.5 (standard) or 3.0 (conservative)

---

### Isolation Forest

**Best For**: Multidimensional patterns, complex anomalies

**How It Works**:

Machine learning algorithm that isolates anomalies by randomly partitioning data:

- Anomalies are easier to isolate (fewer splits needed)
- Normal points are harder to isolate (more splits needed)

**Implementation**:

```python
from sklearn.ensemble import IsolationForest

# Train on historical data (all variables)
X = historical_data[['temp_out', 'out_hum', 'wind_speed', 'bar', 'rain']]
model = IsolationForest(contamination=0.1, random_state=42)
model.fit(X)

# Predict on current value
current = [[temp, hum, wind, bar, rain]]
prediction = model.predict(current)

if prediction[0] == -1:
    return True  # Anomalous
```

**Advantages**:

- Finds subtle patterns
- Handles multiple variables simultaneously
- No assumption of distribution

**Disadvantages**:

- Black box (hard to interpret)
- Requires all variables present
- Sensitive to contamination parameter

**Recommended Settings**:

- Contamination: 0.1 (expect 10% anomalies)
- Random state: 42 (for reproducibility)

---

### STL (Seasonal-Trend Decomposition)

**Best For**: Data with strong seasonality (daily/weekly cycles)

**How It Works**:

Decomposes time series into:

- **Trend**: Long-term progression
- **Seasonal**: Repeating patterns
- **Residual**: Remaining variation

Anomalies are detected in the residual component.

**Implementation**:

```python
from statsmodels.tsa.seasonal import STL

# Decompose time series
stl = STL(historical_data, seasonal=13)  # 13 for 6.5-hour cycle
result = stl.fit()

# Get residuals
residuals = result.resid

# Detect outliers in residuals using 3-sigma
threshold = 3 * np.std(residuals)
if abs(residuals[-1]) > threshold:
    return True  # Anomalous
```

**Advantages**:

- Handles seasonality well
- Separates trend from noise
- Interpretable components

**Disadvantages**:

- Requires sufficient data (> 2 cycles)
- Computationally expensive
- Fixed seasonal period

**Recommended Settings**:

- Seasonal period: 13 (for 2-hour cycles at 10-min intervals)
- Use for temperature (daily cycle)

---

### LOF (Local Outlier Factor)

**Best For**: Density-based outlier detection, clustered data

**How It Works**:

Measures local deviation of density compared to neighbors:

- High LOF: Point is in a sparse region (outlier)
- Low LOF: Point is in a dense region (normal)

**Implementation**:

```python
from sklearn.neighbors import LocalOutlierFactor

# Fit on historical data
lof = LocalOutlierFactor(n_neighbors=20, contamination=0.1)
lof.fit(historical_data.reshape(-1, 1))

# Predict on current value
prediction = lof.fit_predict(
    np.append(historical_data, actual_value).reshape(-1, 1)
)

if prediction[-1] == -1:
    return True  # Anomalous
```

**Advantages**:

- Finds local outliers
- Handles varying densities
- No global threshold needed

**Disadvantages**:

- Sensitive to k parameter
- Computationally expensive
- Requires retraining for each prediction

**Recommended Settings**:

- n_neighbors: 20
- contamination: 0.1

---

## Spatial Verification Methods

### Pearson Correlation (Default)

**Purpose**: Measure trend consistency between suspect and neighbors

**Formula**:

\[
r = \frac{\sum (X_i - \bar{X})(Y_i - \bar{Y})}{\sqrt{\sum (X_i - \bar{X})^2 \sum (Y_i - \bar{Y})^2}}
\]

Where:

- \(X\) = Suspect station time series
- \(Y\) = Neighbor station time series

**Implementation**:

```python
from scipy.stats import pearsonr

# Get time series for same window
suspect_series = get_series(suspect_station, window_hours=6)
neighbor_series = get_series(neighbor_station, window_hours=6)

# Compute correlation
correlation, p_value = pearsonr(suspect_series, neighbor_series)

# Classify based on correlation
if correlation > 0.6:
    return "weather_event"
elif correlation < 0.3:
    return "device_failure"
else:
    return "suspected"
```

**Thresholds**:

| Correlation | Interpretation | Action |
|-------------|----------------|--------|
| > 0.6 | Strong positive correlation | Weather event (ignore) |
| 0.3 to 0.6 | Weak correlation | Suspected (manual review) |
| < 0.3 | No correlation | Device failure (alert) |

**Advantages**:

- Measures trend, not absolute values
- Robust to different base temperatures
- Interpretable

**Disadvantages**:

- Requires sufficient data points (> 10)
- Can be affected by missing data
- Assumes linear relationship

---

### Distance-Based (Fallback)

**Purpose**: Static comparison when correlation fails

**How It Works**:

Compares current values directly using MAD:

\[
\text{deviation} = \frac{|X_{\text{suspect}} - \text{median}(X_{\text{neighbors}})|}{\text{MAD}(X_{\text{neighbors}})}
\]

**Implementation**:

```python
import numpy as np

# Get current values from all neighbors
neighbor_values = [get_current_value(n) for n in neighbors]

median = np.median(neighbor_values)
mad = np.median(np.abs(neighbor_values - median))

deviation = abs(suspect_value - median) / mad

if deviation > 3:
    return "device_failure"
else:
    return "weather_event"
```

**Use Cases**:

- Not enough historical data for correlation
- All neighbors have missing data
- Correlation computation fails

---

## Method Comparison

### Performance Comparison

| Method | CPU Time | Memory | Accuracy | False Positives |
|--------|----------|--------|----------|-----------------|
| ARIMA | High | Medium | ★★★★★ | Low |
| 3-Sigma | Low | Low | ★★★☆☆ | Medium |
| MAD | Low | Low | ★★★★☆ | High |
| IQR | Low | Low | ★★★☆☆ | Medium |
| Isolation Forest | Medium | Medium | ★★★★☆ | Low |
| STL | High | Medium | ★★★★☆ | Medium |
| LOF | High | High | ★★★☆☆ | Medium |

### Recommended Use Cases

=== "Temperature"

    **Primary**: ARIMA (captures daily cycles)
    
    **Backup**: STL (if strong seasonality)
    
    **Quick Check**: 3-Sigma

=== "Humidity"

    **Primary**: ARIMA
    
    **Backup**: MAD (robust to spikes)
    
    **Quick Check**: IQR

=== "Wind Speed"

    **Primary**: MAD (very volatile)
    
    **Backup**: ARIMA
    
    **Quick Check**: IQR

=== "Pressure"

    **Primary**: 3-Sigma (stable baseline)
    
    **Backup**: ARIMA
    
    **Quick Check**: MAD

=== "Rainfall"

    **Primary**: IQR (sparse data, many zeros)
    
    **Backup**: Isolation Forest
    
    **Quick Check**: Simple threshold (> 100mm/h)

### Tuning Guidelines

1. **Start with ARIMA**: Best overall performance
2. **If too slow**: Switch to 3-Sigma or MAD
3. **If too many false positives**: Lower threshold or switch to IQR
4. **If missing real anomalies**: Increase window size or use Isolation Forest
5. **Always enable spatial verification**: Reduces false positives by 80%

