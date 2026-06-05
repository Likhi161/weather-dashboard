"""
WeatherVault - Flask Backend Application
==========================================
REST API that integrates AWS Secrets Manager, S3, and OpenWeatherMap.

Run: python app.py (development) or gunicorn app:app (production)
Host: 0.0.0.0:5000
"""

import logging
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from secrets_manager import SecretsManager
from s3_manager import S3Manager

# ─── Logging Setup ───────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("WeatherVault")

# ─── Flask App Setup ─────────────────────────────────────────
app = Flask(__name__)
CORS(app)

# ─── Constants ────────────────────────────────────────────────
SECRET_NAME = "weather-dashboard/api-credentials"

# ─── AWS Service Instances ────────────────────────────────────
secrets_mgr = SecretsManager()
s3_mgr = None  # Initialized lazily after reading bucket name from Secrets Manager


def get_s3_manager():
    """Lazily initialize S3Manager with bucket name from Secrets Manager."""
    global s3_mgr
    if s3_mgr is None:
        bucket_name = secrets_mgr.get_key(SECRET_NAME, "s3_bucket_name")
        region = secrets_mgr.get_key(SECRET_NAME, "s3_region")
        s3_mgr = S3Manager(bucket_name, region)
        logger.info(f"[App] S3Manager initialized with bucket: {bucket_name}")
    return s3_mgr


# ═══════════════════════════════════════════════════════════════
# HEALTH & INFO ROUTES
# ═══════════════════════════════════════════════════════════════


@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint - returns EC2 status, Secrets Manager status, S3 file count."""
    logger.info("[App] Health check requested")

    status = {
        "ec2": {"status": "running", "message": "Flask server is active"},
        "secrets_manager": {"status": "unknown", "message": ""},
        "s3": {"status": "unknown", "message": "", "file_count": 0},
        "overall": "healthy",
    }

    # Check Secrets Manager
    try:
        secrets_mgr.get_secret(SECRET_NAME)
        status["secrets_manager"]["status"] = "connected"
        status["secrets_manager"]["message"] = "Successfully reading secrets"
    except Exception as e:
        status["secrets_manager"]["status"] = "error"
        status["secrets_manager"]["message"] = str(e)
        status["overall"] = "degraded"

    # Check S3
    try:
        s3 = get_s3_manager()
        files = s3.list_files()
        status["s3"]["status"] = "connected"
        status["s3"]["file_count"] = len(files)
        status["s3"]["message"] = f"{len(files)} files in bucket"
    except Exception as e:
        status["s3"]["status"] = "error"
        status["s3"]["message"] = str(e)
        status["overall"] = "degraded"

    return jsonify({"success": True, "data": status, "error": None})


@app.route("/api/app-info", methods=["GET"])
def app_info():
    """Read app_metadata.json from S3 and return it."""
    logger.info("[App] App info requested from S3")
    try:
        s3 = get_s3_manager()
        metadata = s3.get_json("app-config/app_metadata.json")
        return jsonify({"success": True, "data": metadata, "error": None})
    except Exception as e:
        logger.error(f"[App] Error reading app metadata from S3: {e}")
        return jsonify({"success": False, "data": None, "error": str(e)}), 500


# ═══════════════════════════════════════════════════════════════
# WEATHER ROUTES
# ═══════════════════════════════════════════════════════════════


@app.route("/api/weather/current", methods=["GET"])
def current_weather():
    """Fetch current weather for a city from OpenWeatherMap."""
    city = request.args.get("city")
    if not city:
        return jsonify({"success": False, "data": None, "error": "City parameter is required"}), 400

    logger.info(f"[App] Current weather requested for city: {city}")

    try:
        # Fetch API key and config from Secrets Manager
        api_key = secrets_mgr.get_key(SECRET_NAME, "weather_api_key")
        base_url = secrets_mgr.get_key(SECRET_NAME, "api_base_url")
        units = secrets_mgr.get_key(SECRET_NAME, "default_units")

        # Call OpenWeatherMap API
        url = f"{base_url}/weather"
        params = {"q": city, "appid": api_key, "units": units}

        logger.info(f"[App] Calling OpenWeatherMap current weather API for: {city}")
        response = requests.get(url, params=params, timeout=10)

        if response.status_code == 401:
            logger.error("[App] OpenWeatherMap API key is invalid or not activated")
            return jsonify({
                "success": False,
                "data": None,
                "error": "Weather API key is invalid. Wait 15 minutes for key activation.",
            }), 401

        if response.status_code == 404:
            logger.error(f"[App] City not found: {city}")
            return jsonify({
                "success": False,
                "data": None,
                "error": f"City '{city}' not found. Please check the spelling.",
            }), 404

        response.raise_for_status()
        data = response.json()

        # Build clean response
        weather_result = {
            "city": data["name"],
            "country": data["sys"]["country"],
            "temperature": data["main"]["temp"],
            "feels_like": data["main"]["feels_like"],
            "temp_min": data["main"]["temp_min"],
            "temp_max": data["main"]["temp_max"],
            "humidity": data["main"]["humidity"],
            "description": data["weather"][0]["description"],
            "icon": data["weather"][0]["icon"],
            "wind_speed": data["wind"]["speed"],
            "wind_deg": data["wind"].get("deg", 0),
            "pressure": data["main"]["pressure"],
            "visibility": data.get("visibility", 0),
            "units": units,
        }

        # Save search log to S3
        try:
            s3 = get_s3_manager()
            s3.save_weather_log(city, weather_result)
            logger.info(f"[App] Weather search for '{city}' logged to S3")
        except Exception as s3_err:
            logger.warning(f"[App] Failed to log weather search to S3: {s3_err}")

        return jsonify({"success": True, "data": weather_result, "error": None})

    except requests.exceptions.Timeout:
        logger.error("[App] OpenWeatherMap API request timed out")
        return jsonify({
            "success": False, "data": None,
            "error": "Weather API request timed out. Please try again.",
        }), 500
    except requests.exceptions.RequestException as e:
        logger.error(f"[App] Weather API request failed: {e}")
        return jsonify({
            "success": False, "data": None,
            "error": f"Weather API request failed: {str(e)}",
        }), 500
    except Exception as e:
        logger.error(f"[App] Error in current_weather: {e}")
        return jsonify({"success": False, "data": None, "error": str(e)}), 500


@app.route("/api/weather/forecast", methods=["GET"])
def weather_forecast():
    """Fetch 5-step forecast for a city from OpenWeatherMap."""
    city = request.args.get("city")
    if not city:
        return jsonify({"success": False, "data": None, "error": "City parameter is required"}), 400

    logger.info(f"[App] Forecast requested for city: {city}")

    try:
        api_key = secrets_mgr.get_key(SECRET_NAME, "weather_api_key")
        base_url = secrets_mgr.get_key(SECRET_NAME, "api_base_url")
        units = secrets_mgr.get_key(SECRET_NAME, "default_units")

        url = f"{base_url}/forecast"
        params = {"q": city, "appid": api_key, "units": units, "cnt": 5}

        logger.info(f"[App] Calling OpenWeatherMap forecast API for: {city}")
        response = requests.get(url, params=params, timeout=10)

        if response.status_code == 401:
            return jsonify({
                "success": False, "data": None,
                "error": "Weather API key is invalid or not activated.",
            }), 401

        if response.status_code == 404:
            return jsonify({
                "success": False, "data": None,
                "error": f"City '{city}' not found.",
            }), 404

        response.raise_for_status()
        data = response.json()

        forecast = []
        for item in data.get("list", []):
            forecast.append({
                "datetime": item["dt_txt"],
                "temp": item["main"]["temp"],
                "feels_like": item["main"]["feels_like"],
                "description": item["weather"][0]["description"],
                "icon": item["weather"][0]["icon"],
                "humidity": item["main"]["humidity"],
                "wind_speed": item["wind"]["speed"],
            })

        return jsonify({"success": True, "data": {"forecast": forecast}, "error": None})

    except requests.exceptions.RequestException as e:
        logger.error(f"[App] Forecast API error: {e}")
        return jsonify({
            "success": False, "data": None,
            "error": f"Forecast API error: {str(e)}",
        }), 500
    except Exception as e:
        logger.error(f"[App] Error in weather_forecast: {e}")
        return jsonify({"success": False, "data": None, "error": str(e)}), 500


# ═══════════════════════════════════════════════════════════════
# CITY & TIPS ROUTES
# ═══════════════════════════════════════════════════════════════


@app.route("/api/cities", methods=["GET"])
def get_cities():
    """Read cities.json from S3 and return featured cities."""
    logger.info("[App] Cities list requested from S3")
    try:
        s3 = get_s3_manager()
        data = s3.get_json("app-config/cities.json")
        return jsonify({"success": True, "data": data, "error": None})
    except Exception as e:
        logger.error(f"[App] Error reading cities from S3: {e}")
        return jsonify({"success": False, "data": None, "error": str(e)}), 500


@app.route("/api/weather-tip", methods=["GET"])
def weather_tip():
    """Get a weather tip for a given condition from S3."""
    condition = request.args.get("condition", "").lower()
    if not condition:
        return jsonify({"success": False, "data": None, "error": "Condition parameter is required"}), 400

    logger.info(f"[App] Weather tip requested for condition: {condition}")

    try:
        s3 = get_s3_manager()
        tips_data = s3.get_json("app-config/weather_tips.json")
        tips = tips_data.get("tips", {})

        # Try to match condition
        tip = tips.get(condition)
        if not tip:
            # Try fuzzy matching
            for key in tips:
                if key in condition or condition in key:
                    tip = tips[key]
                    break

        if tip:
            return jsonify({
                "success": True,
                "data": {"condition": condition, "tip": tip["text"], "color": tip["color"]},
                "error": None,
            })
        else:
            return jsonify({
                "success": True,
                "data": {
                    "condition": condition,
                    "tip": "Stay prepared for any weather! Check back for specific tips.",
                    "color": "#6366f1",
                },
                "error": None,
            })

    except Exception as e:
        logger.error(f"[App] Error reading weather tips from S3: {e}")
        return jsonify({"success": False, "data": None, "error": str(e)}), 500


# ═══════════════════════════════════════════════════════════════
# S3 INFO ROUTES
# ═══════════════════════════════════════════════════════════════


@app.route("/api/s3/info", methods=["GET"])
def s3_info():
    """Return S3 bucket statistics."""
    logger.info("[App] S3 bucket info requested")
    try:
        s3 = get_s3_manager()
        stats = s3.get_bucket_stats()
        return jsonify({"success": True, "data": stats, "error": None})
    except Exception as e:
        logger.error(f"[App] Error getting S3 info: {e}")
        return jsonify({"success": False, "data": None, "error": str(e)}), 500


@app.route("/api/s3/weather-history", methods=["GET"])
def s3_weather_history():
    """List all recent weather search logs from S3."""
    logger.info("[App] Weather history requested from S3")
    try:
        s3 = get_s3_manager()
        files = s3.list_files(prefix="weather-data/")

        # Filter for latest.json files only
        latest_files = [f for f in files if f["key"].endswith("latest.json")]

        history = []
        for f in latest_files:
            try:
                data = s3.get_json(f["key"])
                weather = data.get("weather_data", {})
                history.append({
                    "city": data.get("city", "Unknown"),
                    "timestamp": data.get("timestamp", ""),
                    "temperature": weather.get("temperature", "N/A"),
                    "description": weather.get("description", "N/A"),
                    "s3_path": f["key"],
                })
            except Exception as read_err:
                logger.warning(f"[App] Could not read history file {f['key']}: {read_err}")

        return jsonify({"success": True, "data": {"history": history}, "error": None})

    except Exception as e:
        logger.error(f"[App] Error reading weather history: {e}")
        return jsonify({"success": False, "data": None, "error": str(e)}), 500


@app.route("/api/s3/files", methods=["GET"])
def s3_files():
    """List files in S3 bucket with optional prefix filter."""
    prefix = request.args.get("prefix", "")
    logger.info(f"[App] S3 file listing requested with prefix: '{prefix}'")
    try:
        s3 = get_s3_manager()
        files = s3.list_files(prefix=prefix)
        return jsonify({"success": True, "data": {"files": files, "count": len(files)}, "error": None})
    except Exception as e:
        logger.error(f"[App] Error listing S3 files: {e}")
        return jsonify({"success": False, "data": None, "error": str(e)}), 500


# ═══════════════════════════════════════════════════════════════
# SECRETS INFO ROUTE
# ═══════════════════════════════════════════════════════════════


@app.route("/api/secrets/info", methods=["GET"])
def secrets_info():
    """Return secrets metadata only - never actual secret values."""
    logger.info("[App] Secrets metadata requested (values never exposed)")
    try:
        secret_data = secrets_mgr.get_secret(SECRET_NAME)

        # Get API key preview (first 8 chars only)
        api_key = secret_data.get("weather_api_key", "")
        api_key_preview = api_key[:8] + "..." if len(api_key) > 8 else "***"

        metadata = {
            "secret_name": SECRET_NAME,
            "available_keys": list(secret_data.keys()),
            "api_key_preview": api_key_preview,
            "app_id": secret_data.get("app_id", "N/A"),
            "s3_bucket": secret_data.get("s3_bucket_name", "N/A"),
            "units": secret_data.get("default_units", "N/A"),
            "version": secret_data.get("app_version", "N/A"),
            "cache_info": secrets_mgr.get_cache_info(),
        }

        return jsonify({"success": True, "data": metadata, "error": None})

    except Exception as e:
        logger.error(f"[App] Error reading secrets metadata: {e}")
        return jsonify({"success": False, "data": None, "error": str(e)}), 500


# ═══════════════════════════════════════════════════════════════
# CACHE MANAGEMENT
# ═══════════════════════════════════════════════════════════════


@app.route("/api/cache/clear", methods=["POST"])
def clear_caches():
    """Clear both Secrets Manager and S3 caches."""
    logger.info("[App] Cache clear requested for all services")
    try:
        secrets_mgr.clear_cache()

        s3_cleared = False
        try:
            s3 = get_s3_manager()
            s3.clear_cache()
            s3_cleared = True
        except Exception:
            pass

        return jsonify({
            "success": True,
            "data": {
                "secrets_cache": "cleared",
                "s3_cache": "cleared" if s3_cleared else "not initialized",
                "message": "All caches cleared successfully",
            },
            "error": None,
        })
    except Exception as e:
        logger.error(f"[App] Error clearing caches: {e}")
        return jsonify({"success": False, "data": None, "error": str(e)}), 500


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("  WeatherVault - AWS Weather Dashboard")
    logger.info("  Starting Flask server on http://0.0.0.0:5000")
    logger.info("=" * 60)
    app.run(host="0.0.0.0", port=5000, debug=True)
