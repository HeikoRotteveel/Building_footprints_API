import duckdb
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import json
from schemas import Collections, Buildings, Feature
from paginator import Paginator
from contextlib import asynccontextmanager

con = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the database
    global con
    con = duckdb.connect("buildings_database.db")
    con.install_extension("spatial")
    con.load_extension("spatial")
    yield
    # Close the database and release the resources
    con.close()

app = FastAPI(lifespan=lifespan)

####################################
#####  GLOBAL ERROR HANDLERS  ######
####################################

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal Server Error: {str(exc)}"}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()}
    )

def offset_limit_errors(limit, offset):
    if limit > 1000:
        raise HTTPException(400, "Max. limit is 1000")

    if limit <= 0:
        raise HTTPException(400, "Limit cannot be <= 0")

    if offset < 0:
        raise HTTPException(400, "Offset cannot be <0")

def bbox_errors(xmin, ymin, xmax, ymax):
    if xmin >= xmax:
        raise HTTPException(400, "xmin must be < xmax")
    if ymin >= ymax:
        raise HTTPException(400, "ymin must be < ymax")

####################################
###########  ENDPOINTS  ############
####################################

@app.get("/collections",  response_model=Collections)
async def read_municipalities(request: Request, limit: int = 50, offset: int = 0):

    offset_limit_errors(limit, offset)

    try:
        df = con.execute(f"""
            SELECT naam, building_count 
            FROM municipalities
            ORDER BY naam
            LIMIT ?
            OFFSET ?;
        """,[limit,offset]).fetchdf()

        total_count = con.execute("""
            SELECT COUNT(*) FROM municipalities;
        """).fetchone()[0]

    except Exception as e:
        raise HTTPException(500, f"Database query failed: {str(e)}")

    if df.empty:
        raise HTTPException(404, "No municipalities found")

    data = df.to_dict(orient="records")
    paginator = Paginator(request, limit, offset, total_count)

    return {
        "meta": {
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "returned_features": len(data),
            "previous": paginator.previous(),
            "next": paginator.next()
        },
        "data": data
    }

@app.get("/collections/{municipality}/items", response_model=Buildings)
async def buildings_in_municipality(request: Request, municipality: str, limit: int = 50, offset: int = 0):
    offset_limit_errors(limit, offset)

    try:
        res = con.execute(f""" 
            SELECT id, ST_AsGeoJSON(geometry) AS geom_json 
            FROM buildings 
            WHERE municipality_name = ? 
            LIMIT ? 
            OFFSET ?; 
            """,[municipality, limit, offset]).fetchdf()

        total_count = con.execute(f""" 
            SELECT COUNT(*) FROM buildings WHERE municipality_name = ?; 
        """,[municipality]).fetchone()[0]


    except Exception as e:
        raise HTTPException(500, f"Database query failed: {str(e)}")

    if res.empty:
        raise HTTPException(404, f"No buildings found in {municipality}")

    features = []
    for _, row in res.iterrows():
        geom = json.loads(row["geom_json"])

        feature = { "type": "Feature",
                    "geometry": geom,
                    "properties": {
                        "id": row["id"],
                        "municipality_name": municipality }
                    }

        features.append(feature)


    feature_collection = { "type": "FeatureCollection",
                           "features": features }



    paginator = Paginator(request, limit, offset, total_count)

    return {"meta":
                 { "total_count": total_count,
                   "limit": limit,
                   "offset": offset,
                   "returned_features": len(features),
                   "previous": paginator.previous(),
                   "next": paginator.next() },
             "data": feature_collection }

@app.get("/collections/{municipality}/items/{building_id}", response_model=Feature)
async def building_in_municipality(municipality: str, building_id: str):

    try:
        df = con.execute("""
                SELECT id, ST_AsGeoJSON(geometry) AS geom_json
                FROM buildings
                WHERE municipality_name = ? AND id = ?;
            """, [municipality, building_id]).fetchdf()
    except Exception as e:
        raise HTTPException(500, f"Database query failed: {str(e)}")

    if df.empty:
        raise HTTPException(404, "Building not found")

    return {
        "type": "Feature",
        "geometry": json.loads(df["geom_json"][0]),
        "properties": {
            "id": df["id"][0],
            "municipality_name": municipality
        }
    }

@app.get("/buildings/bbox", response_model=Buildings)
async def buildings_in_bbox(request: Request, xmin: float = 78600.0, ymin: float = 445000.0,
                                              xmax: float = 85800.0, ymax: float = 450000.0,
                                              limit: int = 50, offset: int = 0):

    offset_limit_errors(limit, offset)
    bbox_errors(xmin, ymin, xmax, ymax)

    try:
        df = con.execute("""
                SELECT id, ST_AsGeoJSON(geometry) AS geom_json,
                       municipality_name, bbox
                FROM buildings
                WHERE
                    bbox.xmin >= ? AND bbox.xmax <= ? AND
                    bbox.ymin >= ? AND bbox.ymax <= ?
                LIMIT ?
                OFFSET ?;
            """, [xmin, xmax, ymin, ymax, limit, offset]).fetchdf()

        total_count = con.execute("""
                SELECT COUNT(*) FROM buildings;
            """).fetchone()[0]

    except Exception as e:
        raise HTTPException(500, f"Database query failed: {str(e)}")

    if df.empty:
        raise HTTPException(404, "No buildings found in bbox")

    features = [
        {
            "type": "Feature",
            "geometry": json.loads(row["geom_json"]),
            "properties": {
                "id": row["id"],
                "municipality_name": row["municipality_name"],
            },
        }
        for _, row in df.iterrows()
    ]

    paginator = Paginator(request, limit, offset, total_count)

    return {
        "meta": {
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "returned_features": len(features),
            "previous": paginator.previous(),
            "next": paginator.next()
        },
        "data": {"type": "FeatureCollection", "features": features}
    }
