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

import os
import glob
import pathlib
## Read files


def read_shapes(file_directory):
    #Read shape file into a geoDataframe
    gdf = gpd.read_file(file_directory)

    return gdf



def read_netcdf(file_directory):
    #Read netcdf file into a dataframe
    file_nc = xr.open_dataset(file_directory)
    df = file_nc.to_dataframe()
    df.reset_index(inplace = True)

    return df

def load_yearly_datasets_2(config, year):
    datasets = {}
    previous_year = year - 1

    datasets['weather'] = read_netcdf(config['paths']['weather_template'].format(previous_year,previous_year))
    datasets['excess_rainfall_current_year'] = read_netcdf(config['paths']['excess_rainfall'].format(year,year))
    datasets['excess_rainfall_previous_year'] = read_netcdf(config['paths']['excess_rainfall'].format(previous_year,previous_year))
    return datasets



def find_and_load_shapefile(config, year, county):
    # loads shapefile
    crome_dir = config['crop_map_template'].format(year, year, county)
    shapefile_path = glob.glob(os.path.join(crome_dir, '*.shp'))

    if shapefile_path:
        print(f"Loaded CROME data from {shapefile_path[0]}")
        return gpd.read_file(shapefile_path[0])
    else:
        print(f"No shapefile found in {crome_dir}")
        return None


def load_crome_datasets(config, year, county):

    datasets = {}

    #e.g. CropMapOfEngland/2020/CropMapOfEngland2020ESS-SHP/data/Crop_Map_of_England_2020_Essex.shp

    # Load current year CROME data
    datasets['crome'] = find_and_load_shapefile(config,year, county)

    # Load previous year CROME data
    previous_year = year - 1

    datasets['previous_crome'] = find_and_load_shapefile(config,previous_year, county)

    return datasets

#################################TEMP FUNCTION
def load_crome_datasets_shp_gpkg(config, year, county):

    datasets = {}


    def find_and_load_gpkg(year, county,date):
        curr_dir = os.getcwd()
        parent_dir_ = os.path.dirname(curr_dir)
        p = pathlib.PureWindowsPath(parent_dir_)

        # converting fwdslash to backslash
        base_dir = p.as_posix() + '/raw_datasets/'

        crome_dir = base_dir + 'CropMapOfEngland/{year}/{county}_{year}_CROME_{date}.gpkg'.format(year = year, county = county,date=date)

        output = gpd.read_file(crome_dir)
        print(f"Loaded CROME data from {crome_dir}")
        return output

    # Load current year CROME data

    # If curent year CROME is available as gpkg file e.g. BED_2022_CROME_04062024.gpkg then use function as follows

    datasets['crome'] = find_and_load_gpkg(year, county,'04062024')

    # If curent year CROME is available as shapefile  e.g. Crop_Map_of_England_2021_Bedfordshire.shp then use function as follows

    #datasets['crome'] = find_and_load_shapefile(config, previous_year, county)


    # Load previous year CROME data
    previous_year = year - 1

    # If previous_crome year  is available as gpkg file e.g. BED_2022_CROME_04062024.gpkg then use function as follows
    # datasets['previous_crome'] = find_and_load_gpkg(year, county, '04062024')

    # If previous_crome year is available as shapefile  e.g. Crop_Map_of_England_2021_Bedfordshire.shp then use function as follows
    datasets['previous_crome'] = find_and_load_shapefile(config,previous_year, county)

    return datasets


######################################TEMP FUNCTION/


def load_constant_datasets(config):
    datasets = {}
    datasets['soil'] = gpd.read_file(config['paths']['soil'])
    datasets['nvz'] = gpd.read_file(config['paths']['nvz'])
    datasets['crop_lookup'] = pd.read_csv(config['paths']['crop_lookup'])
    datasets['soil_tex_lookup'] = pd.read_csv(config['paths']['soil_tex_lookup'])
    datasets['soil_depth'] = pd.read_csv(config['paths']['soil_depth'])
    datasets['lucode'] = pd.read_csv(config['paths']['lucode'])
    datasets['uk_grid'] = gpd.read_file(config['paths']['uk_grid'])
    return datasets



def convert_4326(geodf):

    #Convert geodataframe coordinate ref system to 4326
    geodf = geodf.to_crs(4326)

    return geodf

#CROME PROCESSING

def CROME_processing(crome_data):

    #check if coordinate ref system is at 27700, centroid calculation should be done in 27700

    if crome_data.crs != 'epsg:27700':
        raise ValueError("Input GeoDataFrame must have CRS set to EPSG 27700 (British National Grid).")

    crome_data['CROME_center'] = crome_data.geometry.centroid

    #convert to 4326 coordinate ref system while geomerty column is active

    crome_data = convert_4326(crome_data)

    # make crome_center the active geometry and then convert to crs 4326 as well
    crome_data = crome_data.set_geometry('CROME_center')
    crome_data = convert_4326(crome_data)

    #rename the geometry column in order to avoid confusion with other gdf datasets

    crome_data.rename(columns = {'geometry':'CROME_geometry'}, inplace = True)

    return crome_data

## Merge dataframes

def merge_dfs(*, main_df, joining_df,merge_column):

    main_df.rename(columns = lambda x:x.lower(), inplace = True)

    joining_df.rename(columns = lambda x:x.lower(), inplace = True)

    merged_df = main_df.merge(joining_df, on = merge_column ,how = 'left')

    return merged_df


def merge_dfs_string_col(*, main_df, joining_df,merge_column):

    # Ensure all columns are lowercase
    main_df.rename(columns = lambda x:x.lower(), inplace = True)

    joining_df.rename(columns = lambda x:x.lower(), inplace = True)

    # strip the whitespace and lowercase all values in column

    main_df[merge_column] = main_df[merge_column].str.strip().str.lower()

    joining_df[merge_column] = joining_df[merge_column].str.strip().str.lower()

    merged_df = main_df.merge(joining_df, on = merge_column ,how = 'left')

    return merged_df


def Previous_CROME_processing(crome_df,crop_lookup):

    crome_df.rename(columns = lambda x:x.lower(), inplace = True)

    crop_lookup.rename(columns = lambda x:x.lower(), inplace = True)

    crome_df = crome_df.loc[:,['cromeid', 'lucode']]

    crome_df_2 = merge_dfs(main_df = crome_df, joining_df= crop_lookup, merge_column='lucode')


    crome_df_3 = crome_df_2.loc[:,['lucode','cromeid', 'crome crop name','crop group id', 'crop type id']]

    rename_column_dict = {
      "lucode": "previous_crop_lucode",
      "crop group id" : "previous crop group id",
      "crop type id" : "previous crop type id",
      "crome crop name" : "previous crome crop name"
    }

    crome_df_3.rename(columns = rename_column_dict, inplace = True)

    return crome_df_3




def annual_rainfall_processing(rainfall_df, year):

    rainfall_df.dropna(subset = ['rainfall'], inplace = True)

    # the rainfall data has both current and previous year data, we specify which year we want
    rainfall_df['Year'] = rainfall_df['time_bnds'].dt.year

    rainfall_df_2 = rainfall_df[rainfall_df['Year'] == year]


    return rainfall_df_2


def monthly_rainfall_processing(rainfall_df, months : list):

    rainfall_df.dropna(subset = ['rainfall'], inplace = True)

    # monthly data comes with time bands 1 and 0
    # the rainfall is same for both time bands, so should be okay to select timeband 1. Further research needed for clarification on time bands
    rainfall_df_2 = rainfall_df[rainfall_df['bnds'] == 1].copy()

    rainfall_df_2.reset_index(inplace= True)
    # we slice for the months we are interested in
    rainfall_df_3 = rainfall_df_2[rainfall_df_2['month_number'].isin(months)].copy()

    return rainfall_df_3

def rainfall_agg_to_gpd(rainfall_df):

    # convert rainfall df to gdf using long and lat to form an active geometry
    rainfall_gdf = gpd.GeoDataFrame(rainfall_df, geometry = gpd.points_from_xy(rainfall_df['longitude'],rainfall_df['latitude'] ))
    #we need the sum of specified month rainfalls per geometry
    rainfall_gdf_2 = rainfall_gdf.groupby('geometry').agg({"rainfall": 'sum'})

    rainfall_gdf_2.reset_index(inplace = True)

    # we must ensure 4326 crs is maintained for all gdf for consistency

    rainfall_gdf_2 = gpd.GeoDataFrame(rainfall_gdf_2, geometry=rainfall_gdf_2["geometry"], crs='EPSG:4326')

    return rainfall_gdf_2


def merge_agg_rainfall(rainfall_1, rainfall_2):

    # we shall merge the rainfall sum from last year with current year, the geometry must be exact match
    rainfall_merged = spatial_join(main_gdf = rainfall_1, joining_df = rainfall_2, predicate = 'intersects' )

    rainfall_merged['oct_to_march_rainfall'] = rainfall_merged["rainfall_left"] + rainfall_merged["rainfall_right"]

    return rainfall_merged

def spatial_join(*,main_gdf,joining_gdf,predicate):

    merged_gdf = gpd.sjoin(main_gdf, joining_gdf, how='left', predicate= predicate)

    return merged_gdf

def point_to_grid(rainfall_gdf, gdf_grid):


    gdf_grid = gdf_grid.to_crs(4326)

    #we project the rainfall gdf to the grid geometry by merging spatially with 'within" condition
    rainfall_grid = spatial_join(main_gdf = rainfall_gdf, joining_gdf = gdf_grid,  predicate = 'within')

    return rainfall_grid


def sowing_date(df, sowing_month,sowing_day, sowing_year, current_year):

    # check which crop has sowing year is current year and which is prev year and assign accordingly
    df['year'] = np.where(df['sowing_year'] == 'current year', current_year, current_year - 1)

    df.rename(columns ={sowing_month : "month", sowing_day : "day"}, inplace = True)

    df["sowingdate"] = pd.to_datetime(df[['year','month','day']])
    # RB209 needs the sowing date in this timestamp format
    df['sowingdate'] = df['sowingdate'].dt.strftime("%Y-%m-%dT00:00:00")

    return df

def get_zipcode(df, geolocator, lat_field, lon_field):
  # use geolocator to obtain zipcode
  try:
    location = geolocator.reverse((df[lat_field], df[lon_field]))
    return location.raw['address']['postcode']
  except (AttributeError, KeyError, ValueError):
    print(df[lat_field], df[lon_field])
    return None

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


def map_SNS_index(df, SNS_mapping):
  # Iterate through the DataFrame rows

  sns_indice = []

  for index, row in df.iterrows():
    # Get the values from the row
    prev_crop_group_id = row['previous crop group id']
    soil_text = row['soiltypename_x']
    rainfall_level = row['rainfall_encoded']
    # Get the SNS index from the mapping dictionary
    SNS_index = SNS_mapping.get(rainfall_level, {}).get(prev_crop_group_id, {}).get(soil_text, 0)
    # Add the SNS index to the DataFrame
    sns_indice.append(SNS_index)

  df["sns_index"] = sns_indice
  return df

##### RAINFALL ENCODER


def rainfall_encoder(df, annual_rain_column):
    # (1,2,3) = low,medium and high rainfall
    bins = [0, 600, 700 ,float('inf')]
    labels = [1, 2, 3]

    # Encode rainfall based on bins and labels
    df['rainfall_encoded'] = pd.cut(df[annual_rain_column], bins=bins, labels=labels, right=False)

    return df

#### IMPUTE NULLS BASED ON FORWARD AND BACKWARD FILL AVERAGE

def impute_nulls_with_avg(df, column_name):
    #this ensures the missing data is imputed based on the neighboring geometry data
    # Forward fill null values
    df['forward_fill'] = df[column_name].ffill()
    # Backward fill null values
    df['backward_fill'] = df[column_name].bfill()
    # Calculate average of forward and backward filled values
    df['imputed_value'] = (df['forward_fill'] + df['backward_fill']) / 2
    # Update original column with imputed values
    df[column_name] = df['imputed_value']
    # Drop intermediate columns
    df.drop(columns=['forward_fill', 'backward_fill', 'imputed_value'], inplace=True)
    return df
