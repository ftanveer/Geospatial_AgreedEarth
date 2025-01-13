import pandas as pd
import geopandas as gpd
import numpy as np

from json import load, loads
import requests as r

from netCDF4 import Dataset
import xarray as xr

from shapely.geometry import Polygon
from shapely.geometry import Point

import json
from json import load, loads

import time
import os
import glob
import pathlib
#custom functions import
from crome_functions_2 import *


curr_dir = os.getcwd()
parent_dir_ = os.path.dirname(curr_dir)
p = pathlib.PureWindowsPath(parent_dir_)

#converting fwdslash to backslash
base_dir = p.as_posix() + '/raw_datasets/'

# -------------------------------------------------
# READ THE DATA FILES
# -------------------------------------------------

#Define the years to process

years_to_process = [2021]

# Define configurations
config = {
    'counties': ['BED', 'BER', 'BRS', 'BUC', 'CAM', 'CHE', 'CMB', 'COR', 'DER', 'DEV', 'DOR', 'DUR', 'ERY', 'ESS', 'ESX', 'GLO', 'GMN', 'HAM', 'HER', 'HRT', 'IOW',
            'KEN', 'LAN', 'LEI', 'LIN', 'LON', 'MER', 'NOR', 'NOT', 'NRM', 'NRT', 'NYO', 'OXF', 'RUT', 'SHR', 'STF', 'SUF', 'SUR', 'SYO', 'TAW', 'WAR',
            'WIL', 'WMD', 'WOR', 'WSX', 'WYR'],
    'years': years_to_process,
    'paths': {
        'soil': os.path.join(base_dir, 'SPMM_1km/SoilParentMateriall_V1_portal1km.shp'),
        'nvz': os.path.join(base_dir, 'Nitrate_Vulnerable_Zones/Nitrate_Vulnerable_Zones_2021_DesignationsPolygon.shp'),
        'crop_lookup': os.path.join(base_dir, 'crop_lookup_table/crop_lookup_table_RB209_15052024.csv'),
        'soil_tex_lookup': os.path.join(base_dir, 'crop_lookup_table/soil_tex_mapped_27052024.csv'),
        'soil_depth': os.path.join(base_dir, 'crop_lookup_table/soil_depth_mapped.csv'),
        'lucode': os.path.join(base_dir, 'crop_lookup_table/lucode_lookup.csv'),
        'uk_grid': os.path.join(base_dir, 'UK_Spatial_1km/ukcp18-uk-land-1km.shp'),
        'weather_template': os.path.join(base_dir, 'weather/rainfall_hadukgrid_uk_1km_ann_{}01-{}12.nc'),
        'excess_rainfall' : os.path.join(base_dir, 'weather/rainfall_hadukgrid_uk_1km_mon_{}01-{}12.nc')
    },
    'crop_map_template': os.path.join(base_dir, 'CropMapOfEngland/{}/CropMapOfEngland{}{}-SHP/data/')
}



# Datasets which are year independant such as soil, crop_lookup tables etc will be preloaded before the for loop

constant_datasets = load_constant_datasets(config)


# -------------------------------------------------
# MAIN LOOP FOR PROCESSING
# -------------------------------------------------


for year in config['years']:

    #Datasets such as weather and excess rainfall depends on the CROME year we are looking at. We will load these datasets for the specified year.

    yearly_datasets = load_yearly_datasets_2(config, year)


    print(year)

    # we need previous year as it is an argument for the weather data and excess rainfall
    previous_year = year - 1

    #For the specified year , we will loop through all the counties

    for county in config['counties']:

        print(county)

        ## NOTE: load_crome_datasets assumes we are loading county's shape files for the current and previous year
        # From CROME site 2018-2021 are available as shapefiles.
        # 2017 and earlier are divided into regions, they are available as gpkg files which I created
        # 2022 is dbttable database that I converted to their respective counties as gpkg files.

        crome_datasets = load_crome_datasets(config, year, county)

        # load_crome_datasets_shp_gpkg is used
        # The load_crome_datasets_shp_gpkg needs to be modified based on which CROME year is being run. Please refer to crome_functions_2.py file
        # documentation for more details.
        #crome_datasets = load_crome_datasets_shp_gpkg(config, year, county)

        # Assign the read datasets to variables from the dictionary for easy tracking

        crome_gdf = crome_datasets['crome']


        Soil_gdf = constant_datasets["soil"]

        print("Soil read!")

        NVZ_gdf = constant_datasets["nvz"]

        print("NVZ read!")

        crop_lookup_csv = constant_datasets["crop_lookup"]

        soil_tex_csv = constant_datasets["soil_tex_lookup"]

        soil_dep_csv = constant_datasets["soil_depth"]

        weather_gdf = yearly_datasets["weather"]

        prev_CROME_gdf = crome_datasets["previous_crome"]

        lucode_df = constant_datasets["lucode"]

        excess_rainfall_current_year = yearly_datasets["excess_rainfall_current_year"]

        excess_rainfall_previous_year = yearly_datasets["excess_rainfall_previous_year"]

        print("Excess rainfall read!")

        grid_gdf = constant_datasets["uk_grid"]

        # -------------------------------------------------
        # PROCESSING THE DATAFRAMES
        # -------------------------------------------------

        ##### PROCESS CROME DATASET

        print("Start processing")

        CROME_gdf = CROME_processing(crome_gdf)

        # 2019 and older CROME does not have this column
        if 'county' not in CROME_gdf.columns:
            # Create the 'county' column and assign the value to all rows
            CROME_gdf['county'] = county

        ##### SOIL DATASET PROCESSING

        Soil_gdf = convert_4326(Soil_gdf)

        Soil_gdf.rename(columns={"geometry": "soil_geometry"}, inplace=True)

        # once the geometry column is renamed, it needs to be reactivated as the primary geometry

        Soil_gdf = Soil_gdf.set_geometry("soil_geometry")

        ##### NITRATE VULNERABLE ZONE PROCESSING

        NVZ_gdf = convert_4326(NVZ_gdf)

        ##### UK GRID GEOMETRY

        grid_gdf = convert_4326(grid_gdf)

        # I want to copy the grid geometry to a new column as it will be useful for the spatial join with  CROME

        grid_gdf["uk_grid_geometry"] = grid_gdf.geometry

        ##### HADLEY RAINFALL DATA

        # Rainfall is evaluated based on previous year

        weather_gdf = annual_rainfall_processing(weather_gdf, previous_year)

        # We shall create a geo pandas df from the long and lat from weather dataframe using 4326 crs standard
        weather_gdf = gpd.GeoDataFrame(weather_gdf, geometry=gpd.points_from_xy(weather_gdf['longitude'],
                                                                                weather_gdf['latitude'],
                                                                                crs="EPSG:4326"))

        # we merge the point geometry for weather dataset with the uk_grid geometry so that we have the weather for grids

        weather_grid_gdf = point_to_grid(weather_gdf, grid_gdf)

        weather_grid_gdf = weather_grid_gdf.loc[:, ["rainfall", "geometry", "uk_grid_geometry"]]

        weather_grid_gdf.rename(columns={'geometry': 'weather_geometry'}, inplace=True)

        weather_grid_gdf = weather_grid_gdf.set_geometry('uk_grid_geometry')

        ##### PREVIOUS CROME DATASET PROCESSING

        prev_CROME_gdf = Previous_CROME_processing(prev_CROME_gdf, crop_lookup_csv)

        ##### EXCESS RAINFALL PROCESSING

        ### PREV YEAR RAINFALL

        excess_rain_prev_year_gdf = monthly_rainfall_processing(excess_rainfall_previous_year, [10, 11, 12])

        excess_rain_prev_year_gdf = rainfall_agg_to_gpd(excess_rain_prev_year_gdf)

        ### CURRENT RAINFALL

        excess_rain_current_year_gdf = monthly_rainfall_processing(excess_rainfall_current_year, [1, 2, 3])

        excess_rain_current_year_gdf = rainfall_agg_to_gpd(excess_rain_current_year_gdf)

        ### PREV AND CURRENT YEAR MERGE

        # We spatially join the rainfall from current and prev year with exact match for the geometry

        excess_rainfall_gpd = gpd.sjoin(excess_rain_prev_year_gdf, excess_rain_current_year_gdf, how='inner', predicate='intersects')

        excess_rainfall_gpd['oct_to_march_rainfall'] = excess_rainfall_gpd["rainfall_left"] + excess_rainfall_gpd["rainfall_right"]

        excess_rainfall_gpd = excess_rainfall_gpd.to_crs(4326)

        excess_rainfall_gpd = excess_rainfall_gpd.loc[:, ['geometry', 'oct_to_march_rainfall']].copy()

        ## PROJECT EXCESS RAINFALL TO UK GRID GEOMETRY

        excess_rainfall_grid_1km = gpd.sjoin(excess_rainfall_gpd, grid_gdf, how='left', predicate='within')

        excess_rainfall_grid_1km.set_geometry('uk_grid_geometry', inplace=True)

        excess_rainfall_grid_1km = excess_rainfall_grid_1km.loc[:, ["uk_grid_geometry", "oct_to_march_rainfall"]]

        # -------------------------------------------------
        # SPATIAL JOINS
        # -------------------------------------------------

        ##### CROME AND SOIL DATASET
        print("SPATIAL JOIN")

        # Merge based on condition that CROME centroid falls within soil grid.

        CROME_gdf_2 = spatial_join(main_gdf=CROME_gdf, joining_gdf=Soil_gdf, predicate='within')

        CROME_gdf_2.rename(columns=lambda x: x.lower(), inplace=True)

        CROME_gdf_2 = CROME_gdf_2.loc[:,
                      ["cromeid", "county", "lucode", "crome_geometry", "crome_center", "soil_group", "soil_tex",
                       "soil_depth"]]

        CROME_gdf_2 = CROME_gdf_2.set_geometry('crome_center')

        ##### CROME AND WEATHER

        # we want to merge CROME center within the uk weather polygons with 'within' condition
        CROME_gdf_3 = spatial_join(main_gdf=CROME_gdf_2, joining_gdf=weather_grid_gdf, predicate='within')

        CROME_gdf_3.drop(columns=["index_right"], inplace=True)

        CROME_gdf_3 = impute_nulls_with_avg(CROME_gdf_3, 'rainfall')

        ##### CROME AND NVZ

        CROME_gdf_4 = spatial_join(main_gdf=CROME_gdf_3, joining_gdf=NVZ_gdf, predicate='within')

        CROME_gdf_4 = CROME_gdf_4.drop_duplicates(subset=['cromeid'], keep='first')

        CROME_gdf_4.loc[:, 'nvz_id'] = CROME_gdf_4['nvz_id'].fillna('Not in NVZ')

        CROME_gdf_4 = CROME_gdf_4.loc[:,
                      ["cromeid", "county", "lucode", "crome_geometry", "crome_center", "soil_group", "soil_tex",
                       "soil_depth", "rainfall", "nvz_id"]]

        ##### CROME AND CROP LOOKUPS

        CROME_gdf_5 = merge_dfs(main_df=CROME_gdf_4, joining_df=crop_lookup_csv, merge_column='lucode')

        # from data viz we see that the NaN crops are grass, trees, mixed crops , water bodies etc so we will impute with -1 for crop group and crop type id
        CROME_gdf_5[['crop type id', 'crop group id']] = CROME_gdf_5[['crop type id', 'crop group id']].fillna(-1)

        ##### CROME AND PREVIOUS CROP CROME

        CROME_gdf_6 = CROME_gdf_5.merge(prev_CROME_gdf, on='cromeid', how='left')

        ##### CROME AND SOIL LOOKUPS

        ## SOIL TEXTURE
        CROME_gdf_7 = merge_dfs_string_col(main_df=CROME_gdf_6, joining_df=soil_tex_csv, merge_column='soil_tex')

        ##SOIL DEPTH
        CROME_gdf_8 = merge_dfs_string_col(main_df=CROME_gdf_7, joining_df=soil_dep_csv, merge_column='soil_depth')

        ##### CROME AND LUCODE

        CROME_gdf_9 = merge_dfs(main_df=CROME_gdf_8, joining_df=lucode_df, merge_column='lucode')

        ##### CROME AND SOWING DATA

        CROME_gdf_10 = sowing_date(CROME_gdf_9, "sowing_month", "sowing_day", "sowing_year", year)

        ## To avoid confusion and to separate one dataset to another we shall create a column for the crome year
        CROME_gdf_10["crome_year"] = year

        ##### SNS INDEX

        ## RAINFALL ENCODING

        CROME_gdf_11 = rainfall_encoder(CROME_gdf_10, 'rainfall')

        # Convert to Integers

        columns_to_convert = ['crop type id', 'crop group id', 'soiltypeid_x', 'previous crop type id',
                              'previous crop group id']
        for column in columns_to_convert:
            CROME_gdf_11[column] = pd.to_numeric(CROME_gdf_11[column], errors='coerce').fillna(-1).astype(int)



        ## SNS MAPPING
        # SNS MAPPING BASED ON RB209 GUIDELINES
        # primary keys (1,2,3) = low,medium and high rainfall
        # secondary keys (1,0,2,7,4,3) = previous crop group id # needs updating and expanding
        # tertiary keys = soil type

        SNS_mapping = {
            1: {
                1: {'Light Sand': 1, 'Medium': 2, 'Deep Clayey': 3, 'Deep Silty': 3, 'Organic': 4, 'Peat': 5},
                0: {'Light Sand': 0, 'Medium': 1, 'Deep Clayey': 2, 'Deep Silty': 2, 'Organic': 4, 'Peat': 5},
                2: {'Light Sand': 0, 'Medium': 1, 'Deep Clayey': 2, 'Deep Silty': 2, 'Organic': 4, 'Peat': 5},
                7: {'Light Sand': 1, 'Medium': 2, 'Deep Clayey': 3, 'Deep Silty': 3, 'Organic': 4, 'Peat': 5},
                4: {'Light Sand': 0, 'Medium': 1, 'Deep Clayey': 2, 'Deep Silty': 2, 'Organic': 4, 'Peat': 5},
                3: {'Light Sand': 1, 'Medium': 3, 'Deep Clayey': 3, 'Deep Silty': 3, 'Organic': 4, 'Peat': 5}
            },
            2: {
                1: {'Light Sand': 1, 'Medium': 2, 'Deep Clayey': 2, 'Deep Silty': 3, 'Organic': 4, 'Peat': 5},
                0: {'Light Sand': 0, 'Medium': 1, 'Deep Clayey': 1, 'Deep Silty': 1, 'Organic': 4, 'Peat': 5},
                2: {'Light Sand': 0, 'Medium': 1, 'Deep Clayey': 1, 'Deep Silty': 1, 'Organic': 4, 'Peat': 5},
                7: {'Light Sand': 0, 'Medium': 2, 'Deep Clayey': 2, 'Deep Silty': 2, 'Organic': 4, 'Peat': 5},
                4: {'Light Sand': 0, 'Medium': 1, 'Deep Clayey': 1, 'Deep Silty': 1, 'Organic': 4, 'Peat': 5},
                3: {'Light Sand': 0, 'Medium': 2, 'Deep Clayey': 3, 'Deep Silty': 3, 'Organic': 4, 'Peat': 5}
            },
            3: {
                1: {'Light Sand': 0, 'Medium': 1, 'Deep Clayey': 2, 'Deep Silty': 2, 'Organic': 4, 'Peat': 5},
                0: {'Light Sand': 0, 'Medium': 1, 'Deep Clayey': 1, 'Deep Silty': 1, 'Organic': 4, 'Peat': 5},
                2: {'Light Sand': 0, 'Medium': 1, 'Deep Clayey': 1, 'Deep Silty': 1, 'Organic': 4, 'Peat': 5},
                7: {'Light Sand': 0, 'Medium': 1, 'Deep Clayey': 1, 'Deep Silty': 2, 'Organic': 4, 'Peat': 5},
                4: {'Light Sand': 0, 'Medium': 1, 'Deep Clayey': 1, 'Deep Silty': 1, 'Organic': 4, 'Peat': 5},
                3: {'Light Sand': 0, 'Medium': 1, 'Deep Clayey': 1, 'Deep Silty': 2, 'Organic': 4, 'Peat': 5}
            }
        }

        CROME_gdf_12 = map_SNS_index(CROME_gdf_11, SNS_mapping)

        # we cannot export category for geojson, so convert to integers

        CROME_gdf_12['rainfall_encoded'] = pd.to_numeric(CROME_gdf_12['rainfall_encoded'], errors='coerce').fillna(-1).astype(int)



        # CROME_gdf_12.set_geometry('crome_geometry',inplace= True)

        CROME_gdf_12.drop(columns=["unnamed: 0_y", "unnamed: 0_x", "crome crop name", "month", "day", "sowing_year",
                                   "previous crome crop name", "soiltypename_y", "soiltypeid_y"], inplace=True)

        ##CROME AND EXCESS RAINFALL
        CROME_gdf_12.set_geometry("crome_center", inplace=True)

        CROME_gdf_13 = gpd.sjoin(CROME_gdf_12, excess_rainfall_grid_1km, how='left', predicate='within')

        CROME_gdf_13 = impute_nulls_with_avg(CROME_gdf_13, 'oct_to_march_rainfall')


        ## DROP NAN

        # We can impute the crop names with value from land use description

        CROME_gdf_13["crop type name"] = CROME_gdf_13["crop type name"].fillna(CROME_gdf_13["land use description"])

        # Similar to crop type id the same applies for sowing date, they are mostly Grass, Non-vegetated land, water bodies etc

        CROME_gdf_13["sowingdate"] = CROME_gdf_13["sowingdate"].fillna(0)


        #  assuming previous crop type is Fallow Land, hence 28 is th crop type id and 1 is crop group id

        CROME_gdf_13["previous crop type id"] = CROME_gdf_13["previous crop type id"].fillna(int(28))

        CROME_gdf_13["previous crop group id"] = CROME_gdf_13["previous crop group id"].fillna(int(1))

        # NOTE: The soil mapping has been created to reflect all unique values for soil texture from Soil dataset,


        # As per Data checking less than 0.3% of soil type id is null so we can impute with the median

        CROME_gdf_13["soiltypeid_x"] = CROME_gdf_13["soiltypeid_x"].fillna(CROME_gdf_13["soiltypeid_x"].median())

        # we fill the corresponding soiltype with desc Imputed_value so we know which were imputed

        CROME_gdf_13["soiltypename_x"] = CROME_gdf_13["soiltypename_x"].fillna("Imputed_value")

        ### NITRATE VULNERABLE ZONE ENCODING

        CROME_gdf_13["nvz_encoding"] = CROME_gdf_13["nvz_id"].apply(lambda x: 1 if x == "Not in NVZ" else 2)

        if CROME_gdf_13['crome_geometry'].is_empty.any():
            print("There are empty geometries in the GeoDataFrame.")
        if CROME_gdf_13.isna().sum().any():
            print("There are NaN values in the GeoDataFrame.")



        CROME_gdf_14 = CROME_gdf_13.loc[:,
                       ["cromeid", "county", "lucode", "soil_group", "soil_tex", "soil_depth", "rainfall", "nvz_id",
                        "crop type name", "crop type id", "crop group id", "previous_crop_lucode",
                        "previous crop group id", "previous crop type id", "soiltypename_x", "soiltypeid_x",
                        "land cover description",
                        "land use description", "sowingdate", "rainfall_encoded", "sns_index", "crome_geometry",
                        "oct_to_march_rainfall", "nvz_encoding","crome_year"]]

        CROME_gdf_14.set_geometry("crome_geometry", inplace=True)

        # For ideal export,1.  please ensure an active geometry is set
        # 2. only one geometry column is present, which is the active one
        # 3. certain data types aren't allowed such as catagorical


        export_dir = base_dir + 'Processed_datasets/{}_{}_RB209_Input_31052024.gpkg'.format(county,year)

        CROME_gdf_14.to_file(export_dir, driver='GPKG', index=False)

        print(f"County {county} of {year} processed and exported.")
















