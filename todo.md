# 專案待辦事項 (Project Todo)

根據 `GEMINI.md` 的需求規格，以下是按優先級排序的開發與測試計畫。

## 階段一：核心模型與模擬邏輯 (Model & Simulation)
此階段專注於後端邏輯，確保能正確建立模型並執行模擬。

- [ ] **環境建置與依賴確認**
    - [ ] 確認 Python 環境與 `pyproject.toml` 依賴 (pyedb, pyaedt, scipy, pywebview)。
    - [ ] 設定日誌 (Logging) 機制。

- [ ] **實作 `modeling.py` (幾何建模 - PyEDB)**
    - [ ] 實作 `create_stackup_model` 函數，接收 JSON 參數。
    - [ ] **材料與疊構**: 使用 PyEDB 建立 Dielectric 與 Conductor 層。
    - [ ] **幾何繪製**: 根據 `width`, `spacing` 繪製差動訊號線 (Traces) 與參考平面 (Planes)。
    - [ ] **埠與設定**: 建立 Differential Wave Ports，並設定 HFSS 求解頻率與收斂條件。
    - [ ] 儲存 `.aedb` 專案檔案。

- [ ] **實作 `simulation.py` (模擬執行 - PyAEDT)**
    - [ ] 實作模擬執行函數，載入 `.aedb`。
    - [ ] **差動對設定**: 使用 `set_differential_pair` 定義埠口。
    - [ ] **執行分析**: 呼叫 HFSS 求解器 (`hfss.analyze`)。
    - [ ] **數據提取**: 提取 dB(S21) 與 Zdiff (由 S11 計算)，並回傳結果。

- [ ] **實作 `characterization_process.py` (優化流程控制)**
    - [ ] **輸入解析**: 讀取 `stackup_viewer.html` 匯出的 JSON 檔案。
    - [ ] **目錄管理**: 建立時間戳記 (Timestamp) 的輸出目錄。
    - [ ] **優化迴圈 (Optimization Loop)**:
        - [ ] 針對每個訊號層 (`width` & `spacing` 存在) 進行迭代。
        - [ ] 整合 `modeling.py` 與 `simulation.py` 執行單次模擬。
        - [ ] **結果判定**: 檢查 Zdiff 與 Loss 是否在 `target ± tolerance` 範圍內。
        - [ ] **參數調整**: 若未通過，根據優先級 (Etch -> Thickness -> Dk -> Df -> Roughness) 調整參數，並限制在 `variation` 允許範圍內。
    - [ ] **結果記錄**: 實作 CSV 記錄功能 (Log 每一代的參數與結果)。
    - [ ] **檔案輸出**: 生成最終的 `_ok.json`, `_ok.csv`, `_ok.xml`。

## 階段二：使用者介面與控制器 (View & Controller)
此階段整合後端邏輯至 GUI。

- [ ] **實作 `gui.py` (使用者介面)**
    - [ ] 使用 `pywebview` 建立視窗。
    - [ ] 實作檔案選擇器 (File Picker) 以選取 JSON 輸入檔。
    - [ ] 實作「開始執行」按鈕與狀態顯示。
    - [ ] 實作即時日誌視窗 (Log Output)，顯示後端處理進度。

- [ ] **實作 `main.py` (主程式)**
    - [ ] 初始化 GUI。
    - [ ] 建立 GUI 與 `characterization_process` 之間的通訊 (將 Log 訊息傳送至前端)。
    - [ ] 處理程式異常與錯誤回報。

## 測試計畫 (Test Plan)

### 1. 單元測試 (Unit Tests)
針對個別函數邏輯進行測試，不依賴 ANSYS 軟體。
- [ ] **參數調整邏輯測試**: 測試優化演算法是否正確依照優先順序調整參數，且嚴格遵守 `variation` 百分比限制 (Clamp logic)。
- [ ] **數學計算測試**: 驗證 Zdiff = 100 * (1 + S11)/(1 - S11) 計算公式。
- [ ] **檔案解析測試**: 測試 JSON 輸入讀取與 XML/CSV 輸出格式正確性。

### 2. 整合測試 (Integration Tests)
- [ ] **Mock 模擬測試**: 
    - 建立 Mock 物件取代 `modeling.py` 與 `simulation.py` 的實際執行。
    - 模擬模擬器回傳特定的 S 參數，驗證 `characterization_process` 的優化迴圈是否能正確收斂或在超時後停止。
- [ ] **幾何生成測試 (Dry Run)**:
    - 執行 `modeling.py` 產生 `.aedb`，但不執行模擬。
    - 手動檢查生成的 `.aedb` (使用 ANSYS Electronics Desktop 開啟)，確認層別、材料、Trace 寬度與 Port 位置是否正確。

### 3. 系統驗收測試 (System Acceptance Tests)
- [ ] **端對端測試 (E2E)**:
    - 使用 `data/stackup_layers_1007.json` 作為輸入。
    - 在具有 ANSYS License 的環境下執行完整流程。
    - 驗證是否產生 `_ok` 系列檔案。
    - 驗證最終輸出的參數是否使 Zdiff/Loss 達到目標 (或在限制下盡可能接近)。
