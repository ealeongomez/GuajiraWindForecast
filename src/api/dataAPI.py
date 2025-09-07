#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# api.py
import os
import json
import time
import pytz
import shutil
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Literal

import requests
from fastapi import FastAPI, Query, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from fastapi.responses import JSONResponse

# ==========================
# Configuración básica
# ==========================
TZ = pytz.timezone("America/Bogota")
DATA_DIR = Path(os.getenv("DATA_DIR", "data/raw"))
STATE_DIR = Path(os.getenv("STATE_DIR", "data/state"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
STATE_DIR.mkdir(parents=True, exist_ok=True)

USER_AGENT = 'GuajiraWindForecast/1.0 (Academic Research)'

MUNICIPIOS: Dict[str, tuple] = {
    "riohacha": (11.5447, -72.9072),
    "maicao": (11.3776, -72.2391),
    "uribia": (11.7147, -72.2652),
    "manaure": (11.7794, -72.4469),
    "fonseca": (10.8306, -72.8517),
    "san_juan_del_cesar": (10.7695, -73.0030),
    "albania": (11.1608, -72.5922),
    "barrancas": (10.9577, -72.7947),
    "distraccion": (10.8958, -72.8869),
    "el_molino": (10.6528, -72.9247),
    "hatonuevo": (11.0694, -72.7647),
    "la_jagua_del_pilar": (10.5108, -73.0714),
    "mingueo": (11.2000, -73.3667),
}

HOUR_FIELDS_ALL = "wind_speed_10m,wind_direction_10m,temperature_2m,relative_humidity_2m,precipitation"
HOUR_FIELDS_WIND = "wind_speed_10m,wind_direction_10m"

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": USER_AGENT})

# ==========================
# Utilidades
# ==========================
def now_tz() -> datetime:
    return datetime.now(TZ)

def to_hour_floor(dt: datetime) -> datetime:
    return dt.replace(minute=0, second=0, microsecond=0)

def parse_city(city: str) -> str:
    return city.strip().lower().replace(" ", "_")

def csv_path(city: str, prefix: str = "open_meteo") -> Path:
    city_norm = parse_city(city)
    return DATA_DIR / f"{prefix}_{city_norm}.csv"

def load_existing(city: str) -> pd.DataFrame:
    path = csv_path(city)
    if path.exists():
        df = pd.read_csv(path)
        if "datetime" in df.columns:
            df["datetime"] = pd.to_datetime(df["datetime"])
        return df
    return pd.DataFrame()

def save_df(df: pd.DataFrame, city: str) -> str:
    if df.empty:
        return ""
    path = csv_path(city)
    tmp = path.with_suffix(".tmp.csv")
    df.sort_values("datetime", inplace=True)
    df.drop_duplicates(subset=["municipio", "datetime"], keep="last", inplace=True)
    df.to_csv(tmp, index=False)
    shutil.move(tmp, path)  # atomic-ish replace
    return str(path)

def normalize_df(df: pd.DataFrame, city: str) -> pd.DataFrame:
    if df.empty:
        return df
    df["datetime"] = pd.to_datetime(df["datetime"])
    df["hour"] = df["datetime"].dt.hour
    df["date"] = df["datetime"].dt.date
    df["municipio"] = parse_city(city)
    return df

def filter_hours(df: pd.DataFrame, start_hour: int, end_hour: int) -> pd.DataFrame:
    if df.empty:
        return df
    return df[(df["hour"] >= start_hour) & (df["hour"] <= end_hour)]

def floor_iso(dt: datetime) -> str:
    return to_hour_floor(dt).strftime("%Y-%m-%dT%H:00")

def ymd(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")

def last_timestamp(df: pd.DataFrame) -> Optional[pd.Timestamp]:
    if df.empty:
        return None
    return pd.to_datetime(df["datetime"]).max()

# ==========================
# Descarga desde Open-Meteo
# ==========================
def fetch_archive(lat: float, lon: float, start_date: str, end_date: str, hourly_fields: str) -> pd.DataFrame:
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": hourly_fields,
        "timezone": "America/Bogota",
    }
    r = SESSION.get(url, params=params, timeout=60)
    r.raise_for_status()
    data = r.json()
    if "hourly" not in data or "time" not in data["hourly"]:
        return pd.DataFrame()
    df = pd.DataFrame({"datetime": data["hourly"]["time"]})
    for k, v in data["hourly"].items():
        if k == "time": 
            continue
        df[k] = v
    return df

def fetch_forecast(lat: float, lon: float, hourly_fields: str, past_days: int = 3, forecast_days: int = 1) -> pd.DataFrame:
    """Cubre hoy (y últimas horas) + próximas horas."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": hourly_fields,
        "timezone": "America/Bogota",
        "past_days": past_days,
        "forecast_days": forecast_days,
    }
    r = SESSION.get(url, params=params, timeout=60)
    r.raise_for_status()
    data = r.json()
    if "hourly" not in data or "time" not in data["hourly"]:
        return pd.DataFrame()
    df = pd.DataFrame({"datetime": data["hourly"]["time"]})
    for k, v in data["hourly"].items():
        if k == "time":
            continue
        df[k] = v
    return df

def incremental_pull(city: str,
                     lat: float,
                     lon: float,
                     start_hour: int,
                     end_hour: int,
                     wind_only: bool = False) -> Dict:
    """
    Descarga incremental: desde el último timestamp guardado hasta la hora actual (redondeada hacia abajo).
    Mezcla archive (hasta ayer) + forecast (hoy y próximas horas).
    """
    hourly_fields = HOUR_FIELDS_WIND if wind_only else HOUR_FIELDS_ALL
    city_norm = parse_city(city)

    existing = load_existing(city_norm)
    last_ts = last_timestamp(existing)
    now_local = now_tz()
    target_until = to_hour_floor(now_local)  # no incluimos la hora en curso

    # Si no hay datos previos: traemos última semana como bootstrap
    if last_ts is None:
        start_date = ymd(now_local - timedelta(days=7))
    else:
        start_date = ymd((last_ts + timedelta(hours=1)).to_pydatetime())

    end_date = ymd(target_until)

    # 1) ARCHIVE: solo si la ventana incluye días <= ayer
    yesterday = ymd(now_local - timedelta(days=1))
    archive_df = pd.DataFrame()
    if start_date <= yesterday:
        arch_end = min(yesterday, end_date)
        archive_df = fetch_archive(lat, lon, start_date, arch_end, hourly_fields)

    # 2) FORECAST: para hoy (y últimas horas recientes)
    forecast_df = fetch_forecast(lat, lon, hourly_fields, past_days=3, forecast_days=1)

    # Unimos y filtramos por rango exacto [start_dt, target_until]
    df_all = pd.concat([archive_df, forecast_df], ignore_index=True)
    if df_all.empty:
        new_rows = 0
        merged = existing
    else:
        df_all["datetime"] = pd.to_datetime(df_all["datetime"])
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        start_dt = TZ.localize(datetime.combine(start_dt.date(), datetime.min.time()))
        mask = (df_all["datetime"] >= start_dt) & (df_all["datetime"] <= target_until)
        df_all = df_all.loc[mask].copy()
        df_all = normalize_df(df_all, city_norm)
        df_all = filter_hours(df_all, start_hour, end_hour)

        # merge incremental
        merged = pd.concat([existing, df_all], ignore_index=True)
        merged.drop_duplicates(subset=["municipio", "datetime"], keep="last", inplace=True)
        new_rows = len(merged) - len(existing)

    path = save_df(merged, city_norm)

    stats = {}
    if not merged.empty:
        if "wind_speed_10m" in merged.columns:
            stats = {
                "total_records": len(merged),
                "date_range": {
                    "start": merged["datetime"].min().strftime("%Y-%m-%d %H:%M"),
                    "end": merged["datetime"].max().strftime("%Y-%m-%d %H:%M"),
                },
                "wind_stats": {
                    "mean": float(merged["wind_speed_10m"].mean()),
                    "max": float(merged["wind_speed_10m"].max()),
                    "min": float(merged["wind_speed_10m"].min()),
                    "std": float(merged["wind_speed_10m"].std()),
                    "median": float(merged["wind_speed_10m"].median()),
                },
            }

    return {
        "city": city_norm,
        "new_rows": int(new_rows),
        "file": path,
        "stats": stats,
        "last_timestamp": merged["datetime"].max().strftime("%Y-%m-%d %H:%M") if not merged.empty else None,
        "success": True,
    }

# ==========================
# Esquemas Pydantic
# ==========================
class DownloadRequest(BaseModel):
    city: str = Field(..., description="Nombre del municipio (o personalizado)")
    start_date: Optional[str] = Field(None, description="YYYY-MM-DD (opcional; si no, usa última semana)")
    end_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    start_hour: int = Field(6, ge=0, le=23)
    end_hour: int = Field(18, ge=0, le=23)
    lat: Optional[float] = None
    lon: Optional[float] = None
    wind_only: bool = False

class BulkDownloadRequest(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    start_hour: int = 6
    end_hour: int = 18
    wind_only: bool = False
    cities: Optional[List[str]] = None  # si None => todos

class UpdateRequest(BaseModel):
    city: Optional[str] = None  # si None => todos
    start_hour: int = 6
    end_hour: int = 18
    wind_only: bool = False

# ==========================
# FastAPI
# ==========================
app = FastAPI(title="Guajira Climate API", version="1.0.0")

@app.get("/health")
def health():
    return {"ok": True, "time": now_tz().isoformat()}

@app.get("/files")
def list_files():
    files = sorted([str(p) for p in DATA_DIR.glob("*.csv")])
    return {"files": files}

@app.get("/stats")
def stats(city: str = Query(..., description="Municipio")):
    city_norm = parse_city(city)
    df = load_existing(city_norm)
    if df.empty:
        raise HTTPException(404, f"No hay datos para {city_norm}")
    out = {
        "city": city_norm,
        "records": len(df),
        "date_range": {
            "start": df["datetime"].min().strftime("%Y-%m-%d %H:%M"),
            "end": df["datetime"].max().strftime("%Y-%m-%d %H:%M"),
        }
    }
    if "wind_speed_10m" in df.columns:
        out["wind_stats"] = {
            "mean": float(df["wind_speed_10m"].mean()),
            "max": float(df["wind_speed_10m"].max()),
            "min": float(df["wind_speed_10m"].min()),
            "std": float(df["wind_speed_10m"].std()),
            "median": float(df["wind_speed_10m"].median()),
        }
    return out

@app.post("/download/single")
def download_single(req: DownloadRequest):
    city_norm = parse_city(req.city)
    # Coordenadas
    if req.lat is not None and req.lon is not None:
        lat, lon = req.lat, req.lon
    else:
        if city_norm not in MUNICIPIOS:
            raise HTTPException(400, f"{city_norm} no está en la lista de municipios y no se pasaron coordenadas")
        lat, lon = MUNICIPIOS[city_norm]

    # Rango
    start_date = req.start_date or (now_tz() - timedelta(days=7)).strftime("%Y-%m-%d")
    end_date = req.end_date or now_tz().strftime("%Y-%m-%d")

    hourly_fields = HOUR_FIELDS_WIND if req.wind_only else HOUR_FIELDS_ALL
    try:
        df = fetch_archive(lat, lon, start_date, end_date, hourly_fields)
        df = normalize_df(df, city_norm)
        df = filter_hours(df, req.start_hour, req.end_hour)
        if df.empty:
            return {"success": True, "message": "Sin datos en el rango solicitado", "city": city_norm}
        path = save_df(pd.concat([load_existing(city_norm), df]), city_norm)
        return {
            "success": True,
            "city": city_norm,
            "saved_file": path,
            "rows": len(df),
            "start_date": start_date,
            "end_date": end_date,
        }
    except Exception as e:
        raise HTTPException(500, f"Error en descarga: {e}")

@app.post("/download/bulk")
def download_bulk(req: BulkDownloadRequest):
    cities = req.cities or list(MUNICIPIOS.keys())
    out = []
    for c in cities:
        city_norm = parse_city(c)
        lat, lon = MUNICIPIOS.get(city_norm, (None, None))
        if lat is None:
            out.append({"city": city_norm, "success": False, "error": "municipio desconocido"})
            continue
        try:
            start_date = req.start_date or (now_tz() - timedelta(days=7)).strftime("%Y-%m-%d")
            end_date = req.end_date or now_tz().strftime("%Y-%m-%d")
            hourly_fields = HOUR_FIELDS_WIND if req.wind_only else HOUR_FIELDS_ALL
            df = fetch_archive(lat, lon, start_date, end_date, hourly_fields)
            df = normalize_df(df, city_norm)
            df = filter_hours(df, req.start_hour, req.end_hour)
            if not df.empty:
                path = save_df(pd.concat([load_existing(city_norm), df]), city_norm)
                out.append({"city": city_norm, "rows": len(df), "file": path, "success": True})
            else:
                out.append({"city": city_norm, "rows": 0, "success": True, "message": "sin datos"})
            time.sleep(0.5)
        except Exception as e:
            out.append({"city": city_norm, "success": False, "error": str(e)})
    return {"result": out}

@app.post("/update/hourly")
def update_hourly(req: UpdateRequest):
    """Actualización incremental hasta la hora cerrada."""
    cities = [parse_city(req.city)] if req.city else list(MUNICIPIOS.keys())
    results = []
    for c in cities:
        if c not in MUNICIPIOS:
            results.append({"city": c, "success": False, "error": "municipio desconocido"})
            continue
        lat, lon = MUNICIPIOS[c]
        try:
            res = incremental_pull(c, lat, lon, req.start_hour, req.end_hour, req.wind_only)
            results.append(res)
            time.sleep(0.3)
        except Exception as e:
            results.append({"city": c, "success": False, "error": str(e)})
    return {"updated": results}

# ==========================
# Scheduler opcional
# ==========================
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = BackgroundScheduler(timezone="America/Bogota")

    def scheduled_update():
        for c, (lat, lon) in MUNICIPIOS.items():
            try:
                incremental_pull(c, lat, lon, start_hour=6, end_hour=18, wind_only=False)
                time.sleep(0.3)
            except Exception:
                continue

    # Ejecuta en el minuto 5 de cada hora
    scheduler.add_job(scheduled_update, CronTrigger(minute=5))
    if os.getenv("ENABLE_SCHEDULER", "true").lower() in ("1", "true", "yes"):
        scheduler.start()
except Exception:
    # Si no está APScheduler instalado, la API sigue funcionando sin el cron.
    pass
