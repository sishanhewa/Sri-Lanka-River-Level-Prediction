"""
Feature Service: Generates the exact same 40 features used during training.
This module is shared across training, live prediction, and simulation.
"""
import pandas as pd
import numpy as np


STATION_MAPPING = {
    'NagalagamStreet': 'Nagalagam Street',
    'Kalawellawa(Millakanda)': 'Kalawellawa (Millakanda)',
}

FEATURE_COLUMNS = [
    'water_level', 'rainfall_mm', 'minor_flood_level', 'major_flood_level',
    'gap_flag_6h', 'gap_flag_24h', 'water_level_was_missing', 'rainfall_was_missing',
    'hour', 'day', 'month', 'day_of_week', 'quarter', 'is_monsoon',
    'water_level_delta',
    'water_level_lag_1', 'water_level_lag_2', 'water_level_lag_4',
    'water_level_lag_8', 'water_level_lag_16', 'water_level_lag_24',
    'rainfall_lag_1', 'rainfall_lag_2', 'rainfall_lag_4', 'rainfall_lag_8',
    'water_level_roll_mean_3', 'water_level_roll_max_3',
    'rainfall_roll_sum_3', 'rainfall_roll_sum_6', 'rainfall_roll_sum_8',
    'rainfall_roll_sum_12', 'rainfall_roll_sum_16',
    'flood_ratio_minor', 'flood_ratio_major',
    'above_minor_flag', 'above_major_flag',
    'station_encoded', 'river_basin_encoded',
    'rainfall_type_encoded', 'status_encoded',
]


def generate_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Takes a DataFrame of recent observations for a single station
    (sorted by time, newest last) and returns a single-row feature vector
    ready for model.predict().
    
    Expects columns: datetime, water_level, rainfall_mm, 
                     minor_flood_level, major_flood_level, station_encoded, etc.
    """
    df = df.copy().sort_values('datetime').reset_index(drop=True)

    # Time features
    last_row = df.iloc[-1]
    dt = pd.to_datetime(last_row['datetime'])

    # Time gap tracking
    if len(df) >= 2:
        time_diff = (pd.to_datetime(df.iloc[-1]['datetime']) - pd.to_datetime(df.iloc[-2]['datetime'])).total_seconds() / 3600.0
    else:
        time_diff = 0

    features = {
        'water_level': last_row.get('water_level', np.nan),
        'rainfall_mm': last_row.get('rainfall_mm', 0),
        'minor_flood_level': last_row.get('minor_flood_level', np.nan),
        'major_flood_level': last_row.get('major_flood_level', np.nan),
        'gap_flag_6h': int(time_diff > 6),
        'gap_flag_24h': int(time_diff > 24),
        'water_level_was_missing': 0,
        'rainfall_was_missing': int(pd.isna(last_row.get('rainfall_mm'))),
        'hour': dt.hour,
        'day': dt.day,
        'month': dt.month,
        'day_of_week': dt.dayofweek,
        'quarter': dt.quarter,
        'is_monsoon': int(dt.month in [5, 6, 7, 10, 11, 12]),
    }

    # Delta
    wl = df['water_level'].values
    features['water_level_delta'] = wl[-1] - wl[-2] if len(wl) >= 2 else 0

    # Lags
    for lag in [1, 2, 4, 8, 16, 24]:
        features[f'water_level_lag_{lag}'] = wl[-1 - lag] if len(wl) > lag else np.nan

    rain = df['rainfall_mm'].fillna(0).values
    for lag in [1, 2, 4, 8]:
        features[f'rainfall_lag_{lag}'] = rain[-1 - lag] if len(rain) > lag else 0

    # Rolling
    features['water_level_roll_mean_3'] = np.mean(wl[-3:]) if len(wl) >= 3 else np.mean(wl)
    features['water_level_roll_max_3'] = np.max(wl[-3:]) if len(wl) >= 3 else np.max(wl)

    for w in [3, 6, 8, 12, 16]:
        features[f'rainfall_roll_sum_{w}'] = np.sum(rain[-w:]) if len(rain) >= w else np.sum(rain)

    # Flood ratios
    minor = features['minor_flood_level']
    major = features['major_flood_level']
    wl_now = features['water_level']
    features['flood_ratio_minor'] = wl_now / minor if minor and minor > 0 else 0
    features['flood_ratio_major'] = wl_now / major if major and major > 0 else 0
    features['above_minor_flag'] = int(wl_now > minor) if minor else 0
    features['above_major_flag'] = int(wl_now > major) if major else 0

    # Encoded categoricals (passed through from caller)
    for col in ['station_encoded', 'river_basin_encoded', 'rainfall_type_encoded', 'status_encoded']:
        features[col] = last_row.get(col, 0)

    return pd.DataFrame([features])[FEATURE_COLUMNS].replace([np.inf, -np.inf], np.nan)
