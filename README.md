# Building Footprints RESTful API

A small repository with Python code of a RESTful API for serving building footprint data from the South Holland region in the Netherlands. The Python code downloads open geospatial data, stores it in a spatial database, and creates a web API to serve the data with various filtering options.

---
## Study Area
**Region:** South Holland (Zuid-Holland), Netherlands

**Bounding  Box  in EPSG:28992 (Amersfoort / RD New):**
```
minx = 78600.0 
miny = 445000.0
maxx = 85800.0
maxy = 450000.0
```

![study_area.png](study_area.png)

---

## Installation

---

1. Clone the repository:

```bash
git clone https://github.com/HeikoRotteveel/Building_footrpints_API
cd Building_footrpints_API
```

2. Create a virtual environment (recommended):
```
python -m venv venv
source venv/bin/activate      # Linux/Mac
venv\Scripts\activate         # Windows
```

3. Install dependencies:
```
pip install -r requirements.txt
```

## Overview

---

Now that you have downloaded all the files and the required libraries, you can start using it! The repository includes everything needed for the complete workflow from raw data import to final API launch. This part will guide you through what steps the program takes and what all the different files do.

## **Project structure**

---
```
.
├── buildings_database.db       # DuckDB database with geometry + bbox columns
├── gemeentegebied.json         # JSON file of municipalities in Zuid-Holland
├── main.py                     # The API code
├── schemas.py                  # Pydantic response models
├── paginator.py                # Pagination helper
├── requirements.txt            # Requirements
└── README.md                   # Project documentation
```

## **Main steps - Backend setup**

---
1. **Setting up DuckDB**
   - Creates a .db file called ['buildings_database.db'](buildings_database.db)
   - Installs and loads the 'Spatial' extension
2. **Transforming coordinates**
   - Transforms the area of interest bbox from ESPG:28992 to EPSG:4326
3. **Retrieving buildings**
    - Retrieves the building data in EPSG:4326 from ['Overture']('s3://overturemaps-us-west-2/release/2025-10-22.0/theme=buildings/type=building/*) and loads it into the database (TABLE buildings)
4. **Transforming buildings**
   - Transforms the 'geometry' and 'bbox' columns of the buildings TABLE from EPSG:4326 to EPSG:28992
5. **Retrieving municipalities**
    - Retrieves the municipality data of the Zuid-Holland province from ['PDOK'](https://api.pdok.nl/kadaster/bestuurlijkegebieden/ogc/v1/collections/gemeentegebied/items?crs=http%3A%2F%2Fwww.opengis.net%2Fdef%2Fcrs%2FEPSG%2F0%2F28992&f=json&ligt_in_provincie_naam=Zuid-Holland&limit=100) in EPSG:28992 and loads it into the database (TABLE municipalities)
6. **Matching building and municipality**
   - Adds 'municipality_name' as a column to the buildings TABLE if the building geometry and the municipality geometry intersect.
   - Each building can only have one municipality to its name, even if it crosses a border with another. The first municipality in the list that has an intersection will therefore be assigned, and all following overlaps are dropped.
   - Adds a 'building_count' column to the municipalities TABLE with the total number of buildings that are contained within the geometry of the municipality.



Running the backend setup with the following prompt in the terminal:
```
python 01_backend_setup.py
```
**You only need to run this function if you do not have the ['buildings_database.db'](buildings_database.db) or want to re-initialise it**, otherwise it does nothing.

## **Running the API**

---
After downloading the required data and setting up the DuckDB database, you can now run the API locally in development mode with the following prompt in the terminal:
```
fastapi dev 02_api.py
```

The API can now be accessed via [http://127.0.0.1:8000](http://127.0.0.1:8000) or with documentation at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). 

For production you can run:

```
fastapi run 02_api.py
```

## **API Endpoints**

---


**GET** `/collections`

Returns a list of all municipalities with building counts.

**Query Parameters:**
- Limit (default 50, max 1000)
- Offset (default 0)

**Example:**
```
curl "http://localhost:8000/collections?limit=20&offset=0"
```

---
**GET** `/collections/{municipality}/items`

Returns buildings inside a municipality as a FeatureCollection.

**Query Parameters:**
- Limit (default 50, max 1000)
- Offset (default 0)

**Example:**
```
curl "http://localhost:8000/collections/Delft/items?limit=20&offset=10"
```

---
**GET** `/collections/{municipality}/items`

Returns a single building as a GeoJSON Feature.

**Query Parameters:**
- Limit (default 50, max 1000)
- Offset (default 0)

**Example:**
```
curl "http://localhost:8000/collections/Delft/items/12345"
```

---
**GET** `/collections/{municipality}/items`

Returns a single building as a GeoJSON Feature.

**Query Parameters:**
- xmin, ymin, xmax, ymax
- Limit (default 50, max 1000)
- Offset (default 0)

**Example:**
```
curl "http://localhost:8000/buildings/bbox?xmin=78000&ymin=445000&xmax=85000&ymax=450000"
```