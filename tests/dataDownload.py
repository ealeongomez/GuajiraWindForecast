#!/usr/bin/env python3
"""
Clase para descargar datos climáticos de La Guajira usando Open-Meteo API
"""

import requests
import pandas as pd
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path

class ClimateDataDownloader:
    """
    Clase para descargar datos climáticos de La Guajira desde Open-Meteo API
    """
    
    def __init__(self, start_date: str = None, end_date: str = None, 
                 start_hour: int = 6, end_hour: int = 18):
        """
        Inicializa el descargador de datos climáticos
        
        Args:
            start_date: Fecha de inicio (YYYY-MM-DD)
            end_date: Fecha de fin (YYYY-MM-DD)
            start_hour: Hora inicial (0-23)
            end_hour: Hora final (0-23)
        """
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'GuajiraWindForecast/1.0 (Academic Research)'
        })
        
        # Configurar fechas por defecto (últimos 7 días)
        if start_date is None:
            self.start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        else:
            self.start_date = start_date
            
        if end_date is None:
            self.end_date = datetime.now().strftime("%Y-%m-%d")
        else:
            self.end_date = end_date
            
        self.start_hour = start_hour
        self.end_hour = end_hour
        
        # Coordenadas de municipios de La Guajira
        self.municipios = {
            "Riohacha": (11.5447, -72.9072),
            "Maicao": (11.3776, -72.2391),
            "Uribia": (11.7147, -72.2652),
            "Manaure": (11.7794, -72.4469),
            "Fonseca": (10.8306, -72.8517),
            "San_Juan_del_Cesar": (10.7695, -73.0030),
            "Albania": (11.1608, -72.5922),
            "Barrancas": (10.9577, -72.7947),
            "Distraccion": (10.8958, -72.8869),
            "El_Molino": (10.6528, -72.9247),
            "Hatonuevo": (11.0694, -72.7647),
            "La_Jagua_del_Pilar": (10.5108, -73.0714),
            "Mingueo": (11.2000, -73.3667)
        }
        
        # Crear directorio de datos si no existe
        self.data_dir = Path("data/raw")
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def fetch_open_meteo_hourly(self, municipio: str, lat: float, lon: float) -> pd.DataFrame:
        """
        Consulta Open-Meteo y filtra por el rango horario definido.
        
        Args:
            municipio: Nombre del municipio
            lat: Latitud
            lon: Longitud
            
        Returns:
            DataFrame con datos de velocidad del viento
        """
        print(f"📡 Descargando datos para {municipio}...")
        
        url = "https://archive-api.open-meteo.com/v1/archive"
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "hourly": "wind_speed_10m,wind_direction_10m,temperature_2m,relative_humidity_2m,precipitation",
            "timezone": "America/Bogota"
        }

        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            df = pd.DataFrame({
                "datetime": data["hourly"]["time"],
                "wind_speed_10m": data["hourly"]["wind_speed_10m"],
                "wind_direction_10m": data["hourly"]["wind_direction_10m"],
                "temperature_2m": data["hourly"]["temperature_2m"],
                "relative_humidity_2m": data["hourly"]["relative_humidity_2m"],
                "precipitation": data["hourly"]["precipitation"]
            })

            df["datetime"] = pd.to_datetime(df["datetime"])
            df["hour"] = df["datetime"].dt.hour
            df["date"] = df["datetime"].dt.date
            df["municipio"] = municipio

            # Filtro por hora
            df = df[(df["hour"] >= self.start_hour) & (df["hour"] <= self.end_hour)]
            
            print(f"✅ Datos obtenidos para {municipio}: {len(df)} registros")
            return df
            
        except Exception as e:
            print(f"❌ Error obteniendo datos para {municipio}: {e}")
            return pd.DataFrame()
    
    def fetch_wind_data_only(self, municipio: str, lat: float, lon: float) -> pd.DataFrame:
        """
        Consulta Open-Meteo y obtiene únicamente datos de velocidad del viento.
        
        Args:
            municipio: Nombre del municipio
            lat: Latitud
            lon: Longitud
            
        Returns:
            DataFrame con datos de velocidad del viento
        """
        print(f"🌬️ Descargando datos de viento para {municipio}...")
        
        url = "https://archive-api.open-meteo.com/v1/archive"
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "hourly": "wind_speed_10m,wind_direction_10m",  # Solo datos de viento
            "timezone": "America/Bogota"
        }

        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            df = pd.DataFrame({
                "datetime": data["hourly"]["time"],
                "wind_speed_10m": data["hourly"]["wind_speed_10m"],
                "wind_direction_10m": data["hourly"]["wind_direction_10m"]
            })

            df["datetime"] = pd.to_datetime(df["datetime"])
            df["hour"] = df["datetime"].dt.hour
            df["date"] = df["datetime"].dt.date
            df["municipio"] = municipio

            # Filtro por hora
            df = df[(df["hour"] >= self.start_hour) & (df["hour"] <= self.end_hour)]
            
            print(f"✅ Datos de viento obtenidos para {municipio}: {len(df)} registros")
            return df
            
        except Exception as e:
            print(f"❌ Error obteniendo datos de viento para {municipio}: {e}")
            return pd.DataFrame()
    
    def save_wind_data(self, df: pd.DataFrame, municipio: str) -> str:
        """
        Guarda los datos de viento como CSV en la ruta especificada.
        
        Args:
            df: DataFrame con los datos de viento
            municipio: Nombre del municipio
            
        Returns:
            Ruta del archivo guardado
        """
        if df.empty:
            print(f"⚠️  No hay datos de viento para guardar de {municipio}")
            return ""
            
        filename = f"wind_data_{municipio.lower().replace('_', '_')}_{self.start_date}_{self.end_date}.csv"
        filepath = self.data_dir / filename
        df.to_csv(filepath, index=False)
        print(f"💾 Datos de viento guardados: {filepath}")
        return str(filepath)
    
    def download_single_city(self, city_name: str, lat: float = None, lon: float = None) -> Dict[str, any]:
        """
        Descarga datos de velocidad del viento para una ciudad específica
        
        Args:
            city_name: Nombre de la ciudad
            lat: Latitud (opcional, si no se proporciona se busca en municipios predefinidos)
            lon: Longitud (opcional, si no se proporciona se busca en municipios predefinidos)
            
        Returns:
            Diccionario con DataFrame de datos de viento y ruta del archivo guardado
        """
        print(f"🌬️ Descargando datos de velocidad del viento para: {city_name}")
        print(f"📅 Período: {self.start_date} a {self.end_date}")
        print(f"⏰ Horario: {self.start_hour}:00 a {self.end_hour}:00")
        print("=" * 50)
        
        # Verificar si la ciudad está en los municipios predefinidos
        if lat is None or lon is None:
            if city_name in self.municipios:
                lat, lon = self.municipios[city_name]
                print(f"📍 Usando coordenadas predefinidas para {city_name}: ({lat}, {lon})")
            else:
                print(f"❌ Error: {city_name} no está en la lista de municipios predefinidos")
                print(f"   Municipios disponibles: {list(self.municipios.keys())}")
                print(f"   Por favor, proporciona latitud y longitud manualmente")
                return {"data": pd.DataFrame(), "filepath": "", "success": False}
        else:
            print(f"📍 Usando coordenadas proporcionadas: ({lat}, {lon})")
        
        # Descargar datos usando función específica para viento
        df = self.fetch_wind_data_only(city_name, lat, lon)
        
        if not df.empty:
            # Guardar datos
            filepath = self.save_wind_data(df, city_name)
            
            # Generar estadísticas de viento
            stats = {
                "total_records": len(df),
                "date_range": {
                    "start": df['date'].min().strftime("%Y-%m-%d"),
                    "end": df['date'].max().strftime("%Y-%m-%d")
                },
                "wind_stats": {
                    "mean": df['wind_speed_10m'].mean(),
                    "max": df['wind_speed_10m'].max(),
                    "min": df['wind_speed_10m'].min(),
                    "std": df['wind_speed_10m'].std(),
                    "median": df['wind_speed_10m'].median()
                }
            }
            
            print(f"\n✅ Descarga de datos de viento completada para {city_name}")
            print(f"   - Registros obtenidos: {stats['total_records']}")
            print(f"   - Velocidad promedio: {stats['wind_stats']['mean']:.1f} km/h")
            print(f"   - Velocidad máxima: {stats['wind_stats']['max']:.1f} km/h")
            print(f"   - Archivo guardado: {filepath}")
            
            return {
                "data": df,
                "filepath": filepath,
                "stats": stats,
                "success": True
            }
        else:
            print(f"❌ No se pudieron obtener datos de viento para {city_name}")
            return {
                "data": pd.DataFrame(),
                "filepath": "",
                "stats": {},
                "success": False
            }

    def save_data(self, df: pd.DataFrame, municipio: str) -> str:
        """
        Guarda los datos como CSV en la ruta especificada.
        
        Args:
            df: DataFrame con los datos
            municipio: Nombre del municipio
            
        Returns:
            Ruta del archivo guardado
        """
        if df.empty:
            print(f"⚠️  No hay datos para guardar de {municipio}")
            return ""
            
        filename = f"open_meteo_{municipio.lower().replace('_', '_')}_{self.start_date}_{self.end_date}.csv"
        filepath = self.data_dir / filename
        df.to_csv(filepath, index=False)
        print(f"💾 Guardado: {filepath}")
        return str(filepath)
    
    def download_all_data(self) -> Dict[str, pd.DataFrame]:
        """
        Descarga datos de todos los municipios de La Guajira
        
        Returns:
            Diccionario con DataFrames por municipio
        """
        print(f"🌬️ Iniciando descarga de datos climáticos para La Guajira")
        print(f"📅 Período: {self.start_date} a {self.end_date}")
        print(f"⏰ Horario: {self.start_hour}:00 a {self.end_hour}:00")
        print("=" * 60)
        
        all_data = {}
        saved_files = []
        
        for municipio, (lat, lon) in self.municipios.items():
            print(f"\n Procesando: {municipio}")
            
            # Descargar datos
            df = self.fetch_open_meteo_hourly(municipio, lat, lon)
            
            if not df.empty:
                all_data[municipio] = df
                
                # Guardar datos
                filepath = self.save_data(df, municipio)
                if filepath:
                    saved_files.append(filepath)
                
                # Pausa para no sobrecargar la API
                import time
                time.sleep(1)
            else:
                print(f"⚠️  No se pudieron obtener datos para {municipio}")
        
        print(f"\n Resumen:")
        print(f"   - Municipios procesados: {len(self.municipios)}")
        print(f"   - Datos obtenidos: {len(all_data)}")
        print(f"   - Archivos guardados: {len(saved_files)}")
        
        return all_data
    
    def generate_summary_report(self, data_dict: Dict[str, pd.DataFrame]) -> str:
        """
        Genera un reporte resumen de los datos descargados
        
        Args:
            data_dict: Diccionario con DataFrames por municipio
            
        Returns:
            String con el reporte
        """
        print("\n📊 Generando reporte resumen...")
        
        report = []
        report.append("=" * 60)
        report.append("🌬️ REPORTE DE DATOS CLIMÁTICOS - LA GUAJIRA")
        report.append("=" * 60)
        report.append(f"📅 Período: {self.start_date} a {self.end_date}")
        report.append(f"⏰ Horario: {self.start_hour}:00 a {self.end_hour}:00")
        report.append("=" * 60)
        
        total_records = 0
        for municipio, df in data_dict.items():
            if not df.empty:
                records = len(df)
                total_records += records
                
                report.append(f"\n📍 {municipio}:")
                report.append(f"   - Registros: {records}")
                report.append(f"   - Fechas: {df['date'].min()} a {df['date'].max()}")
                
                if 'wind_speed_10m' in df.columns:
                    avg_wind = df['wind_speed_10m'].mean()
                    max_wind = df['wind_speed_10m'].max()
                    report.append(f"   - Velocidad viento promedio: {avg_wind:.1f} km/h")
                    report.append(f"   - Velocidad viento máxima: {max_wind:.1f} km/h")
                
                if 'temperature_2m' in df.columns:
                    avg_temp = df['temperature_2m'].mean()
                    report.append(f"   - Temperatura promedio: {avg_temp:.1f}°C")
        
        report.append(f"\n📈 TOTAL:")
        report.append(f"   - Registros totales: {total_records}")
        report.append(f"   - Municipios con datos: {len(data_dict)}")
        report.append("\n" + "=" * 60)
        report.append("✅ Descarga completada exitosamente!")
        report.append("=" * 60)
        
        return "\n".join(report)
    
    def get_statistics(self, data_dict: Dict[str, pd.DataFrame]) -> Dict:
        """
        Calcula estadísticas de los datos descargados
        
        Args:
            data_dict: Diccionario con DataFrames por municipio
            
        Returns:
            Diccionario con estadísticas
        """
        stats = {
            'total_records': 0,
            'municipios_with_data': 0,
            'date_range': {},
            'wind_stats': {},
            'temperature_stats': {}
        }
        
        for municipio, df in data_dict.items():
            if not df.empty:
                stats['municipios_with_data'] += 1
                stats['total_records'] += len(df)
                
                # Estadísticas de viento
                if 'wind_speed_10m' in df.columns:
                    stats['wind_stats'][municipio] = {
                        'mean': df['wind_speed_10m'].mean(),
                        'max': df['wind_speed_10m'].max(),
                        'min': df['wind_speed_10m'].min(),
                        'std': df['wind_speed_10m'].std()
                    }
                
                # Estadísticas de temperatura
                if 'temperature_2m' in df.columns:
                    stats['temperature_stats'][municipio] = {
                        'mean': df['temperature_2m'].mean(),
                        'max': df['temperature_2m'].max(),
                        'min': df['temperature_2m'].min(),
                        'std': df['temperature_2m'].std()
                    }
        
        return stats


def main():
    """
    Función principal para ejecutar la descarga de datos
    """
    print("🧪 TEST: Descarga de Datos Climáticos de La Guajira")
    print("=" * 60)
    
    # Crear instancia del descargador
    downloader = ClimateDataDownloader(
        start_date="2023-07-01",
        end_date="2023-07-07",
        start_hour=6,
        end_hour=18
    )
    
    # Ejemplo 1: Descargar datos de viento de una ciudad específica (usando coordenadas predefinidas)
    print("\n" + "="*60)
    print("🌬️ EJEMPLO 1: Descarga de datos de viento (Riohacha)")
    print("="*60)
    
    result_riohacha = downloader.download_single_city("Riohacha")
    if result_riohacha["success"]:
        print(f"📊 Estadísticas de viento de Riohacha:")
        stats = result_riohacha["stats"]
        print(f"   - Registros: {stats['total_records']}")
        print(f"   - Velocidad promedio: {stats['wind_stats']['mean']:.1f} km/h")
        print(f"   - Velocidad máxima: {stats['wind_stats']['max']:.1f} km/h")
        print(f"   - Velocidad mínima: {stats['wind_stats']['min']:.1f} km/h")
        print(f"   - Desviación estándar: {stats['wind_stats']['std']:.1f} km/h")
    
    # Ejemplo 2: Descargar datos de viento con coordenadas personalizadas
    print("\n" + "="*60)
    print("🌬️ EJEMPLO 2: Descarga de datos de viento con coordenadas personalizadas")
    print("="*60)
    
    # Coordenadas de ejemplo para una ubicación personalizada
    custom_lat, custom_lon = 11.5447, -72.9072  # Coordenadas de Riohacha como ejemplo
    result_custom = downloader.download_single_city("Ubicacion_Personalizada", custom_lat, custom_lon)
    if result_custom["success"]:
        print(f"📊 Datos de viento obtenidos para ubicación personalizada")
        print(f"   - Velocidad promedio: {result_custom['stats']['wind_stats']['mean']:.1f} km/h")
        print(f"   - Archivo guardado: {result_custom['filepath']}")
    
    # Ejemplo 3: Descargar todos los datos (función original)
    print("\n" + "="*60)
    print("🌬️ EJEMPLO 3: Descarga de todos los municipios")
    print("="*60)
    
    data_dict = downloader.download_all_data()
    
    # Generar y mostrar reporte
    report = downloader.generate_summary_report(data_dict)
    print(report)
    
    # Mostrar estadísticas
    stats = downloader.get_statistics(data_dict)
    print(f"\n📋 ESTADÍSTICAS:")
    print(f"   - Total de registros: {stats['total_records']}")
    print(f"   - Municipios con datos: {stats['municipios_with_data']}")
    
    print("\n Próximos pasos:")
    print("1. Analizar datos en notebooks/")
    print("2. Implementar procesamiento de datos")
    print("3. Crear modelos de predicción")
    print("4. Desarrollar chatbot")


if __name__ == "__main__":
    main()

