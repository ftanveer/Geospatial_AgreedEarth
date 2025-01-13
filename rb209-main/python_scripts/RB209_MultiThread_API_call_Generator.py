import pandas as pd
import geopandas as gpd
import numpy as np

from json import load, loads
import requests as r

from netCDF4 import Dataset
import xarray as xr

from shapely.geometry import Polygon
from shapely.geometry import Point

from datetime import datetime



from concurrent.futures import ThreadPoolExecutor, as_completed
import functools


import json
from json import load, loads, JSONDecodeError
import time
import logging


import os
import pathlib
#custom functions import
from crome_functions_2 import *




###  CONFIGURE THE ERROR LOGGER

logging.basicConfig(
    filename='error_log.log',   # Log file name
    level=logging.INFO,        # Logging level (ERROR captures only error messages)
    format='%(asctime)s - %(levelname)s - %(message)s'  # Log message format
)

#### PATH DIRECTORY

curr_dir = os.getcwd()
parent_dir_ = os.path.dirname(curr_dir)
p = pathlib.PureWindowsPath(parent_dir_)

parent_dir = p.as_posix()

#Adjust the file directory accordingly
rb209_input_dir = parent_dir + '/raw_datasets/Processed_datasets'

#Load the lucode df, it will be a constant dataset
# Lucode_N_application contains avg N recommendation provided by Janice, these values will be used for crops which are in CROME but not
# mapped to RB209 crop type id based on the crop lookup table.

lucode_N_application = pd.read_csv(parent_dir + '/raw_datasets/crop_lookup_table/lucode_to_N_app_2022.csv')
lucode_N_application.drop(columns=["Unnamed: 0"], inplace=True)
lucode_N_application.rename(columns={"LUCODE": "lucode"}, inplace=True)



# define api call function

def make_api_call(item,j,total_api_rows):

    logging.info("Starting API call for index %d", j)

    print(f"{j}/{total_api_rows}")

    try:
        api_data = r.post(
            url + "api/main/recommendations",
            auth=auth,
            json=item)
        api_data.raise_for_status()  # Raise an error for bad status codes

        # Parse the JSON response
        recommends = loads(api_data.text)



        try:
            crop_need_value = recommends['Recommendations'][0]['CropNeedValue']
        except:
            print(item['Field']['Soil']["SoilTypeID"])
            print(recommends)
            crop_need_value = float('nan')

    except r.RequestException as req_err:
        # Handle request-related errors
        logging.error(f"Request error at index {j}: {req_err}")
        crop_need_value = float('nan')

    except (JSONDecodeError, KeyError, IndexError) as parse_err:
        # Handle JSON parsing errors or missing keys/indices
        logging.error(f"Parsing error at index {j}: {parse_err}")
        logging.error(f"Item: {item}")
        crop_need_value = float('nan')

    return crop_need_value, j








for filename in os.listdir(rb209_input_dir):
    if filename.endswith('.gpkg'):
        file_path = os.path.join(rb209_input_dir, filename)



        gdf_1 = gpd.read_file(file_path)

        logging.info(f"Processing {filename}")

        input_shape = gdf_1.shape
        print(f"{filename} has shape {input_shape}")

        start_time = time.time()

        print(f"Processing {filename}")


        # OPTIONAL: Slice a small test gdf for testing purposes
        #gdf_1 = gdf_1.iloc[0:100,:]

        # -------------------------------------------------
        # EXTRACT INTERESTED CROPS
        # -------------------------------------------------

        crops_of_interest = [1, 2, 3, 9, 26]  ## all crop id based off crop lookup table



        gdf_rb209 = gdf_1.loc[gdf_1["crop type id"].isin(crops_of_interest)]

        total_api_rows = gdf_rb209.shape[0]

        print(f"{total_api_rows} number of rows calling the RB209 API")


        ### FINAL FEAT ENG
        # improvement would be to have harvest year in crop lookup, although my findings shows modifying harvest year does not change rb209 N recomm values
        gdf_rb209.loc[:,"harvest_year"] = gdf_rb209["crome_year"]

        # -------------------------------------------------
        # POPULATE RB209 INPUT DICTIONARY
        # -------------------------------------------------



        dict_list = []

        # Iterate over the rows of the DataFrame
        for index, row in gdf_rb209.iterrows():
            # Initialize the nested dictionary
            dict_input = {
                "Field": {
                    "FieldType": 1,
                    "MultipleCrops": False,
                    "Arable": [{
                        "CropGroupID": row['crop group id'],
                        "CropTypeID": row['crop type id'],
                        "CropInfo1ID": 2,
                        "SowingDate": row['sowingdate'],
                        "ExpectedYield": 0
                    }],
                    "Grassland": {},
                    "Soil": {
                        "SoilTypeID": row['soiltypeid_x'],
                        "NVZActionProgrammeID": row["nvz_encoding"],
                        "SoilAnalyses": [{'SulphurDeficient': False,
                                          'SNSIndexID': row['sns_index'],
                                          'SNSMethodologyID': 4}]
                    },
                    "HarvestYear": row['harvest_year'],
                    "Area": 1.0,
                    "Postcode": "",
                    "Altitude": 0,
                    "SiteClassID": 3,
                    "RainfallAverage": row['rainfall'],
                    "ExcessWinterRainfall": row['oct_to_march_rainfall'],
                    "OrganicMaterials": [],
                    "PreviousCropping": {
                        "PreviousGrassID": 1,
                        "PreviousCropGroupID": row['previous crop group id'],
                        "PreviousCropTypeID": row['previous crop type id']
                    }
                },
                "Nutrients": {
                    "Nitrogen": True,
                    "Phosphate": False,
                    "Potash": False,
                    "Magnesium": False,
                    "Sodium": False,
                    "Sulphur": False,
                    "Lime": False
                },
                "Totals": False
            }
            # Append the dictionary to the list

            if row["crop group id"] == 0:

                if row["soiltypeid_x"] == 3:
                    # if crop group id is 0 then we need to specify CropInfo2ID
                    # if soiltypeid is 3 (which is Deep Clay) then we need to specify KReleasingClay
                    dict_input['Field']['Arable'][0]["CropInfo2ID"] = 1
                    dict_input['Field']['Soil']["KReleasingClay"] = False


                else:
                    dict_input['Field']['Arable'][0]["CropInfo2ID"] = 1


            elif row["soiltypeid_x"] == 3:
                # if soiltypeid is 3 (which is Deep Clay) then we need to specify KReleasingClay
                dict_input['Field']['Soil']["KReleasingClay"] = False

            dict_list.append(dict_input)

        #### READ RB209 API CREDENTIALS

        with open(parent_dir + '/rb209_credentials/api_key.json') as f:
            api_cred = json.load(f)
        print(api_cred.keys())

        auth = api_cred['UserName'], api_cred['Licence Key']

        url = 'https://rb209-api-v1.ahdb.org.uk/'

        # -------------------------------------------------
        # CALL THE API AND APPEND TO A LIST
        # -------------------------------------------------


        # define an empty list and append the RB209 values to it

        rb209_out = [None] * len(dict_list)

        with ThreadPoolExecutor(max_workers=10) as executor:
            # Submit tasks to the executor
            futures = {executor.submit(functools.partial(make_api_call, item, j, total_api_rows)): j for j, item in
                       enumerate(dict_list)}

            for future in as_completed(futures):
                try:
                    crop_need_value, index = future.result()
                    rb209_out[index] = crop_need_value
                except Exception as e:
                    logging.error(f"Unexpected error: {e}")



        # Sanity check to ensure the list is fully populated
        if len(rb209_out) != len(dict_list):
            logging.error("Mismatch in lengths: rb209_out and dict_list do not have the same length")
            continue


        #Convert list to df

        df_out = pd.DataFrame(rb209_out)



        ##### ADD TO DATAFRAME

        gdf_rb209["N_Recommend_RB209"] = df_out.iloc[:, 0].values



        gdf_rb209["N_Recommend_RB209"] = gdf_rb209["N_Recommend_RB209"].fillna("None")

        # to avoid Warning for pandas 2.0 FutureWarning: Downcasting behavior in `replace` is deprecated and will be removed in a future version.
        # added line below
        pd.set_option('future.no_silent_downcasting', True)

        ## Replace None with -999
        gdf_rb209["N_Recommend_RB209"] = gdf_rb209["N_Recommend_RB209"].replace("None", -999)

        gdf_rb209["N_Recommend_RB209"] = pd.to_numeric(gdf_rb209["N_Recommend_RB209"], errors='coerce')


        # -------------------------------------------------
        # MERGE WITH N APPLICATION VALUES
        # -------------------------------------------------

        # NOTE: N application comes from Avg values from lucode_to_N csv file


        gdf_2 = gdf_1.merge(lucode_N_application, how='left', on='lucode')


        # We will fill the N application values for crops of interest with NaN

        gdf_2.loc[gdf_2["crop type id"].isin(crops_of_interest), "N_Application"] = np.nan

        # Slice only needed columns

        rb209_out_N_app = gdf_rb209.loc[:, ["cromeid", "N_Recommend_RB209"]]

        gdf_3 = gdf_2.merge(rb209_out_N_app, how='left', on='cromeid')

        gdf_3.loc[:, "N_Application"] = gdf_3["N_Application"].fillna(value=gdf_3["N_Recommend_RB209"])





        gdf_3.drop(columns=["N_Recommend_RB209"], inplace=True)

        ## Change crs to 27700

        gdf_3 = gdf_3.to_crs(27700)

        # Get current date in the format DDMMYYYY
        current_date = datetime.now().strftime('%d%m%Y')

        #Get county name
        county_name = filename.split('_')[0]

        # Get crome_year
        crome_year = filename.split('_')[1]

        # Define the output folder and ensure it exists
        output_folder = parent_dir + '/raw_datasets/RB209_datasets'
        os.makedirs(output_folder, exist_ok=True)

        # Define the output file path
        output_dir = f'{output_folder}/{county_name}_{crome_year}_RB209_Output_{current_date}.gpkg'

        print(output_dir)

        gdf_3.to_file(output_dir,driver='GPKG', index=False)





end_time = time.time()

elapsed_time = end_time - start_time
print(f"Elapsed Time: {elapsed_time} seconds")
