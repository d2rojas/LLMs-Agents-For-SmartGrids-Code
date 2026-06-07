# Wind Power Forecasting Agent (LLM-Based)
This repository contains an agentic AI system that performs 48-hour wind power forecasting using a combination of historical SCADA data and real-time meteorological forecasts (ERA5). The system utilizes Gemini 3 Flash (or Claude 3) to reason over binned data and provide structured JSON forecasts. This is located in `presentation.ipynb`.

`experiments.ipynb` contains the experiments conducted to determine which prompt engineering or tokenization methods best improved the accuracy of our model.

## Git LFS
To manage these large dataset files efficiently within Git, we will use Git Large File Storage (Git LFS).
**It is mandatory for all team members to set up Git LFS before cloning or working with the data files.** Failure to do so will result in errors when pushing/pulling large files.

### Setup Instructions: Git LFS
- **Download and install Git LFS:** https://git-lfs.com/
- Alternatively, using a package manager:
    - macOS (Homebrew): `brew install git-lfs`
    - Windows (Chocolatey): `choco install git-lfs`

- Make sure to run `git lfs install` from within your local clone of the repo

- After that, you can commit and push normally

## Quick Start (Using presentation.ipynb)
1. Clone the Repository
```
git clone https://github.com/JettN/ECE-285-Team2.git
cd ECE-285-Team2
```
2. Install Dependencies
```
pip install -r requirements.txt
```
3. Setup API Keys

The notebook requires an API key for the LLM provider.

**Gemini**: Get a key from Google AI Studio.

**Claude**: Get a key from Anthropic Console.

In the "Load LLM Client" cell of the notebook, set your provider and key:

```
PROVIDER = "gemini" # or "claude"
GEMINI_API_KEY = os.environ["GOOGLE_API_KEY"] #or
GEMINI_API_KEY = "your_key_here"
```
## Data Requirements
The notebook expects the SDWPF Dataset (Baidu KDD Cup 2022) to be present in the root directory:

`wtbdata_245days.csv`: Historical SCADA data for 134 turbines.

**Note:** If you have Git LFS installed, you can pull the dataset from the directory.

## System Architecture
The forecasting pipeline follows an "Agentic" flow:

1. Data Retrieval: Loads 14 days of historical SCADA data.

2. Preprocessing: Performs 16-level equal-width binning on wind speed and power to manage context window efficiency.

3. Tool Use: Fetches 48-hour ERA5 weather forecasts (100m wind speed) via the Open-Meteo API.

4. LLM Reasoning: Passes the binned history and weather forecast to the LLM.

5. Verification: Validates the output for JSON structure and ensures a 288-step forecast (10-minute resolution).

6. Evaluation: Calculates RMSE/MAE and plots results against ground truth.

## Usage
1. Open `presentation.ipynb` in Jupyter or VS Code.

2. Run the Helper Functions cells to initialize the binning and weather tools.

3. Scroll down to the "LLM API Call with Forecast added" section

4. Adjust the Turbine ID and Data_Start_Day in the final cell.

5. Execute the `call_llm_with_forecast` function to generate the prediction.

## Limitations & Notes
API Limits: The Gemini free tier is limited to 20 requests per day.

Retries: The weather tool has a built-in 3-attempt retry logic with a 5-second sleep to handle API rate limiting.

Physical Bounds: The model is instructed to clip power output between 0 and 1500kW.
