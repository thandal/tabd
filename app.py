import subprocess
import os
import sys

PORT = "8888"

def run_proxy():
    print("Starting 'Through a Browser, Darkly' Proxy...")
    print(f"Port: {PORT}")
    
    # Path to the mitmdump executable in the venv
    mitm_path = os.path.join(os.path.dirname(__file__), "python_env", "bin", "mitmdump")
    
    # Addon script
    addon_path = os.path.join(os.path.dirname(__file__), "darkly_addon.py")
    
    try:
        # Run mitmdump with our addon and specify the port
        subprocess.run([mitm_path, "-s", addon_path, "-p", PORT], check=True)
    except KeyboardInterrupt:
        print("\nProxy stopped.")
    except Exception as e:
        print(f"Error starting proxy: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_proxy()
