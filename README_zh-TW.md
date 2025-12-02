# 堆疊特性分析工具 (Stackup Characterization Tool)

**使用 ANSYS HFSS 3D Layout 的自動化堆疊特性分析工具。**

本工具提供了一個友善的圖形使用者介面 (GUI)，透過與 ANSYS Electronics Desktop (AEDT) 的介接，來分析並最佳化 PCB 堆疊參數（如介電常數 Dk、損耗因子 Df、銅箔粗糙度等）。

## 功能特色

*   **友善的 GUI 介面**：使用 `pywebview` 構建，提供現代化且反應靈敏的操作介面。
*   **自動化最佳化**：迭代最佳化堆疊參數，以符合目標阻抗 (Impedance) 和損耗 (Loss)。
*   **Ansys 整合**：無縫整合 `pyaedt` 和 `pyedb` 以驅動 HFSS 3D Layout 模擬。
*   **即時回饋**：在應用程式中直接查看最佳化進度和統計數據。
*   **簡易部署**：透過 `uv` 進行獨立執行與環境管理。

## 前置需求

1.  **ANSYS Electronics Desktop (AEDT)**：您必須安裝並擁有有效的 Ansys Electronics Desktop 授權（建議使用 2022 R2 或更新版本）。
2.  **Windows 作業系統**：本工具專為 Windows 環境設計。

## 安裝與使用

本專案使用 `uv` 進行相依性套件管理，所有過程皆自動化處理。

1.  **複製 (Clone) 或下載** 本專案。
2.  **雙擊 `run.bat`**。
    *   腳本會自動檢查 `uv`，若未安裝則會自動安裝。
    *   確保安裝正確的 Python 版本 (3.10)。
    *   同步所有必要的相依性套件。
    *   最後，啟動 GUI 應用程式。

> **注意**：首次執行可能需要幾分鐘下載 Python 和相關套件。之後的執行將會非常快速。

## 如何使用

1.  使用 `run.bat` 啟動應用程式。
2.  點擊 **"Select Stackup File"** (選擇堆疊檔案) 以載入您的堆疊設定 (JSON 格式)。
3.  輸入 **Max Iterations** (最大迭代次數，例如 10)。
4.  點擊 **"Start Optimization"** (開始最佳化)。
5.  在儀表板中監控日誌和統計數據。
6.  完成後，特性化後的堆疊檔案和 AEDB 模型將儲存在帶有時間戳記的輸出目錄中。
