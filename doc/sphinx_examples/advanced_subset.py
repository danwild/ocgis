import os.path

from ocgis import OcgOperations, RequestDataset, RequestDatasetCollection, env


# Directory holding climate data.
DATA_DIR = '/usr/local/climate_data/CanCM4'
# Filename to variable name mapping.
NCS = {'tasmin_day_CanCM4_decadal2000_r2i1p1_20010101-20101231.nc': 'tasmin',
       'tas_day_CanCM4_decadal2000_r2i1p1_20010101-20101231.nc': 'tas',
       'tasmax_day_CanCM4_decadal2000_r2i1p1_20010101-20101231.nc': 'tasmax'}
# Always start with a snippet (if there are no calculations!).
SNIPPET = True
# Data returns will overwrite in this case. Use with caution!!
env.OVERWRITE = True


# RequestDatasetCollection #############################################################################################

rdc = RequestDatasetCollection([RequestDataset(
    os.path.join(DATA_DIR, uri), var) for uri, var in NCS.iteritems()])

# Return In-Memory #####################################################################################################

# Data is returned as a dictionary-like object (SpatialCollection) with 51 keys (don't forget Puerto Rico...). A key in 
# the returned dictionary corresponds to a geometry "ugid" with the value of type OcgCollection.
print('returning numpy...')
ops = OcgOperations(dataset=rdc, spatial_operation='clip', aggregate=True, snippet=SNIPPET, geom='state_boundaries')
ret = ops.execute()

# Return a SpatialCollection, but only for a target state in a U.S. state boundaries shapefile. In this case, the UGID 
# attribute value of 23 is associated with Nebraska.

print('returning numpy for a state...')
ops = OcgOperations(dataset=rdc, spatial_operation='clip', aggregate=True, snippet=SNIPPET, geom='state_boundaries',
                    select_ugid=[23])
ret = ops.execute()

# Write to Shapefile ###################################################################################################

print('returning shapefile...')
ops = OcgOperations(dataset=rdc, spatial_operation='clip', aggregate=True, snippet=SNIPPET, geom='state_boundaries',
                    output_format='shp')
path = ops.execute()

# Write All Data to Keyed Format #######################################################################################

# Without the snippet, we are writing all data to the linked CSV-Shapefile output format. The operation will take 
# considerably longer.
print('returning csv-shp...')
ops = OcgOperations(dataset=rdc, spatial_operation='clip', aggregate=True, snippet=False, geom='state_boundaries',
                    output_format='csv-shp')
path = ops.execute()