import sys
import os
import subprocess

def run():
    print("Running pytest tests/ ...")
    venv_python = os.path.join(".venv2", "Scripts", "python.exe")
    if not os.path.exists(venv_python):
        venv_python = sys.executable # fallback
        
    pytest_cmd = [venv_python, "-m", "pytest", "tests/"]
    print(f"Command: {' '.join(pytest_cmd)}")
    res_pytest = subprocess.run(pytest_cmd, capture_output=True, text=True)
    
    # Save the output to a file
    with open("test_results.log", "w", encoding="utf-8") as f:
        f.write("=== PYTEST OUTPUT ===\n")
        f.write(f"STDOUT:\n{res_pytest.stdout}\n")
        f.write(f"STDERR:\n{res_pytest.stderr}\n")
        f.write(f"RETURN CODE: {res_pytest.returncode}\n\n")
        
    print("Test run completed. Output written to test_results.log")

if __name__ == "__main__":
    run()
