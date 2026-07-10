import pyautogui
import time
import sys
import os

# Add tui library to path
sys.path.insert(0, os.path.join(os.path.expanduser("~"), ".tui"))
import tui

# Initialize TUI helper
ui = tui.TUIHelper("remote", "v1.0.0", "red", "gliddd4")


import json
import threading
import logging
import subprocess
import warnings
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
from flask import Flask, request, jsonify
from flask_cors import CORS

# Global flag to track if browser is already initialized
BROWSER_INITIALIZED = False
HELIUM_PROCESS = None

pyautogui.FAILSAFE = False

# Suppress Flask startup messages and warnings
warnings.filterwarnings("ignore")
logging.getLogger("werkzeug").setLevel(logging.ERROR)
logging.getLogger("flask.cli").setLevel(logging.ERROR)

# Configuration
PROJECT_DIR = os.path.join(os.path.expanduser("~"), "Remote", "macOS")
CONFIG_FILE = os.path.join(PROJECT_DIR, "buttons.json")

buttons = {}
app = Flask(__name__)
CORS(app)

REQUIRED_BUTTONS = [
    'magnet_menubar',
    'magnet_left_option',
    'search_bar',
    'pop-up_button',
    'pop-up_button_2',
    'full-screen_button',
    'model_picker_button',
    'new_chat_button',
    'text_input_box'
]

OPTIONAL_BUTTONS = [
]

# Default browser paths for different platforms
DEFAULT_BROWSERS = {
    'chrome': '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    'chromium': '/Applications/Chromium.app/Contents/MacOS/Chromium',
    'helium': '/Applications/Helium.app/Contents/MacOS/Helium',
}

def ensure_directories():
    os.makedirs(PROJECT_DIR, exist_ok=True)

def load_config():
    global buttons
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                buttons = json.load(f)
        except Exception:
            buttons = {}
    
    # Set default browser to Chrome if not configured
    if 'browser_path' not in buttons:
        buttons['browser_path'] = DEFAULT_BROWSERS['chrome']
        save_config()

def save_config():
    with open(CONFIG_FILE, 'w') as f:
        json.dump(buttons, f, indent=4)

def _convert_menu_lines_to_blocks(menu_lines):
    """Convert old menu_lines format to new blocks format"""
    information = []
    menu = []
    select_ui = None
    
    current_section = 'information'
    for line in menu_lines:
        if isinstance(line, tuple) and line[0] == "SELECT_PROMPT":
            select_ui = line
        elif isinstance(line, str) and line.strip() == "Menu:":
            current_section = 'menu'
            menu.append(line)
        elif current_section == 'information':
            if line != "":  # Skip empty lines in information
                information.append(line)
        elif current_section == 'menu':
            if line != "":  # Skip empty lines in menu
                menu.append(line)
    
    return {
        'information': information,
        'menu': menu,
        'select_ui': select_ui
    }


def show_curses_submenu(menu_lines=None, valid_keys=None, input_mode=False, menu_items=None, blocks=None, display_only=False, auto_timeout=0, quit_presses=2):
    """Show a submenu using tui library - wrapper for compatibility"""
    # Support both old menu_lines and new blocks system
    if blocks is None and menu_lines is not None:
        # Legacy mode - convert menu_lines to blocks
        blocks = _convert_menu_lines_to_blocks(menu_lines)
    
    if valid_keys is None:
        valid_keys = ['q', 'a'] + [str(i) for i in range(1, 10)]
    
    # Add menu_items and valid_keys to blocks
    if blocks is not None:
        blocks['menu_items'] = menu_items or []
        blocks['valid_keys'] = valid_keys
    
    # Auto-detect display_only mode: if valid_keys is empty list, use display_only
    if valid_keys == []:
        display_only = True
    
    # Use tui library
    window = tui.Window("remote", "v1.0.0", "red", "gliddd4")
    return window.show(blocks, input_mode=input_mode, display_only=display_only, auto_timeout=auto_timeout, quit_presses=quit_presses)


def record_button():
    """Auto-cycle through required buttons and record their positions"""
    
    while True:  # Loop to keep showing menu after recording
        ai_url = buttons.get('ai_website_url', 'https://chat.leadscloud.org/#/chat')
        missing = [btn for btn in REQUIRED_BUTTONS if btn not in buttons]
        
        # Build information
        information = []
        if missing:
            missing_str = ', '.join(missing)
            information.append(f"Missing: {missing_str}")
        
        # Build menu items
        menu_items = []
        all_buttons = REQUIRED_BUTTONS + OPTIONAL_BUTTONS
        
        # Show all buttons
        for i, btn in enumerate(all_buttons, 1):
            # Mark first two buttons (magnet buttons) as optional
            if i <= 2:
                line = f"[{i}] {btn} (optional)"
            elif btn in OPTIONAL_BUTTONS and btn not in buttons:
                line = f"[{i}] {btn} (optional)"
            else:
                line = f"[{i}] {btn}"
            menu_items.append((line, str(i)))
        
        if missing:
            menu_items.append(("[a] Record all missing", 'a'))
        
        select_prompt = "❯  Select an option:" if not missing else "❯  Select an option to re-record:"
        
        # Show menu using TUI helper
        choice = ui.show_menu(
            information=information,
            menu_items=menu_items,
            prompt=select_prompt,
            menu_title="Record Menu:"
        )
        
        if choice == 'q':
            return  # Exit the loop and return to main menu
        
        buttons_to_record = []
        
        if choice == 'a':
            if not missing:
                ui.show_error("All required buttons are already configured!")
                continue  # Go back to menu
            buttons_to_record = missing

        elif choice.isdigit() and 1 <= int(choice) <= len(all_buttons):
            btn_index = int(choice) - 1
            buttons_to_record = [all_buttons[btn_index]]
        else:
            ui.show_error("Invalid choice!")
            continue  # Go back to menu

        
        # Show recording instructions with menu
        instructions_menu_items = [
            ("[y] Start recording", 'y'),
            ("[n] Go back", 'n'),
        ]
        
        recording_choice = ui.show_menu(
            information=[
                "Position your mouse over the button's location",
                "You'll have 3 seconds before it records the button position"
            ],
            menu_items=instructions_menu_items,
            menu_title="Record Menu:"
        )
        
        if recording_choice == 'n':
            continue  # Go back to record button menu

        
        for btn in buttons_to_record:
            btn_num = all_buttons.index(btn) + 1
            
            # Show countdown
            ui.show_countdown(
                title=f"[{btn_num}/{len(all_buttons)}] Recording: {btn}",
                seconds=3,
                extra_info=["Do not touch the mouse!"]
            )
            
            x, y = pyautogui.position()
            buttons[btn] = {"x": x, "y": y}
            save_config()
            
            # Show capture confirmation
            ui.show_info([
                f"Captured {btn} at ({x}, {y})",
                "",
                f"Progress: {btn_num}/{len(all_buttons)}",
            ], timeout=0.8)




def click_btn(name):
    if name in buttons:
        pyautogui.click(buttons[name]['x'], buttons[name]['y'])
    else:
        raise Exception(f"Button '{name}' not found!")

def wait_for_response_completion():
    """Wait for AI response using browser automation (Selenium) and return the response text"""
    if not SELENIUM_AVAILABLE:
        time.sleep(buttons.get("response_wait_time", 10))
        return None
    
    try:
        # Connect to already-running Helium browser via remote debugging
        chrome_options = Options()
        chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
        driver = webdriver.Chrome(options=chrome_options)
        
        max_wait = buttons.get("max_response_wait", 120)
        last_text_length = 0
        stable_count = 0
        start_time = time.time()
        final_text = ""
        
        while time.time() - start_time < max_wait:
            try:
                # Find all message elements in the chat
                messages = driver.find_elements(By.CSS_SELECTOR, "div.markdown-body, div[class*=\"Markdown\"], div[class*=\"markdown\"], div[class*=\"message-content\"], div[class*=\"MessageContent\"]")
                
                if messages:
                    current_text = messages[-1].text
                    current_length = len(current_text)
                    
                    # If text length hasn't changed for 2 seconds, response is complete
                    if current_length == last_text_length and current_length > 0:
                        stable_count += 1
                        if stable_count >= 4:  # 4 checks x 0.5s = 2 seconds stable
                            final_text = current_text
                            driver.quit()
                            return final_text
                    else:
                        stable_count = 0
                        last_text_length = current_length
                
                time.sleep(0.5)
                
            except Exception:
                time.sleep(0.5)
        
        driver.quit()
        return None
        
    except Exception:
        time.sleep(buttons.get("response_wait_time", 10))
        return None

def automate_ai_chat(prompt, image_path=None, new_chat=True, anonymous=False):
    """Main automation function"""
    global BROWSER_INITIALIZED
    
    if anonymous:
        new_chat = True

    # Validate browser path
    browser_path = buttons.get('browser_path', DEFAULT_BROWSERS['chrome'])
    if not os.path.exists(browser_path):
        return {"error": f"Browser not found at {browser_path}"}
    

    missing = [b for b in REQUIRED_BUTTONS if b not in buttons]
    if missing:
        return {"error": f"Missing required button coordinates: {', '.join(missing)}"}
    
    try:
        # Only navigate to URL if browser not initialized yet
        if not BROWSER_INITIALIZED:
            print("[r] First time browser setup detected")
            
            # Check if browser is running with debug port, if not launch it
            if not is_browser_running_with_debug():
                print("[r] Launching browser")
                if not launch_browser_with_debugging():
                    return {"error": "Failed to launch browser"}
            
            # Arrange Helium window using Magnet
            print("[r] Arranging window")
            time.sleep(1)
            
            if "magnet_menubar" in buttons and "magnet_left_option" in buttons:
                click_btn("magnet_menubar")
                time.sleep(0.5)
                click_btn("magnet_left_option")
                time.sleep(0.5)
            
            # Navigate to URL
            ai_url = buttons.get("ai_website_url", "https://chat.leadscloud.org/#/chat")
            print(f"[r] Navigating to provider")
            click_btn("search_bar")
            time.sleep(0.5)
            pyautogui.write(ai_url)
            pyautogui.press("enter")
            time.sleep(3)
            
            # Click pop-up buttons
            print("[r] Closing popups")
            click_btn("pop-up_button")
            time.sleep(0.5)
            click_btn("pop-up_button_2")
            time.sleep(0.5)
            
            # Full screen
            print("[r] Enabling fullscreen")
            click_btn("full-screen_button")
            time.sleep(0.5)
            
            BROWSER_INITIALIZED = True
        
        if new_chat:
            print("[r] Starting new chat")
            click_btn("new_chat_button")
            time.sleep(2)
        
        print("[r] Sending prompt")
        click_btn("text_input_box")
        time.sleep(1.5)
        
        if image_path and os.path.exists(image_path):
            os.system(f"osascript -e 'set the clipboard to (read (POSIX file \"{image_path}\") as «class PNGf»)'")
            time.sleep(0.5)
            pyautogui.hotkey("command", "v")
            time.sleep(1)
        else:
            # Copy prompt to clipboard
            escaped_prompt = prompt.replace("'", "'\\''")
            os.system(f"printf '%s' '{escaped_prompt}' | pbcopy")
            time.sleep(0.5)
            # Paste into text box
            pyautogui.hotkey("command", "v")
            time.sleep(1)
        
        pyautogui.press("enter")
        time.sleep(2)
        
        print("[r] Waiting for response")
        # Get response text directly from Selenium
        response_text = wait_for_response_completion()
        
        if response_text is None:
            response_text = "Error: Could not retrieve response from browser"
        
        print(f"[r] Response received ({len(response_text)} chars)")
        
        return {
            "success": True,
            "prompt": prompt if not image_path else f"[Image: {image_path}]",
            "response": response_text
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def status():
    missing = [b for b in REQUIRED_BUTTONS if b not in buttons]
    return jsonify({
        "status": "online",
        "configured": len(missing) == 0,
        "missing_buttons": missing,
        "buttons": buttons
    })

@app.route('/send', methods=['POST'])
def send_prompt():
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "Missing request data"}), 400
    
    prompt = data.get('prompt', '')
    image_path = data.get('image_path')
    new_chat = data.get('new_chat', True)
    
    anonymous = data.get("anonymous", False)
    if not prompt and not image_path:
        return jsonify({"error": "Missing 'prompt' or 'image_path' in request"}), 400
    
    print(f"\n[API] Received request: {prompt[:50] if prompt else f'Image: {image_path}'}...")
    
    result = automate_ai_chat(prompt, image_path, new_chat)
    
    return jsonify(result)

@app.route('/config', methods=['GET'])
def get_config():
    return jsonify({
        "buttons": buttons,
        "required": REQUIRED_BUTTONS
    })

@app.route('/config/wait-time', methods=['POST'])
def set_wait_time():
    data = request.get_json()
    if 'seconds' in data:
        buttons['max_response_wait'] = int(data['seconds'])
        save_config()
        return jsonify({"success": True, "max_wait_time": buttons['max_response_wait']})
    return jsonify({"error": "Missing 'seconds' parameter"}), 400

@app.route('/config/ai-url', methods=['POST'])
def set_ai_url():
    data = request.get_json()
    if 'url' in data:
        buttons['ai_website_url'] = data['url']
        save_config()
        return jsonify({"success": True, "ai_url": buttons['ai_website_url']})
    return jsonify({"error": "Missing 'url' parameter"}), 400

@app.route('/shutdown', methods=['POST'])
def shutdown_server():
    """Shutdown endpoint to stop the server gracefully"""
    print("\n[SERVER] Shutdown request received...")
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        # For production servers, we can't shutdown this way
        # Just return success and the monitor will handle it
        return jsonify({"success": True, "message": "Shutdown initiated"})
    func()
    return jsonify({"success": True, "message": "Server shutting down..."})

def switch_model(model_name):
    """Switch to a different AI model using Selenium"""
    if not SELENIUM_AVAILABLE:
        return {"error": "Selenium not installed"}
    
    if 'model_picker_button' not in buttons:
        return {"error": "Model picker button not configured"}
    
    try:
        # Bring browser to front first
        browser_name = os.path.basename(buttons.get("browser_path", DEFAULT_BROWSERS["chrome"])).replace(" ", "")
        print(f"[MODEL SWITCH] Bringing {browser_name} to front...")
        os.system(f"osascript -e 'tell application \"{browser_name}\" to activate'")
        time.sleep(0.5)
        
        # Click the model picker button
        print(f"[MODEL SWITCH] Opening model picker...")
        click_btn('model_picker_button')
        time.sleep(1)  # Wait for popup to open
        
        # Connect to browser
        chrome_options = Options()
        chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
        driver = webdriver.Chrome(options=chrome_options)
        
        print(f"[MODEL SWITCH] Searching for model: {model_name}")
        
        # Find all clickable elements in the popup (buttons, divs with click handlers, etc.)
        # Look for text that matches the model name
        possible_selectors = [
            f"//button[contains(text(), '{model_name}')]",
            f"//div[contains(text(), '{model_name}')]",
            f"//span[contains(text(), '{model_name}')]",
            f"//li[contains(text(), '{model_name}')]",
            f"//*[contains(text(), '{model_name}')]",
        ]
        
        model_found = False
        for selector in possible_selectors:
            try:
                elements = driver.find_elements(By.XPATH, selector)
                if elements:
                    # Click the first matching element
                    elements[0].click()
                    print(f"[MODEL SWITCH] Clicked on: {model_name}")
                    model_found = True
                    break
            except:
                continue
        
        driver.quit()
        
        if model_found:
            time.sleep(0.5)  # Wait for selection to register
            return {"success": True, "model": model_name}
        else:
            return {"error": f"Model '{model_name}' not found in picker"}
            
    except Exception as e:
        return {"error": str(e)}

@app.route('/switch-model', methods=['POST'])
def api_switch_model():
    """API endpoint to switch AI model"""
    data = request.get_json()
    
    if not data or 'model' not in data:
        return jsonify({"error": "Missing 'model' parameter"}), 400
    
    model_name = data['model']
    print(f"\n[API] Received model switch request: {model_name}")
    
    result = switch_model(model_name)
    return jsonify(result)

def launch_browser_with_debugging():
    """Launch configured browser with remote debugging port"""
    global HELIUM_PROCESS
    
    browser_path = buttons.get('browser_path', DEFAULT_BROWSERS['chrome'])
    
    if not os.path.exists(browser_path):
        print(f"[ERROR] Browser not found at: {browser_path}")
        return False
    
    try:
        # Launch browser with debugging port in background
        HELIUM_PROCESS = subprocess.Popen(
            [browser_path, '--remote-debugging-port=9222'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(3)  # Give browser time to start
        return True
    except Exception as e:
        print(f"[ERROR] Failed to launch browser: {e}")
        print(f"[ERROR] Tried to launch: {browser_path}")
        print(f"[INFO] Change browser with menu option [b]")
        return False

def is_browser_running_with_debug():
    """Check if browser is already running with debug port"""
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', 9222))
        sock.close()
        return result == 0
    except:
        return False

def monitor_browser_and_shutdown():
    """Monitor browser process and shutdown server if it closes"""
    global HELIUM_PROCESS
    
    # Only monitor if we launched the browser ourselves
    if not HELIUM_PROCESS:
        return  # Don't monitor if user is managing browser manually
    
    while True:
        time.sleep(5)  # Check every 5 seconds
        
        # Check if our launched browser process is still running
        if HELIUM_PROCESS.poll() is not None:
            print("\n[MONITOR] Browser closed - stopping server and returning to menu...")
            time.sleep(1)
            # Trigger server shutdown by making a request to a shutdown endpoint
            import requests
            try:
                requests.post('http://127.0.0.1:8080/shutdown', timeout=1)
            except:
                pass
            return

def get_network_ip():
    """Get the network IP address"""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"


def run_server():
    global HELIUM_PROCESS, BROWSER_INITIALIZED
    
    # Step 1: Show initial menu asking if user wants to set up browser
    setup_menu_items = [
        ("[y] Yes - setup and start server", 'y'),
        ("[n] No - start server only", 'n'),
    ]
    
    setup_choice = ui.show_menu(
        information=["Start server with browser setup?"],
        menu_items=setup_menu_items,
        menu_title="Server Menu:"
    )
    
    if setup_choice == 'q':
        return
    
    do_browser_setup = (setup_choice == 'y')

    
    # Step 2: Start logs in a separate thread while showing UI
    log_lines = []
    log_lock = threading.Lock()
    server_ready = threading.Event()
    server_error = threading.Event()
    server_running = True  # Flag to control server loop
    
    def add_log(msg):
        with log_lock:
            log_lines.append(msg)  # Remove [r] prefix

    
    def server_setup_thread():
        """Run server setup in background thread"""
        global BROWSER_INITIALIZED
        
        try:
            # Close any existing browser instances first
            browser_path = buttons.get("browser_path", DEFAULT_BROWSERS["chrome"])
            browser_name = os.path.basename(browser_path).replace(" ", "")
            
            add_log("Starting server")
            add_log("Checking if browser is open")
            
            # Kill any existing browser processes
            try:
                result = os.system(f"pgrep -f {browser_name} >/dev/null 2>&1")
                if result == 0:  # Browser is running
                    os.system(f"pkill -f {browser_name} 2>/dev/null")
                    time.sleep(1)
                    add_log("Closed browser")
            except:
                pass
            
            # Launch browser with debugging port
            add_log("Opening browser")
            if not launch_browser_with_debugging():
                add_log("ERROR: Failed to launch browser")
                server_error.set()
                return
            
            add_log("Browser is ready")
            
            if do_browser_setup:
                # Bring browser to front using AppleScript
                browser_name = os.path.basename(buttons.get("browser_path", DEFAULT_BROWSERS["chrome"])).replace(" ", "")
                add_log("Bringing browser to front")
                os.system(f"osascript -e 'tell application \"{browser_name}\" to activate'")
                time.sleep(1)
                
                ai_url = buttons.get("ai_website_url", "https://chat.leadscloud.org/#/chat")
                
                # Wait before Magnet
                add_log("Moving window")
                time.sleep(1)
                
                # Click Magnet buttons
                if "magnet_menubar" in buttons and "magnet_left_option" in buttons:
                    click_btn("magnet_menubar")
                    time.sleep(0.5)
                    click_btn("magnet_left_option")
                    time.sleep(0.5)
                
                # Navigate to URL
                add_log("Opening provider")
                click_btn("search_bar")
                time.sleep(0.5)
                pyautogui.write(ai_url)
                pyautogui.press("enter")
                time.sleep(3)
                
                # Click pop-up buttons
                add_log("Closing popups")
                click_btn("pop-up_button")
                time.sleep(0.5)
                click_btn("pop-up_button_2")
                time.sleep(0.5)
                
                # Click full-screen button
                add_log("Opening fullscreen")
                click_btn("full-screen_button")
                time.sleep(0.5)
                
                BROWSER_INITIALIZED = True
            
            network_ip = get_network_ip()
            
            # Add final logs
            add_log("Ctrl+C to stop server")  # Changed from ^C

            add_log(f"Running on http://{network_ip}:8080")
            add_log("Browser will close on shutdown")
            
            server_ready.set()
            
        except Exception as e:
            add_log(f"ERROR: {e}")
            server_error.set()
    
    # Start setup thread
    setup_thread = threading.Thread(target=server_setup_thread, daemon=True)
    setup_thread.start()
    
    # Step 3: Show live logs using tui library
    import curses
    
    def show_live_logs_tui(stdscr):
        nonlocal server_running  # Access parent scope variable
        
        curses.use_default_colors()
        curses.curs_set(0)
        
        curses.start_color()
        curses.init_pair(11, 241, -1)
        curses.init_pair(12, 179, -1)
        curses.init_pair(13, 15, -1)
        curses.init_pair(14, 196, -1)

        banner = tui.Banner("remote", "v1.0.0", short=True)
        select_ui = tui.SelectUI(prompt="❯  Server running (Ctrl+C to stop)")

        last_size = (0, 0)
        needs_redraw = True
        while server_running and not server_error.is_set():
            current_size = stdscr.getmaxyx()

            if select_ui.gradient.update():
                needs_redraw = True

            if current_size != last_size:
                needs_redraw = True
                last_size = current_size

            if needs_redraw:
                height, width = stdscr.getmaxyx()
                stdscr.erase()

                y = banner.draw(stdscr, 0)
                y += 1

                try:
                    stdscr.addstr(y, 0, "Logs:", curses.A_BOLD)
                    y += 1
                except:
                    pass

                with log_lock:
                    current_logs = list(log_lines)

                for i, log_line in enumerate(current_logs):
                    if y + i < height - 4:
                        try:
                            if "ERROR" in log_line:
                                stdscr.addstr(y + i, 0, log_line, curses.color_pair(14))
                            else:
                                stdscr.addstr(y + i, 0, log_line, curses.color_pair(13))
                        except:
                            pass

                select_ui.draw(stdscr, show_help_mode=False)

                stdscr.refresh()
                needs_redraw = False

            stdscr.timeout(50)
            try:
                key = stdscr.getch()
                if key == 3:
                    server_running = False
                    break
            except:
                pass

            time.sleep(0.05)


        
        # If error occurred, wait for user input
        if server_error.is_set():
            with log_lock:
                log_lines.append("")
                log_lines.append("Returning to menu in 3 seconds...")
            
            # Redraw with error message
            stdscr.erase()
            y = banner.draw(stdscr, 0)
            
            separator = "─" * width
            if y < height:
                try:
                    stdscr.addstr(y, 0, separator, curses.color_pair(11))
                except:
                    pass
                y += 1
            
            with log_lock:
                current_logs = list(log_lines)
            
            for i, log_line in enumerate(current_logs):
                if y + i < height - 1:
                    try:
                        if "ERROR" in log_line:
                            stdscr.addstr(y + i, 0, log_line, curses.color_pair(14))
                        else:
                            stdscr.addstr(y + i, 0, log_line, curses.color_pair(13))
                    except:
                        pass
            
            stdscr.refresh()
            time.sleep(3)
            return
    
    curses.wrapper(show_live_logs_tui)
    
    # If error occurred, return to menu
    if server_error.is_set():
        return
    
    # Step 4: Start browser monitor thread
    monitor_thread = threading.Thread(target=monitor_browser_and_shutdown, daemon=True)
    monitor_thread.start()
    
    # Step 5: Start Flask server in background thread
    def run_flask():
        try:
            # Suppress Flask startup banner
            import click
            click.echo = lambda *args, **kwargs: None
            
            app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False, threaded=True)
        except:
            pass
    
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Wait for Flask to start
    time.sleep(1)
    
    # Show UI again with server running status (blocks until Ctrl+C in curses)
    curses.wrapper(show_live_logs_tui)
    
    # Cleanup browser on exit
    global BROWSER_INITIALIZED
    if HELIUM_PROCESS:
        HELIUM_PROCESS.terminate()
        try:
            HELIUM_PROCESS.wait(timeout=2)
        except:
            HELIUM_PROCESS.kill()
    BROWSER_INITIALIZED = False



def test_workflow():
    missing = [b for b in REQUIRED_BUTTONS if b not in buttons]
    
    # Check if we can run test
    if missing:
        ui.show_error([
            f"Missing: {', '.join(missing)}",
            "",
            "Cannot run test. Please record missing buttons first."
        ], timeout=3)
        return

    
    # Show menu
    test_menu_items = [
        ("[1] Test with text prompt", '1'),
        ("[2] Test with image", '2'),
    ]
    
    choice = ui.show_menu(
        information=[],
        menu_items=test_menu_items,
        menu_title="Test Workflow Menu:"
    )
    
    if choice == 'q':
        return
    
    if choice not in ["1", "2"]:
        return
    
    # Get input - confirm if user wants new chat
    new_chat_input = ui.show_confirmation("Start new chat?", default='y')
    new_chat = new_chat_input.lower() != 'n' if new_chat_input else True

    
    if choice == "1":
        test_prompt = ui.show_input(
            prompt="Prompt:",
            information=["Enter test prompt:"],
            menu_title="Test Workflow Menu:"
        )
        if not test_prompt:
            test_prompt = "Hello, how are you?"
        
        # Show countdown
        ui.show_countdown(
            title="Starting test workflow",
            seconds=3,
            extra_info=["Do not touch the mouse!"]
        )
        
        result = automate_ai_chat(test_prompt, None, new_chat)
    elif choice == "2":
        image_path = ui.show_input(
            prompt="Path:",
            information=["Enter image path:"],
            menu_title="Test Workflow Menu:"
        )
        
        # Show countdown
        ui.show_countdown(
            title="Starting test workflow",
            seconds=3,
            extra_info=["Do not touch the mouse!"]
        )
        
        result = automate_ai_chat("", image_path, new_chat)
    
    # Show result
    ui.show_info([
        "",
        "="*50,
        "Test Result:",
        "="*50,
        str(result),
        "="*50
    ], timeout=5)



def show_curses_menu(config_dir, ai_url, buttons_status):
    """Show the main menu using TUI helper"""
    menu_items = [
        ("[r] Record button", 'r'),
        ("[t] Test workflow", 't'),
        ("[w] Reply wait time", 'w'),
        ("[p] Provider", 'p'),
        ("[b] Browser", 'b'),
        ("[s] Start server", 's'),
    ]
    
    information = [
        f"Config: {config_dir}",
        f"Site: {ai_url.replace('https://', '').replace('http://', '')}",
        buttons_status,
    ]
    
    # Use TUI helper with 3 quit presses for main menu
    return ui.show_menu(
        information=information,
        menu_items=menu_items,
        menu_title="Menu:",
        quit_presses=3
    )


def main():
    ensure_directories()
    load_config()
    
    while True:
        # Get button status
        required_configured = sum(1 for btn in REQUIRED_BUTTONS if btn in buttons)
        missing = [btn for btn in REQUIRED_BUTTONS if btn not in buttons]
        buttons_str = f"Buttons: {required_configured}/{len(REQUIRED_BUTTONS)}"
        if missing:
            buttons_str += f"\nMissing: {', '.join(missing)}"
        
        ai_url = buttons.get("ai_website_url", "https://chat.leadscloud.org/#/chat")
        
        # Show menu using tui
        choice = show_curses_menu(PROJECT_DIR, ai_url, buttons_str)
        
        if choice == 'r':
            record_button()
        elif choice == 't':
            test_workflow()
        elif choice == 'w':
            current_wait = buttons.get('max_response_wait', 30)

            current_wait = buttons.get('max_response_wait', 30)
            
            seconds_input = ui.show_input(
                prompt="Seconds:",
                information=[f"Current max wait time: {current_wait} seconds"],
                menu_title="Wait Time Menu:"
            )
            
            if seconds_input and seconds_input != 'q':
                try:
                    seconds = int(seconds_input)
                    buttons['max_response_wait'] = seconds
                    save_config()
                except ValueError:
                    ui.show_error("Invalid input. Please enter a number.")

        elif choice == 'p':  # Provider
            current_url = buttons.get('ai_website_url', 'https://chat.leadscloud.org/#/chat')
            
            url_menu_items = [
                ("[1] Change URL", '1'),
            ]
            
            url_choice = ui.show_menu(
                information=[f"Current AI website: {current_url}"],
                menu_items=url_menu_items,
                menu_title="Provider Menu:"
            )
            
            if url_choice == '1':
                url = ui.show_input(
                    prompt="URL:",
                    information=[],
                    menu_title="Provider Menu:"
                )
                
                if url:
                    buttons['ai_website_url'] = url
                    save_config()

        elif choice == 'b':
            current_browser = buttons.get('browser_path', DEFAULT_BROWSERS['chrome'])
            browser_name = os.path.basename(current_browser)
            
            browser_menu_items = [
                ("[1] Chrome (default)", '1'),
                ("[2] Chromium", '2'),
                ("[3] Helium", '3'),
                ("[4] Custom path", '4'),
            ]
            
            browser_choice = ui.show_menu(
                information=[
                    f"Current browser: {browser_name}",
                    f"Path: {current_browser}",
                ],
                menu_items=browser_menu_items,
                menu_title="Browser Menu:"
            )
            
            if browser_choice == "1":
                buttons['browser_path'] = DEFAULT_BROWSERS['chrome']
                save_config()
            elif browser_choice == "2":
                buttons['browser_path'] = DEFAULT_BROWSERS['chromium']
                save_config()
            elif browser_choice == "3":
                buttons['browser_path'] = DEFAULT_BROWSERS['helium']
                save_config()
            elif browser_choice == "4":
                custom_path = ui.show_input(
                    prompt="Path:",
                    information=["Enter full path to Chrome-based browser:"],
                    menu_title="Browser Menu:"
                )
                
                if custom_path and os.path.exists(custom_path):
                    buttons['browser_path'] = custom_path
                    save_config()
                elif custom_path:
                    ui.show_error("Invalid path!")

        elif choice == 's':
            missing = [b for b in REQUIRED_BUTTONS if b not in buttons]
            if missing:
                # Show warning
                warning_menu_items = [
                    ("[y] Continue anyway", 'y'),
                    ("[n] Cancel", 'n'),
                ]
                
                confirm = ui.show_menu(
                    information=[
                        f"WARNING: Missing required button coordinates:",
                        f"{', '.join(missing)}",
                        "",
                        "Server will start but API calls will fail until configured.",
                    ],
                    menu_items=warning_menu_items,
                    menu_title="Server Menu:"
                )
                if confirm != 'y':
                    continue
            
            missing_optional = [b for b in OPTIONAL_BUTTONS if b not in buttons]
            if missing_optional:
                # Show info
                ui.show_info([
                    f"INFO: Optional features not configured:",
                    f"{','.join(missing_optional)}",
                    "",
                    "Window management features will be disabled."
                ], timeout=3)
            
            run_server()

        elif choice == 'q':
            # Show goodbye message (main menu = 1 second)
            ui.show_goodbye(is_main_menu=True)
            
            # Clean up browser process if it's running
            global BROWSER_INITIALIZED
            if HELIUM_PROCESS:
                HELIUM_PROCESS.terminate()
                try:
                    HELIUM_PROCESS.wait(timeout=2)
                except:
                    HELIUM_PROCESS.kill()
            break

if __name__ == "__main__":
    main()