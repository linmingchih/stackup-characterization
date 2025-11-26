# 專案詳細規格書 (Project Specification)

本規格書對應 `todo.md` 之開發項目，詳細定義各模組之功能需求、輸入輸出格式、與邏輯規則，基礎參照 `GEMINI.md`。

## 1. 核心模型與模擬邏輯 (Core Model & Simulation)

### 1.1 幾何建模模組 (`modeling.py`)

此模組負責將堆疊參數轉換為 ANSYS HFSS 3D Layout 專案 (`.aedb`)。

*   **執行方式**: 獨立 Subprocess 執行 (因 `PyEDB` 與 `PyAEDT` 在同一 Process 內可能衝突)。
*   **輸入資料**: 透過 JSON 或 Pickle 傳入字典物件，包含：
    *   `output_aedb_path`: 目標 `.aedb` 路徑。
    *   `frequency`: 模擬頻率 (GHz)。
    *   `layers`: 包含 Dielectric 與 Signal 層的完整列表，按物理順序排列。
    *   `target_layer`: 當前要模擬的訊號層名稱 (Signal Layer Name)。
    *   `trace_params`: 該層的 `width`, `spacing` (mils 或 mm, 需統一單位)。
    *   `ref_layers`: 參考層名稱列表 (如 `['gnd1', 'gnd2']`)。
*   **功能需求**:
    1.  **初始化**: 使用 `pyedb.Edb(version='2024.1')` (或相容版本) 建立專案。
    2.  **材料庫 (Material Def)**:
        *   遍歷輸入的層，為每一層建立 Dielectric Material。
        *   設定 `permittivity` (Dk) 與 `dielectric_loss_tangent` (Df)。
    3.  **堆疊建立 (Stackup)**:
        *   使用 `edb.stackup.add_layer`。
        *   **Signal Layer**: Type='signal', Material='copper', Thickness (from JSON). 設定 Roughness 參數 (`hallhuray_surface_ratio`, `hallhuray_nodule_radius` 應用於 top/bottom/side)。
        *   **Dielectric Layer**: Type='dielectric', Material (對應上述建立的材料), Thickness。
    4.  **幾何繪製 (Layout)**:
        *   **Traces (差動對)**: 在 `target_layer` 繪製兩條平行線。
            *   長度: 固定 1000 mil (或足夠長度以避免邊緣效應)。
            *   寬度: `width`。
            *   間距: `spacing` (假設 Spacing 為 **Edge-to-Edge**，實作需依此計算中心座標。若輸入定義不明，需於程式碼中註解假設)。
        *   **Planes (參考層)**: 在 `ref_layers` 指定的層上建立 `create_rectangle`，覆蓋整個 Trace 區域 (例如 `('0mil', '-100mil')` to `('1000mil', '100mil')`)，Net Name設為 `GND`。
    5.  **埠口設定 (Ports)**:
        *   建立 **Differential Wave Ports**。
        *   位置: Trace 的起點 (0mil) 與終點 (1000mil)。
        *   定義: Positive Net = Trace_P, Negative Net = Trace_N。
    6.  **模擬設定 (Setup)**:
        *   `create_hfss_setup`。
        *   Type: Single Frequency。
        *   Freq: 輸入的 `frequency`。
        *   Max Passes: 20。
        *   Max Delta S: 0.01。
    7.  **存檔與關閉**: `edb.save_edb_as` 與 `edb.close_edb`。

### 1.2 模擬執行模組 (`simulation.py`)

此模組負責執行模擬並提取數據。

*   **執行方式**: 獨立 Subprocess。
*   **輸入資料**: `.aedb` 檔案路徑。
*   **功能需求**:
    1.  **載入專案**: `pyaedt.Hfss3dLayout`。
    2.  **差動對定義**: 呼叫 `set_differential_pair` 將 Port 分組 (例如 `Diff1` = Port1_P + Port1_N)。
    3.  **執行模擬**: `hfss.analyze(cores=N)`。
    4.  **數據提取**:
        *   取得 **Complex S-parameters** (複數 S 參數)，而非僅 Magnitude。
        *   提取 `S(diff1, diff1)` (回波損耗) 與 `S(diff2, diff1)` (插入損耗)。
    5.  **後處理計算**:
        *   **S21 (dB)**: `20 * log10(abs(S(diff2, diff1)))`。如果 `loss_target` 為 0，仍需計算。
        *   **Zdiff (Ohm)**: 使用公式 `Zdiff = 100 * (1 + S11) / (1 - S11)`。其中 `S11` 為 `S(diff1, diff1)` 的複數值。
    6.  **輸出**: 回傳 JSON 格式結果 `{ "Zdiff_real": float, "S21_db": float, "pass": bool }`。

### 1.3 流程控制模組 (`characterization_process.py`)

核心邏輯與優化演算法。

*   **輸入**: `stackup_viewer.html` 匯出的原始 JSON。
*   **資料結構解析**:
    *   讀取 `frequency`。
    *   讀取 `settings` 中的 `variation` (百分比) 與 `tolerance` (百分比)。
    *   解析 `rows`。
*   **優化流程 (Optimization Loop)**:
    *   針對每一個 Signal Layer (具備 `width` 與 `spacing`):
        1.  **初始檢查**: 若 `width` 或 `spacing` 為空，跳過。
        2.  **參數初始化**: 讀取 JSON 初始值 (Width, Spacing, Etch, Thickness, Dk, Df, Roughness)。
        3.  **迭代迴圈 (Iteration Loop)**:
            *   **Step A**: 呼叫 `modeling.py` 產生模型。
            *   **Step B**: 呼叫 `simulation.py` 取得 `current_Zdiff` 與 `current_S21`。
            *   **Step C**: 記錄 Log (CSV)。
            *   **Step D**: 判斷收斂。
                *   條件: `abs(current_Zdiff - target_Zdiff) <= target_Zdiff * 1%` **且** `abs(current_S21 - target_S21) <= target_S21 * 1%`。
                *   注意: 若 `target_S21` 為 0，則僅檢查 Zdiff (或 S21 誤差絕對值小於特定閾值)。
            *   **Step E**: 若未收斂，計算參數調整量。
                *   **調整策略**: 依序調整以下參數，直到該參數達到 `variation` 極限，才移動到下一個參數。
                *   **順序**:
                    1.  `etch_factor` (±20%)
                    2.  `thickness` (導體厚度) (±20%)
                    3.  `dk` (上下介電層 Dk) (±20%)
                    4.  `df` (上下介電層 Df) (±20%)
                    5.  `hallhuray_surface_ratio` (±50%)
                    6.  `nodule_radius` (±50%)
                *   **限制 (Clamping)**: 新參數值必須限制在 `Initial_Value * (1 ± variation/100)` 範圍內。
                *   **Etch Factor 特例**: 若值為負 (如 -2.5)，變異範圍應用於絕對值 (即 -3.0 ~ -2.0)。
    *   **結果輸出**:
        *   更新原始 JSON 資料結構中的參數為優化後數值。
        *   產生 `_ok.json` (完整 JSON)。
        *   產生 `_ok.csv` (迭代過程 Log)。
        *   產生 `_ok.xml` (最終 Stackup XML 定義)。

## 2. 使用者介面與控制器 (UI & Controller)

### 2.1 GUI 介面 (`gui.py`)

*   **框架**: `pywebview`。
*   **元件**:
    *   **File Input**: 選擇 `stackup_layers_xxxx.json`。
    *   **Start Button**: 觸發 Characterization。
    *   **Log Area**: `<textarea>` 或 `<div>`，即時顯示後端 `print` 的訊息 (透過 Pywebview API 傳遞)。
    *   **Progress**: 簡單顯示當前處理的 Layer 名稱。

### 2.2 主程式 (`main.py`)

*   負責啟動 `pywebview`。
*   建立 Python to JS 的 API 橋接 (`expose`)。
*   捕捉 `characterization_process` 的 `stdout/stderr` 並即時推送到 GUI。

## 3. 檔案與目錄結構

*   **Root**:
    *   `main.py`
    *   `gui.py`
    *   `characterization_process.py`
    *   `modeling.py`
    *   `simulation.py`
*   **Output**:
    *   在輸入 JSON 同級目錄下建立 `Timestamp_Folder/` (如 `20251126_0900/`)。
    *   所有 `.aedb` 與結果檔案 (`_ok.*`) 存於此。

## 4. 錯誤處理與邊界條件

*   **HFSS License**: 若無 License，模擬將失敗。需捕獲 PyAEDT 異常並在 Log 顯示。
*   **幾何錯誤**: 若參數導致幾何不合理 (如 spacing < 0)，需在 `modeling.py` 前攔截。
*   **不收斂**: 若所有參數調整皆達到極限仍未收斂，標記該 Layer 為 Fail，並保留最後一次的最佳參數(或初始參數)，繼續執行下一層，不應中斷整個流程。
