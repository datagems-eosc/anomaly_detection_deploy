# Device Failure Example

## Scenario: Temperature Sensor Malfunction

### Context

On November 18, 2025, the temperature sensor at Pelion station began reporting unrealistic values (99°C), while neighboring stations showed normal readings.

### Detection Run

```bash
python anomaly_detector.py \
  --end "2025-11-18 16:00:00" \
  --window 6 \
  --temporal-method arima \
  --spatial-verify
```

### Console Output

```
═══════════════════════════════════════════════
 ANOMALY DETECTION REPORT
═══════════════════════════════════════════════
End Time: 2025-11-18 16:00:00
Window: 6 hours
Method: arima
Spatial Verification: Enabled

Total Stations: 14
Anomalous Stations: 1
Normal Stations: 13

Anomaly Breakdown:
  🔴 Device Failures: 1      <-- ⚠️ ACTION REQUIRED!
  🌧️ Weather Events: 0
  ⚠️ Suspected: 0

═══════════════════════════════════════════════
 DETAILED REPORTS
═══════════════════════════════════════════════

[ STATION: pelion (Pelion Mountain) ]
  🔴 Temperature Anomaly:
      Method: arima
      Expected: 5.2°C | Actual: 99.0°C
      • 2025-11-18 16:00:00: 99.00°C -> 🔴 Device Failure
        └─ Diag: Trend Inconsistent (Corr: 0.05, 2 neighbors)

═══════════════════════════════════════════════
 NEIGHBOR COMPARISON - Station: pelion
═══════════════════════════════════════════════

Time                 | pelion  | zagora | volos
---------------------|---------|--------|-------
2025-11-18 10:00:00  | 5.2     | 8.1    | 10.2
2025-11-18 10:30:00  | 5.3     | 8.2    | 10.3
2025-11-18 11:00:00  | 5.4     | 8.3    | 10.4
2025-11-18 11:30:00  | 5.3     | 8.2    | 10.5
2025-11-18 12:00:00  | 5.2     | 8.1    | 10.6
2025-11-18 12:30:00  | 5.1     | 8.0    | 10.7
2025-11-18 13:00:00  | 5.0     | 7.9    | 10.8
2025-11-18 13:30:00  | 4.9     | 7.8    | 10.9
2025-11-18 14:00:00  | 4.8     | 7.7    | 11.0
2025-11-18 14:30:00  | 4.9     | 7.6    | 11.1
2025-11-18 15:00:00  | 5.0     | 7.7    | 11.2
2025-11-18 15:30:00  | 5.1     | 7.8    | 11.3
2025-11-18 16:00:00  | 99.0 🔴 | 7.9    | 11.4

Observation: pelion suddenly jumps to 99°C while neighbors remain stable
→ Classification: Device Failure (Sensor Error)

RECOMMENDATION: Inspect Pelion station temperature sensor
```

### Analysis

#### Why Was This Classified as Device Failure?

1. **Isolated Anomaly**: Only 1 station affected (out of 14)
2. **Low Spatial Correlation**: 0.05 (<< 0.3 threshold)
3. **Unrealistic Value**: 99°C is physically impossible for this location (mountain, altitude 1200m)
4. **Neighbors Normal**: Nearby stations show stable, expected temperatures

#### Spatial Correlation Details

```
Station Pair       | Correlation | Distance | Neighbor Trend
-------------------|-------------|----------|----------------
pelion ↔ zagora    | 0.03        | 32.1 km  | Stable ~8°C
pelion ↔ volos     | 0.08        | 35.4 km  | Stable ~11°C
```

**Interpretation**: Pelion's behavior is completely uncorrelated with neighbors → Isolated issue

### Time Series Visualization

#### Temperature Comparison

```
Temp (°C)
   100 ┤                          ● ← pelion (ANOMALY)
    90 ┤
    80 ┤
    70 ┤
    60 ┤
    50 ┤
    40 ┤
    30 ┤
    20 ┤
    11 ┤                      ─────● volos (NORMAL)
     8 ┤                  ─────●     zagora (NORMAL)
     5 ┤──────────────●
       └─────────────────────────────
       10:00              16:00
```

**Pattern**: 
- **Pelion**: Sudden jump (physically impossible)
- **Neighbors**: Smooth, gradual changes (normal weather)

### Failure Mode Analysis

#### Common Sensor Failure Patterns

| Pattern | Likely Cause | Example Value |
|---------|--------------|---------------|
| Fixed value (99.0) | Sensor disconnected | 99.0, 999.9 |
| Negative spikes | Electrical interference | -127, -999 |
| Constant zero | Power loss | 0.0 |
| Erratic jumps | Loose connection | 5 → 99 → 3 → 105 |

**This case**: Fixed at 99.0 → **Sensor disconnected or failed**

#### Diagnostic Steps for Technicians

1. **Check physical connection**: Sensor cable may be disconnected
2. **Inspect sensor housing**: Water ingress? Damage?
3. **Test voltage**: Proper power supply to sensor?
4. **Check datalogger**: Error codes in station logs?
5. **Replace sensor**: If steps 1-4 show no issue

### What Would Happen Without Spatial Verification?

```bash
# Without --spatial-verify
python anomaly_detector.py \
  --end "2025-11-18 16:00:00" \
  --temporal-method arima
```

**Result**:

```
Anomaly Breakdown:
  🔴 Device Failures: 1      <-- Still flagged, but no confirmation
  🌧️ Weather Events: 0
  ⚠️ Suspected: 0
```

**Problem**: 
- Without spatial verification, we can't be confident
- Could it be an extreme microclimate event?
- Could it be a wildfire nearby?

**With spatial verification**: 
- ✅ Confirmed as device failure (neighbors normal)
- ✅ High confidence → immediate technician dispatch
- ✅ No false investigation of "extreme weather"

### Real-World Impact

#### Before Dual-Verification

```
Operator receives alert → Checks weather reports → Sees clear skies → 
Still uncertain if it's sensor or real → Waits for more data → 
Sensor remains broken for hours/days
```

#### After Dual-Verification

```
System reports "Device Failure" → Operator immediately dispatches technician → 
Sensor replaced within 4 hours → Data integrity restored
```

**Time saved**: ~24 hours  
**False investigations**: 0

---

## Alert Message

### Email Alert (Example)

```
Subject: 🔴 URGENT - Device Failure Detected at Pelion Station

Station: pelion (Pelion Mountain)
Variable: Temperature (temp_out)
Timestamp: 2025-11-18 16:00:00

Anomaly Details:
  - Expected: 5.2°C
  - Actual: 99.0°C
  - Deviation: +93.8°C

Spatial Verification:
  - Correlation with neighbors: 0.05 (very low)
  - Neighbors checked: zagora, volos
  - Neighbor status: All normal

Classification: DEVICE FAILURE (High Confidence)

Action Required:
  ☐ Dispatch technician to Pelion station
  ☐ Check temperature sensor connection
  ☐ Inspect for physical damage
  ☐ Replace sensor if necessary

Dashboard: https://dashboard.example.com/stations/pelion
Report: /var/log/weather/reports/report_20251118_160000.json
```

---

## Comparison: Weather Event vs Device Failure

| Characteristic | Weather Event | Device Failure |
|----------------|---------------|----------------|
| **Affected Stations** | Multiple (≥3) | Single (1) |
| **Spatial Correlation** | High (>0.6) | Low (<0.3) |
| **Value Plausibility** | Realistic | Often unrealistic |
| **Neighbor Behavior** | Similar pattern | Normal/different |
| **Temporal Pattern** | Gradual change | Sudden jump |
| **Action Required** | None | Dispatch technician |

### Example Values

```
Weather Event:
  Station A: 15°C → 10°C (gradual drop)
  Station B: 16°C → 11°C (gradual drop)
  Station C: 14°C → 9°C  (gradual drop)
  Correlation: 0.89 ✅

Device Failure:
  Station A: 5°C → 99°C  (sudden jump)
  Station B: 8°C → 8°C   (stable)
  Station C: 11°C → 11°C (stable)
  Correlation: 0.05 ❌
```

---

## Post-Incident Analysis

### Technician Report (Example)

```
Date: 2025-11-18
Station: Pelion Mountain
Issue: Temperature sensor failure

Findings:
  - Sensor cable disconnected from datalogger
  - Cable connection corroded due to moisture
  - Sensor itself functional when tested separately

Actions Taken:
  - Cleaned and reconnected cable
  - Applied dielectric grease to prevent corrosion
  - Verified readings: Now reporting 5.3°C (expected for altitude)
  - Added cable strain relief

Preventive Measures:
  - Schedule quarterly inspections of cable connections
  - Consider upgrading to sealed waterproof connectors
```

### Validation After Repair

```bash
# Run detection again after repair
python anomaly_detector.py \
  --end "2025-11-18 18:00:00" \
  --spatial-verify
```

**Result**:

```
Total Stations: 14
Anomalous Stations: 0
Normal Stations: 14

✅ All stations operating normally
```

---

## Key Takeaways

1. **Low correlation (<0.3) = Device failure** - Strong indicator of isolated issue
2. **Unrealistic values** - 99°C at mountain station is physically impossible
3. **Spatial verification provides confidence** - Enables immediate action without doubt
4. **Typical failure mode** - Fixed value (99.0) suggests disconnected sensor
5. **Quick resolution** - Clear classification → fast technician dispatch → rapid fix

---

## Related Examples

- [Weather Event Example](weather-event.md) - Contrasting case with high correlation
- [Detection Methods](../system/detection-methods.md) - How ARIMA detected the anomaly
- [Station Network](../system/station-network.md) - Understanding neighbor relationships

