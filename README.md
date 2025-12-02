# Stackup Characterization Tool

[**繁體中文**](README_zh-TW.md)

**Automated stackup characterization tool using ANSYS HFSS 3D Layout.**

This tool provides a user-friendly GUI to characterize and optimize PCB stackup parameters (such as dielectric constant, loss tangent, roughness, etc.) by interfacing with ANSYS Electronics Desktop (AEDT).

## Features

*   **User-Friendly GUI**: Built with `pywebview` for a modern, responsive interface.
*   **Automated Optimization**: Iteratively optimizes stackup parameters to match target impedance and loss.
*   **Ansys Integration**: Seamlessly uses `pyaedt` and `pyedb` to drive HFSS 3D Layout simulations.
*   **Real-time Feedback**: View optimization progress and statistics directly in the application.
*   **Easy Deployment**: Self-contained execution via `uv`.

## Prerequisites

1.  **ANSYS Electronics Desktop (AEDT)**: You must have a valid installation and license of Ansys Electronics Desktop (2022 R2 or later recommended).
2.  **Windows OS**: This tool is designed for Windows.

## Installation & Usage

This project uses `uv` for dependency management, which is handled automatically.

1.  **Clone or Download** this repository.
2.  **Double-click `run.bat`**.
    *   The script will automatically check for `uv` and install it if missing.
    *   It will ensure the correct Python version (3.10) is installed.
    *   It will sync all necessary dependencies.
    *   Finally, it will launch the GUI application.

> **Note**: The first run may take a few minutes to download Python and dependencies. Subsequent runs will be instant.

## How to Use

1.  Launch the application using `run.bat`.
2.  Click **"Select Stackup File"** to load your stackup configuration (JSON format).
3.  Enter the **Max Iterations** (e.g., 10) for the optimization loop.
4.  Click **"Start Optimization"**.
5.  Monitor the logs and statistics in the dashboard.
6.  Upon completion, the characterized stackup and AEDB models will be saved in a timestamped output directory.
