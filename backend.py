import os
import logging
import json
from flask import Flask, request, jsonify, redirect, render_template_string
from spotipy.oauth2 import SpotifyOAuth
import spotipy

# Suppress Flask's default logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)

# Load Spotify API credentials from credentials.json
CREDENTIALS_FILE = "credentials.json"

try:
    with open(CREDENTIALS_FILE, "r") as file:
        credentials = json.load(file)
        CLIENT_ID = credentials["CLIENT_ID"]
        CLIENT_SECRET = credentials["CLIENT_SECRET"]
        REDIRECT_URI = credentials["REDIRECT_URI"]
except FileNotFoundError:
    print(f"Error: {CREDENTIALS_FILE} not found. Please create the file and add your Spotify credentials.")
    exit(1)
except KeyError as e:
    print(f"Error: Missing key {e} in {CREDENTIALS_FILE}. Please ensure all required fields are present.")
    exit(1)

# Scopes for controlling playback
SCOPE = "user-read-playback-state user-modify-playback-state"

# Spotify OAuth object
sp_oauth = SpotifyOAuth(client_id=CLIENT_ID,
                        client_secret=CLIENT_SECRET,
                        redirect_uri=REDIRECT_URI,
                        scope=SCOPE)

@app.route('/login', methods=['GET'])
def login():
    """Redirect the user to Spotify's login page."""
    auth_url = sp_oauth.get_authorize_url()
    return jsonify({"auth_url": auth_url})

@app.route('/callback', methods=['GET'])
def callback():
    """Handle the redirect from Spotify and fetch the access token."""
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    print("Access token fetched successfully.")
    return render_template_string("""
        <html>
            <body>
                <h1>Login Successful!</h1>
                <p>You can now return to the application.</p>
                <script>
                    // Close the browser tab
                    window.close();
                </script>
            </body>
        </html>
    """)

@app.route('/logout', methods=['POST'])
def logout():
    """Log out by clearing the cached token."""
    cache_handler = sp_oauth.cache_handler
    if isinstance(cache_handler, spotipy.cache_handler.CacheFileHandler):
        cache_path = cache_handler.cache_path
        if os.path.exists(cache_path):
            os.remove(cache_path)
            print("Logged out and cache cleared.")
            return jsonify({"message": "Logged out successfully."})
    return jsonify({"message": "No cached token found."})

@app.route('/token', methods=['GET'])
def get_token():
    """Fetch the cached access token."""
    token_info = sp_oauth.get_cached_token()
    if token_info:
        return jsonify({"access_token": token_info['access_token']})
    return jsonify({"error": "No cached token found."}), 404

@app.route('/token_status', methods=['GET'])
def token_status():
    """Check if a token is cached and refresh it if expired."""
    try:
        token_info = sp_oauth.get_cached_token()
        if not token_info:
            print("No cached token found.")
            return jsonify({"logged_in": False, "error": "No cached token found"}), 401

        # Refresh the token if it has expired
        if sp_oauth.is_token_expired(token_info):
            print("Access token expired. Refreshing...")
            token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
            print(f"Access token refreshed successfully: {token_info['access_token']}")

        return jsonify({"logged_in": True, "access_token": token_info['access_token']})
    except Exception as e:
        print(f"Error refreshing token: {e}")
        return jsonify({"logged_in": False, "error": "Failed to refresh token"}), 401

@app.route('/current_track', methods=['GET'])
def current_track():
    """Fetch the currently playing track."""
    token_info = sp_oauth.get_cached_token()
    if not token_info:
        return jsonify({"error": "Access token is missing or expired"}), 401

    # Refresh the token if it has expired
    if sp_oauth.is_token_expired(token_info):
        try:
            token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
            print("Access token refreshed successfully.")
        except spotipy.exceptions.SpotifyOauthError as e:
            print(f"Error refreshing access token: {e}")
            return jsonify({"error": "Failed to refresh access token"}), 401

    token = token_info['access_token']
    try:
        sp = spotipy.Spotify(auth=token)
        current_playback = sp.current_playback()
        if current_playback:
            return jsonify(current_playback)
        else:
            return jsonify({"error": "No track is currently playing"}), 404
    except spotipy.exceptions.SpotifyException as e:
        return jsonify({"error": str(e)}), 401

if __name__ == '__main__':
    app.run(port=5000)