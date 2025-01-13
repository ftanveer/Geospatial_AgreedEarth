# RB209 API Data Processing

This project processes GeoPackage (GPKG) files, makes API calls to the RB209 recommendation system, and outputs the results to new GPKG files. 
The input files should be stored in the `Processed_datasets` directory. The output files will be saved in the `RB209_datasets` directory (if it doesn't exist, the script will create it automatically).

## Table of Contents

- [Requirements](#requirements)
- [Setup](#setup)
- [Usage](#usage)
- [Logging](#logging)

## Requirements

Please refer to requirements.txt

## Setup

1. Clone the repository to your local machine:

    ```bash
    git clone <repository-url>
    cd <repository-name>
    ```

2. Install the required Python packages:

    ```bash
    pip install pandas geopandas requests
    ```

3. Ensure that you have your RB209 API credentials stored in a JSON file (`api_key.json`) in the `rb209_credentials` directory. The JSON file should have the following structure:

    ```json
    {
        "UserName": "your_username",
        "Licence Key": "your_licence_key"
    }
    ```

## Usage

1. Place your input GPKG files in the `Processed_datasets` directory. The files should follow the naming convention: `<county>_<year>_RB209_Input_<date>.gpkg`. For example: `ESS_2021_RB209_Input_29052024.gpkg`.

2. Run the Python script:

    
    RB209_MultiThread_API_call_Generator.py
    

3. The output files will be saved in the `RB209_datasets` directory with the naming convention: `<county>_<year>_RB209_Output_<date>.gpkg`.

4. For running the script with preferred crops please modify this line accordingly:
    ```bash
    crops_of_interest =  [5...] ## add crop type id from crop lookup table
    ```

## Logging

The script will generate a log file named error_log.log in the project root directory. This log file will contain debug and error messages to help you track the progress and identify any issues during the execution.

