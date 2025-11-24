import duckdb
from pyproj import Transformer
import requests
import json


con = None

def setup_duckdb(db_name = "buildings_database.db", extensions = ['spatial'] ):
    # SETTING UP DUCKDB
    global con
    con = duckdb.connect(db_name)
    print(f"-> Connected to {db_name}")

    for extension in extensions:
        con.install_extension(extension)
        con.load_extension(extension)
        print(f"-> Extension {extension} added")

def crs_transform(crs_from = 28992, crs_to = 4326, bbox = [(78600.0, 445000.0), (85800.0, 450000.0)]):
    #BBOX in EPSG:28992
    minx, miny = bbox[0]
    maxx, maxy = bbox[1]

    print(f"-> Transforming {bbox[0]} and {bbox[1]} from CRS {crs_from} to CRS {crs_to}")

    # Convert to Lon-Lat
    reproject = Transformer.from_crs(crs_from, crs_to, always_xy=True)
    minx, miny = reproject.transform(minx, miny)
    maxx, maxy = reproject.transform(maxx, maxy)

    print(f"-> Successfully transformed to {(minx, miny)} and {(maxx, maxy)}")

    return (minx, miny), (maxx, maxy)

def retrieve_buildings(minx, miny, maxx, maxy):
    print(f"-> Retrieving buildings in BBOX {minx, miny}, {maxx, maxy}")

    # SQL script to retrieve buildings from overturemaps
    sql_buildings = f"""
    CREATE TABLE IF NOT EXISTS buildings AS                            
          SELECT id, geometry, bbox
          FROM read_parquet('s3://overturemaps-us-west-2/release/2025-10-22.0/theme=buildings/type=building/*', filename=true, hive_partitioning=1)
          WHERE bbox.xmin BETWEEN {minx} AND {maxx} AND bbox.ymin BETWEEN {miny} AND {maxy};
    """

    con.sql(sql_buildings)
    count = con.sql("SELECT COUNT(*) FROM buildings")
    print(f"-> Successfully retrieved {count} buildings")

def transform_geometry_values(from_crs="4326", to_crs="28992"):
    transform_geometry = f"""
    UPDATE buildings
    SET geometry = ST_Transform(
        ST_FLIPCOORDINATES(geometry),
        'EPSG:{from_crs}',
        'EPSG:{to_crs}'
    );
    """
    print(f"-> Transforming geometry from EPSG:{from_crs} to EPSG:{to_crs} ")
    con.sql(transform_geometry)

    transform_bbox = f"""
        UPDATE buildings
        SET bbox = (SELECT STRUCT_PACK(
            xmin := ST_X(min),
            xmax := ST_X(max),
            ymin := ST_Y(min),
            ymax := ST_Y(max))
        FROM (SELECT
            ST_Transform(ST_FLIPCOORDINATES(ST_Point(bbox.xmin, bbox.ymin)),'EPSG:{from_crs}', 'EPSG:{to_crs}') AS min,
            ST_Transform(ST_FLIPCOORDINATES(ST_Point(bbox.xmax, bbox.ymax)),'EPSG:{from_crs}', 'EPSG:{to_crs}') AS max)
        );"""
    print(f"-> Transforming bbox from EPSG:{from_crs} to EPSG:{to_crs} ")
    con.sql(transform_bbox)

    print(f"-> Successfully transformed from EPSG:{from_crs} to EPSG:{to_crs} ")

def retrieve_municipalities(province_name = 'Zuid-Holland'):
    print(f"-> Retrieving municipalities from {province_name}")
    url = f"https://api.pdok.nl/kadaster/bestuurlijkegebieden/ogc/v1/collections/gemeentegebied/items?crs=http%3A%2F%2Fwww.opengis.net%2Fdef%2Fcrs%2FEPSG%2F0%2F28992&f=json&ligt_in_provincie_naam={province_name}&limit=100"
    response = requests.get(url)
    print(f"-> Status code of response: {response.status_code}")
    with open("gemeentegebied.json", "w") as f:
        json.dump(response.json()['features'], f)

    load_data_into_db = f"""
    CREATE TABLE IF NOT EXISTS municipalities AS SELECT * FROM 'gemeentegebied.json';
    """

    print("-> Loading response into database")
    con.sql(load_data_into_db)

    # Unpacking all the properties
    columns = ["code", "identificatie", "ligt_in_provincie_code", "ligt_in_provincie_naam", "naam"]

    for col in columns:
        con.sql(f"ALTER TABLE municipalities ADD COLUMN IF NOT EXISTS {col} TEXT;")

    con.sql("""
    UPDATE municipalities
    SET
        code = properties ->> 'code',
        identificatie = properties ->> 'identificatie',
        ligt_in_provincie_code = properties ->> 'ligt_in_provincie_code',
        ligt_in_provincie_naam = properties ->> 'ligt_in_provincie_naam',
        naam = properties ->> 'naam';
    """)
    print("-> Unpacking properties")

    print("-> Removing properties column")
    drop_properties = """
    ALTER TABLE municipalities DROP COLUMN properties;
    """

    con.sql(drop_properties)

def match_building_and_municipality():
    print("-> Adding municipality_name column to TABLE buildings")
    add_column_municipality = """
    ALTER TABLE buildings ADD COLUMN IF NOT EXISTS municipality_name TEXT;
    """
    con.sql(add_column_municipality)

    add_municipality_name = """
    UPDATE buildings AS b
    SET municipality_name =
    (
        SELECT m.naam
        FROM municipalities m
        WHERE ST_Intersects(b.geometry, ST_GeomFromGeoJSON(m.geometry))
        LIMIT 1
    );
    """
    con.sql(add_municipality_name)
    print("-> Successfully added municipality information to the buildings")

    print("-> Adding building_count column to TABLE municipalities")
    add_column_building_count = """
    ALTER TABLE municipalities ADD COLUMN IF NOT EXISTS building_count INTEGER;
    """
    con.sql(add_column_building_count)

    print("-> Counting the number of buildings per municipality")
    counting_buildings = """
    UPDATE municipalities AS m
    SET building_count = (
        SELECT COUNT(*)
        FROM buildings b
        WHERE b.municipality_name = m.naam);
    """
    con.sql(counting_buildings)


def main():
    setup_duckdb()
    (minx, miny), (maxx, maxy) = crs_transform()
    retrieve_buildings(minx, miny, maxx, maxy)
    transform_geometry_values()
    retrieve_municipalities()
    match_building_and_municipality()
    print("-> The DuckDB database has been successfully created")
    con.close()

main()



