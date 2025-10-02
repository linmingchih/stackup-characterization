import subprocess
import sys
import time
import json


subprocess.run(
    [sys.executable, "model.py"],  # 傳入參數
    capture_output=True, 
    text=True
)

result = subprocess.run(
    [sys.executable, "simulate.py"],  # 傳入參數
    capture_output=True, 
    text=True
)

with open('data/result.json') as f:
    loss = json.load(f)
    print(loss)
