import subprocess
import os
import sys

def main():
    # Define path to venv python
    # Assuming run.py is in the root of the project
    venv_python = os.path.join(os.getcwd(), ".venv", "Scripts", "python.exe")
    
    script_to_run = "characterization_process.py"
    
    if not os.path.exists(venv_python):
        print(f"Error: Virtual environment python not found at {venv_python}")
        return

    if not os.path.exists(script_to_run):
        print(f"Error: Script {script_to_run} not found.")
        return

    print(f"Running {script_to_run} using {venv_python}...")
    
    try:
        subprocess.run([venv_python, script_to_run], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Execution failed with code {e.returncode}")
    except KeyboardInterrupt:
        print("\nExecution interrupted by user.")

if __name__ == "__main__":
    main()
