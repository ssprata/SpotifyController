import tkinter as tk
from tkinter import simpledialog
from PIL import Image, ImageTk, ImageOps  # For handling images
import keyboard
import requests
import webbrowser
import ctypes
import subprocess
import os
import threading
import json
import sys

# Determine the correct path for the config file
if getattr(sys, 'frozen', False):
    # If running as a bundled executable
    CONFIG_FILE = os.path.join(sys._MEIPASS, "config.json")
else:
    # If running as a script
    CONFIG_FILE = "config.json"

# Create the main Tkinter window
root = tk.Tk()
root.title("Spotify Controller")
root.geometry("450x300")
root.resizable(False, False)

# Set the background color of the root window
root.configure(bg="#07003a")

def process_image(image_path, target_color=None, invert_black=False):
    """
    Process an image to replace black pixels with a target color or invert black to white.
    """
    try:
        image = Image.open(image_path).resize((30, 30)).convert("RGBA")
        data = image.getdata()
        new_data = []

        for item in data:
            if item[:3] == (0, 0, 0): 
                if target_color:
                    new_data.append((*target_color, item[3]))  
                elif invert_black:
                    new_data.append((255, 255, 255, item[3]))  
                else:
                    new_data.append(item) 
            else:
                new_data.append(item)

        image.putdata(new_data)
        return ImageTk.PhotoImage(image)
    except FileNotFoundError:
        print(f"Error: Image file '{image_path}' not found.")
        return None
    except Exception as e:
        print(f"Error processing image '{image_path}': {e}")
        return None
# Load and process the door icon
door_icon_normal = process_image("dooricon.png", target_color=(30, 215, 96))  # Replace black with Spotify green
door_icon_inverted = process_image("dooricon.png", invert_black=True)  # Invert black to white

# Debugging: Check if the images were loaded successfully
print(f"door_icon_normal: {door_icon_normal}, door_icon_inverted: {door_icon_inverted}")

if not door_icon_normal or not door_icon_inverted:
    print("Error: Failed to load door icon images. Please ensure 'dooricon.png' exists in the application directory.")
    tk.messagebox.showerror("Error", "Failed to load door icon images. Please ensure 'dooricon.png' exists in the application directory.")
    sys.exit(1)  # Exit the application if the images cannot be loaded

def open_setup_guide():
    print("Opening setup guide...")
    try:
        # Hide the root window while the setup guide is open
        root.withdraw()

        guide_window = tk.Toplevel(root)
        guide_window.title("Setup Guide")
        guide_window.geometry("600x400")

        label = tk.Label(guide_window, text="Follow the video below to create your Spotify Developer App:", font=("Arial", 12))
        label.pack(pady=10)

        # Embed the YouTube video
        video_frame = tk.Label(guide_window, text="YouTube Video Placeholder", bg="black", fg="white", width=70, height=20)
        video_frame.pack(pady=10)

        # Add instructions
        instructions = tk.Label(guide_window, text="After creating your app, enter your Client ID and Client Secret below.", font=("Arial", 10))
        instructions.pack(pady=10)

        # Input fields for Client ID and Client Secret
        client_id_label = tk.Label(guide_window, text="Client ID:")
        client_id_label.pack()
        client_id_entry = tk.Entry(guide_window, width=50)
        client_id_entry.pack()

        client_secret_label = tk.Label(guide_window, text="Client Secret:")
        client_secret_label.pack()
        client_secret_entry = tk.Entry(guide_window, width=50, show="*")  # Hide input for security
        client_secret_entry.pack()

        def save_credentials():
            """Save the entered credentials to credentials.json."""
            client_id = client_id_entry.get().strip()
            client_secret = client_secret_entry.get().strip()

            if not client_id or not client_secret:
                tk.messagebox.showerror("Error", "Both Client ID and Client Secret are required.")
                print("Error: Missing Client ID or Client Secret.")
                return

            # Save the credentials to credentials.json
            credentials = {
                "CLIENT_ID": client_id,
                "CLIENT_SECRET": client_secret,
                "REDIRECT_URI": "http://localhost:5000/callback"
            }
            with open("credentials.json", "w") as file:
                json.dump(credentials, file, indent=4)
                print("Credentials saved successfully.")
                tk.messagebox.showinfo("Success", "Credentials saved successfully. Opening the main application.")
                guide_window.destroy()  # Close the setup guide
                root.deiconify()  # Show the root window again
                open_main_ui()  # Open the main UI after saving credentials

        save_button = tk.Button(guide_window, text="Save Credentials", command=save_credentials)
        save_button.pack(pady=10)

        close_button = tk.Button(guide_window, text="Close", command=lambda: [guide_window.destroy(), root.deiconify()])
        close_button.pack(pady=10)

        print("Setup guide window created successfully.")
    except Exception as e:
        print(f"Error opening setup guide: {e}")

def check_credentials():
    """Check if CLIENT_ID and CLIENT_SECRET are empty in credentials.json."""
    try:
        with open("credentials.json", "r") as file:
            credentials = json.load(file)
            client_id = credentials.get("CLIENT_ID", "")
            client_secret = credentials.get("CLIENT_SECRET", "")

            # If either CLIENT_ID or CLIENT_SECRET is empty, open the setup guide
            if not client_id or not client_secret:
                print("Spotify credentials are missing. Opening setup guide...")
                open_setup_guide()
    except FileNotFoundError:
        print("Error: credentials.json not found. Prompting user for input...")
        prompt_for_credentials()
    except json.JSONDecodeError:
        print("Error: credentials.json is not a valid JSON file. Prompting user for input...")
        prompt_for_credentials()


# Start the backend server
backend_process = subprocess.Popen(["python", "backend.py"], cwd=os.path.dirname(__file__))

# Ensure the backend process is terminated when the app exits
import atexit
@atexit.register
def cleanup():
    backend_process.terminate()

# Backend URL
BACKEND_URL = "http://localhost:5000"
access_token = None  # Global variable to store the access token
token_error_shown = False  # Global flag to prevent multiple error dialogs

# Default shortcuts
shortcuts = {
    "skip": "ctrl+right",
    "previous": "ctrl+left",
    "volume_up": "ctrl+up",
    "volume_down": "ctrl+down"
}

def load_shortcuts():
    """Load shortcuts from the configuration file."""
    global shortcuts
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as file:
                shortcuts = json.load(file)
                print("Shortcuts loaded from config file.")
        else:
            print("Config file not found. Using default shortcuts.")
    except Exception as e:
        print(f"Error loading shortcuts: {e}")

def save_shortcuts():
    """Save shortcuts to the configuration file."""
    try:
        with open(CONFIG_FILE, "w") as file:
            json.dump(shortcuts, file, indent=4)
            print("Shortcuts saved to config file.")
    except Exception as e:
        print(f"Error saving shortcuts: {e}")

# Key codes for media keys
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1

def send_media_key(key_code):
    """Send a media key event using the Windows API."""
    ctypes.windll.user32.keybd_event(key_code, 0, 0, 0)  # Key down
    ctypes.windll.user32.keybd_event(key_code, 0, 2, 0)  # Key up
# Functions for Spotify control
def skip_track(track_label):
    """Simulate the 'Next Track' media key."""
    send_media_key(VK_MEDIA_NEXT_TRACK)
    print("Skipped to the next track.")
    
    # Fetch the current track in a separate thread
    threading.Thread(target=lambda: fetch_current_track(track_label), daemon=True).start()

def previous_track(track_label):
    """Simulate the 'Previous Track' media key."""
    send_media_key(VK_MEDIA_PREV_TRACK)
    print("Went back to the previous track.")
    
    # Fetch the current track in a separate thread
    threading.Thread(target=lambda: fetch_current_track(track_label), daemon=True).start()

def volume_up(volume_slider):
    """Increase the Spotify playback volume."""
    def increase_volume():
        global access_token
        if not access_token:
            print("You must log in first!")
            return
        try:
            # Get the current volume
            response = requests.get(f"https://api.spotify.com/v1/me/player", headers={
                "Authorization": f"Bearer {access_token}"
            })
            if response.status_code != 200:
                print(f"Error fetching current playback: {response.json().get('error', 'Unknown error')}")
                return
            current_volume = response.json().get("device", {}).get("volume_percent", 0)
            new_volume = min(current_volume + 5, 100)  # Increase volume by 5%, max 100%
            # Set the new volume
            response = requests.put(f"https://api.spotify.com/v1/me/player/volume?volume_percent={new_volume}", headers={
                "Authorization": f"Bearer {access_token}"
            })
            if response.status_code == 204:
                print(f"Spotify volume increased to {new_volume}%.")
                volume_slider.set(new_volume)  # Update the slider position
            else:
                print(f"Error setting volume: {response.json().get('error', 'Unknown error')}")
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")

    # Run the volume adjustment in a separate thread
    threading.Thread(target=increase_volume, daemon=True).start()

def volume_down(volume_slider):
    """Decrease the Spotify playback volume."""
    def decrease_volume():
        global access_token
        if not access_token:
            print("You must log in first!")
            return
        try:
            # Get the current volume
            response = requests.get(f"https://api.spotify.com/v1/me/player", headers={
                "Authorization": f"Bearer {access_token}"
            })
            if response.status_code != 200:
                print(f"Error fetching current playback: {response.json().get('error', 'Unknown error')}")
                return
            current_volume = response.json().get("device", {}).get("volume_percent", 0)
            new_volume = max(current_volume - 5, 0)  # Decrease volume by 5%, min 0%
            # Set the new volume
            response = requests.put(f"https://api.spotify.com/v1/me/player/volume?volume_percent={new_volume}", headers={
                "Authorization": f"Bearer {access_token}"
            })
            if response.status_code == 204:
                print(f"Spotify volume decreased to {new_volume}%.")
                volume_slider.set(new_volume)  # Update the slider position
            else:
                print(f"Error setting volume: {response.json().get('error', 'Unknown error')}")
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")

    # Run the volume adjustment in a separate thread
    threading.Thread(target=decrease_volume, daemon=True).start()

# Define the open_main_ui function here
def open_main_ui():
    global btn_login, btn_skip, btn_previous, btn_volume_up, btn_volume_down, door_icon_main_inverted, door_icon_main
    try:
        backend_process = subprocess.Popen(["python", "backend.py"], cwd=os.path.dirname(__file__))
        print("Backend server started successfully.")
    except Exception as e:
        print(f"Error starting backend server: {e}")
        sys.exit(1)
    
    global root  # Reuse the existing root instance
    root.title("Spotify Controller")
    root.geometry("450x300")
    root.resizable(False, False)

    # Set the background color of the root window
    root.configure(bg="#07003a")

    # Create a menu bar
    menu_bar = tk.Menu(root)

    # Add a "Menu" dropdown
    menu = tk.Menu(menu_bar, tearoff=0)
    menu.add_command(label="Change Skip Shortcut", command=lambda: change_shortcut("skip"))
    menu.add_command(label="Change Previous Shortcut", command=lambda: change_shortcut("previous"))
    menu.add_command(label="Change Volume Up Shortcut", command=lambda: change_shortcut("volume_up"))
    menu.add_command(label="Change Volume Down Shortcut", command=lambda: change_shortcut("volume_down"))
    menu_bar.add_cascade(label="Menu", menu=menu)

    # Configure the menu bar
    root.config(menu=menu_bar)

    # Current track label
    track_label = tk.Label(root, text="No track is currently playing.", font=("Arial", 14), fg="white", bg="#07003a")
    track_label.pack(pady=35)

    # Buttons for playback control
    btn_skip = tk.Button(root, text="Skip Track", command=lambda: skip_track(track_label), width=20, bg="#0a004d", fg="white", bd=0)
    btn_skip.pack(pady=5)

    btn_previous = tk.Button(root, text="Previous Track", command=lambda: previous_track(track_label), width=20, bg="#0a004d", fg="white", bd=0)
    btn_previous.pack(pady=5)

    btn_volume_up = tk.Button(root, text="Volume Up", command=lambda: volume_up(volume_slider), width=20, bg="#0a004d", fg="white", bd=0)
    btn_volume_up.pack(pady=5)

    btn_volume_down = tk.Button(root, text="Volume Down", command=lambda: volume_down(volume_slider), width=20, bg="#0a004d", fg="white", bd=0)
    btn_volume_down.pack(pady=5)

    # Reinitialize the door icons
    door_icon_main = process_image("dooricon.png", target_color=(30, 215, 96))  # Replace black with Spotify green
    door_icon_main_inverted = process_image("dooricon.png", invert_black=True)  # Invert black to white

    if not door_icon_main or not door_icon_main_inverted:
        print("Error: Failed to load door icon images. Please ensure 'dooricon.png' exists in the application directory.")
        tk.messagebox.showerror("Error", "Failed to load door icon images. Please ensure 'dooricon.png' exists in the application directory.")
        sys.exit(1)  # Exit the application if the images cannot be loaded

    # Login/Logout button
    btn_login = tk.Button(
        root,
        image=door_icon_main,
        command=lambda: login_to_spotify(btn_login, btn_skip, btn_previous, btn_volume_up, btn_volume_down, track_label, door_icon_main_inverted),
        width=40,
        height=40,
        bd=0,
        bg="#07003a"
    )
    btn_login.place(x=410, y=0)  # Position at the top-right corner

    # Volume slider
    def set_volume(value):
        """Set the Spotify playback volume based on the slider value."""
        global access_token
        if not access_token:
            print("You must log in first!")
            return
        try:
            volume = int(value)  # Convert slider value to integer
            response = requests.put(f"https://api.spotify.com/v1/me/player/volume?volume_percent={volume}", headers={
                "Authorization": f"Bearer {access_token}"
            })
            if response.status_code == 204:
                print(f"Spotify volume set to {volume}%.")
            else:
                print(f"Error setting volume: {response.json().get('error', 'Unknown error')}")
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")

    volume_slider = tk.Scale(
        root,
        from_=0,
        to=100,
        orient="horizontal",
        length=300,
        command=set_volume,
        bg="#07003a",
        fg="white",
        troughcolor="#0a004d",
        highlightthickness=0
    )
    volume_slider.pack(pady=5)

    def fetch_current_volume():
        """Fetch the current Spotify playback volume and update the slider."""
        global access_token
        if not access_token:
            print("You must log in first!")
            return
        try:
            response = requests.get(f"https://api.spotify.com/v1/me/player", headers={
                "Authorization": f"Bearer {access_token}"
            })
            if response.status_code == 200:
                current_volume = response.json().get("device", {}).get("volume_percent", 0)
                volume_slider.set(current_volume)  # Set the slider to the current volume
                print(f"Current Spotify volume: {current_volume}%.")
            else:
                print(f"Error fetching current volume: {response.json().get('error', 'Unknown error')}")
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")

    # Fetch the current volume on startup
    fetch_current_volume()

    # Check token status on startup
    check_token_status(btn_login, btn_skip, btn_previous, btn_volume_up, btn_volume_down, track_label, door_icon_main_inverted, door_icon_main)
    
    # Start periodic track fetching
    periodic_fetch_current_track(track_label)

    # Run the main UI
    root.mainloop()



def change_shortcut(action):
    """Change the shortcut for a specific action by detecting key combinations."""
    def normalize_key(key):
        """Normalize tkinter key names to match keyboard library key names."""
        key_mapping = {
            "Control_L": "ctrl",
            "Control_R": "ctrl",
            "Shift_L": "shift",
            "Shift_R": "shift",
            "Alt_L": "alt",
            "Alt_R": "alt",
            "plus": "+",
            "minus": "-",
            "Return": "enter",
            "space": "space",
        }
        return key_mapping.get(key, key.lower())

    def on_key_press(event):
        """Capture key presses and add them to the keys_pressed set."""
        key = normalize_key(event.keysym)
        if key not in keys_pressed:
            keys_pressed.append(key)
        update_pressed_keys_label()

    def on_key_release(event):
        """Capture key releases but keep the keys displayed."""
        key = normalize_key(event.keysym)
        if key not in keys_pressed:
            keys_pressed.append(key)
        update_pressed_keys_label()

    def update_pressed_keys_label():
        """Update the label to show the currently pressed keys."""
        pressed_keys_text = " + ".join(keys_pressed)
        pressed_keys_label.config(text=f"Pressed Keys: {pressed_keys_text}")

    def confirm_shortcut():
        """Confirm the shortcut and close the dialog."""
        new_shortcut = "+".join(keys_pressed)
        if new_shortcut:
            # Remove the old shortcut
            if action in shortcuts:
                old_shortcut = shortcuts[action]
                keyboard.remove_hotkey(old_shortcut)

            # Add the new shortcut
            shortcuts[action] = new_shortcut
            keyboard.add_hotkey(new_shortcut, actions[action])
            print(f"Shortcut for {action} changed to {new_shortcut}.")
            save_shortcuts()  # Save the updated shortcuts to the config file
        else:
            print("No shortcut was set.")
        dialog.destroy()

    keys_pressed = []  # List to store currently pressed keys
    dialog = tk.Toplevel(root)  # Create a modal dialog
    dialog.title(f"Change Shortcut for {action}")
    dialog.geometry("400x150")
    dialog.grab_set()  # Make the dialog modal
    dialog.focus_force()  # Make the dialog the active window

    label = tk.Label(dialog, text=f"Press the new shortcut for {action}.")
    label.pack(pady=10)

    pressed_keys_label = tk.Label(dialog, text="Pressed Keys: ", font=("Arial", 10))
    pressed_keys_label.pack(pady=5)

    confirm_button = tk.Button(dialog, text="Confirm", command=confirm_shortcut)
    confirm_button.pack(pady=10)

    # Bind key press and release events to the dialog
    dialog.bind("<KeyPress>", on_key_press)
    dialog.bind("<KeyRelease>", on_key_release)

    # Wait for the dialog to close
    dialog.wait_window()

def check_token_status(btn_login, btn_skip, btn_previous, btn_volume_up, btn_volume_down, track_label, door_icon_main_inverted, door_icon_main):
    """Check the token status and refresh it if necessary."""
    global access_token, token_error_shown
    try:
        response = requests.get(f"{BACKEND_URL}/token_status")
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data.get("access_token")  # Update the global access_token
            print("Access token is valid.")
            # Change the button to the logout state
            btn_login.config(image=door_icon_inverted, command=lambda: logout_of_spotify(btn_login, btn_skip, btn_previous, btn_volume_up, btn_volume_down, track_label, door_icon_inverted))
            token_error_shown = False  # Reset the flag when the token is valid
        elif response.status_code == 401:
            print("Access token expired or invalid. Please log in again.")
            if not token_error_shown:  # Show the error dialog only once
                token_error_shown = True
                tk.messagebox.showerror("Error", "Access token expired. Please log in again.")
                btn_login.config(command=lambda: login_to_spotify(btn_login, btn_skip, btn_previous, btn_volume_up, btn_volume_down, track_label, door_icon_main_inverted))
        else:
            print(f"Unexpected error: {response.json().get('error', 'Unknown error')}")
    except Exception as e:
        print(f"Error checking token status: {e}")

def login_to_spotify(btn_login, btn_skip, btn_previous, btn_volume_up, btn_volume_down, track_label, door_icon_inverted):
    """Log in to Spotify and fetch the access token."""
    global token_error_shown
    response = requests.get(f"{BACKEND_URL}/login")
    auth_url = response.json().get("auth_url")
    webbrowser.open(auth_url)
    print("Opened Spotify login page in the browser.")
    
    # Enable playback control buttons
    btn_skip.config(state=tk.NORMAL)
    btn_previous.config(state=tk.NORMAL)
    btn_volume_up.config(state=tk.NORMAL)
    btn_volume_down.config(state=tk.NORMAL)

    # Change the button to the logout state
    btn_login.config(image=door_icon_inverted, command=lambda: logout_of_spotify(btn_login, btn_skip, btn_previous, btn_volume_up, btn_volume_down, track_label, door_icon_inverted))

    fetch_access_token(callback=fetch_current_track(track_label))  # Fetch the access token and then fetch the current track
    check_token_status(btn_login, btn_skip, btn_previous, btn_volume_up, btn_volume_down, track_label, door_icon_main_inverted, door_icon_main)
    token_error_shown = False  # Reset the flag after successful login

def logout_of_spotify(btn_login, btn_skip, btn_previous, btn_volume_up, btn_volume_down, track_label, door_icon_normal):
    """Log out of Spotify by clearing the cached access token and disabling controls."""
    global access_token
    access_token = None  # Clear the access token
    print("Logged out of Spotify. Access token cleared.")
    
    # Update the login button
    btn_login.config(image=door_icon_normal, command=lambda: login_to_spotify(btn_login, btn_skip, btn_previous, btn_volume_up, btn_volume_down, track_label, door_icon_normal))
    
    # Reset the track label
    track_label.config(text="No track is currently playing.")
    
    # Disable playback control buttons
    btn_skip.config(state=tk.DISABLED)
    btn_previous.config(state=tk.DISABLED)
    btn_volume_up.config(state=tk.DISABLED)
    btn_volume_down.config(state=tk.DISABLED)

def fetch_access_token(callback=None):
    """Fetch the access token from the backend and execute a callback if provided."""
    global access_token
    try:
        response = requests.get(f"{BACKEND_URL}/token")
        if response.status_code == 200:
            access_token = response.json().get("access_token")
            print("Access token fetched successfully.")
            if callback:
                callback()  # Execute the callback function (e.g., fetch_current_track)
        else:
            print("Failed to fetch access token.")
    except Exception as e:
        print(f"Error fetching access token: {e}")

def fetch_current_track(track_label):
    """Fetch the currently playing track."""
    global access_token
    if not access_token:
        print("You must log in first!")
        return
    try:
        print("Fetching current track...")
        response = requests.get(f"{BACKEND_URL}/current_track", params={"token": access_token})
        if response.status_code == 401:  # Token expired
            print("Access token expired. Refreshing token...")
            check_token_status(
                btn_login, btn_skip, btn_previous, btn_volume_up, btn_volume_down, track_label, door_icon_main_inverted, door_icon_main
            )
            root.after(0, lambda: fetch_current_track(track_label))  # Retry the request on the main thread
            return
        if response.status_code != 200:
            print(f"Error fetching current track: {response.json().get('error', 'Unknown error')}")
            root.after(0, lambda: track_label.config(text="Error fetching current track."))  # Update UI on the main thread
            return
        current_track = response.json()
        if current_track and current_track.get("item"):
            track_name = current_track["item"]["name"]
            artist_name = current_track["item"]["artists"][0]["name"]
            full_text = f"Now Playing: {artist_name} - {track_name}"
            root.after(0, lambda: track_label.config(text=full_text))  # Update UI on the main thread
        else:
            root.after(0, lambda: track_label.config(text="No track is currently playing."))  # Update UI on the main thread
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        root.after(0, lambda: track_label.config(text="Error fetching current track."))  # Update UI on the main thread

def periodic_fetch_current_track(track_label):
    """Fetch the current track periodically without consuming too many resources."""
    def fetch_in_thread():
        try:
            # Pass all required arguments to fetch_current_track
            fetch_current_track(track_label)
        except Exception as e:
            print(f"Error during periodic fetch: {e}")
    
    # Run the fetch in a separate thread to avoid blocking the UI
    if backend_process.poll() is None:  # Check if the backend process is still running
        if not token_error_shown:  # Stop periodic fetch if token error is shown
            threading.Thread(target=fetch_in_thread, daemon=True).start()
            # Schedule the function to run again after 3 seconds
            root.after(3000, lambda: periodic_fetch_current_track(track_label))
        else:
            print("Token error detected. Stopping periodic fetch.")
    else:
        print("Backend server is not running. Stopping periodic fetch.")

scrolling_job = None  # Global variable to track the current scrolling job
current_scrolling_text = None  # Global variable to track the currently scrolling text

def scroll_track_label(text, label, delay=150):
    """
    Scroll the text in the label from left to right after "Now Playing:" if it's too long.
    """
    global scrolling_job, current_scrolling_text
    static_text = "Now Playing: "  # Static part of the text

    # If the text hasn't changed, do nothing
    if current_scrolling_text == text:
        return

    # Update the current scrolling text
    current_scrolling_text = text

    # Cancel any existing scrolling job
    if scrolling_job is not None:
        label.after_cancel(scrolling_job)
        scrolling_job = None

    # Check if the text is longer than the label width
    if len(text) > 30:
        dynamic_text = text[len(static_text):] + "   "  # Add spacing for smooth scrolling

        def scroll():
            global scrolling_job
            nonlocal dynamic_text
            # Move the first character to the end
            dynamic_text = dynamic_text[1:] + dynamic_text[0]
            # Update the label with the static and scrolling parts
            label.config(text=static_text + dynamic_text[:30])
            # Schedule the next scroll
            scrolling_job = label.after(delay, scroll)

        # Start the scrolling loop
        scroll()
    else:
        # If the text fits, display it as is
        label.config(text=text)

def prompt_for_credentials():
    """Prompt the user to input their Spotify Developer credentials."""
    credentials = {}
    credentials["CLIENT_ID"] = simpledialog.askstring("Spotify Credentials", "Enter your Spotify Client ID:")
    credentials["CLIENT_SECRET"] = simpledialog.askstring("Spotify Credentials", "Enter your Spotify Client Secret:")
    credentials["REDIRECT_URI"] = "http://localhost:5000/callback"  # Default redirect URI

    # Save the credentials to credentials.json
    with open("credentials.json", "w") as file:
        json.dump(credentials, file, indent=4)
        print("Credentials saved to credentials.json.")

    return credentials


# Check if credentials.json exists
if not os.path.exists("credentials.json"):
    print("Spotify credentials not found. Prompting user for input...")
    open_setup_guide()  # This will call open_main_ui() after setup if credentials are saved
else:
    try:
        print("Checking credentials.json...")
        with open("credentials.json", "r") as file:
            credentials = json.load(file)
            client_id = credentials.get("CLIENT_ID", "")
            client_secret = credentials.get("CLIENT_SECRET", "")

            print(f"CLIENT_ID: {client_id}, CLIENT_SECRET: {client_secret}")

            if not client_id or not client_secret:
                print("Spotify credentials are missing. Opening setup guide...")
                open_setup_guide()
            else:
                print("Valid credentials found. Opening main UI...")
                open_main_ui()  # Call directly if credentials are valid
    except (FileNotFoundError, json.JSONDecodeError):
        print("Error reading credentials.json. Prompting user for input...")
        open_setup_guide()

# Map actions to functions
actions = {
    "skip": skip_track,
    "previous": previous_track,
    "volume_up": volume_up,
    "volume_down": volume_down
}

# Load shortcuts from the config file
load_shortcuts()

# Bind shortcuts
for action, shortcut in shortcuts.items():
    keyboard.add_hotkey(shortcut, actions[action])

root.mainloop()