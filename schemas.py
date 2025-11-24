from pydantic import BaseModel, Field
from typing import List, Any, Optional

class Metadata(BaseModel):
    total_count: int = Field(..., example=500)
    limit: int = Field(..., example=50)
    offset: int = Field(..., example=0)
    returned_features: int = Field(..., example=50)
    previous: Optional[str] = Field(None, example="/collections?limit=50&offset=0")
    next: Optional[str] = Field(None, example="/collections?limit=50&offset=50")

# Schema for GET /collections
class Municipality(BaseModel):
    naam: str = Field(..., example="Amsterdam")
    building_count: int = Field(..., example=1234)

class Collections(BaseModel):
    meta: Metadata
    data: List[Municipality]

# Schema for GET /collections/{municipality/items}
class Building(BaseModel):
    id: str = Field(..., example="building_001")
    municipality_name: str = Field(..., example="Amsterdam")

class Geometry(BaseModel):
    type: str = Field(..., example="Polygon")
    coordinates: Any = Field(..., example=[[[0,0],[1,0],[1,1],[0,1],[0,0]]])

class Feature(BaseModel):
    type: str = Field(..., example="Feature")
    geometry: Geometry
    properties: Building

class FeatureCollection(BaseModel):
    type: str = Field(..., example="FeatureCollection")
    features: List[Feature]

class Buildings(BaseModel):
    meta: Metadata
    data: FeatureCollection

# Schema for GET /collections/{municipality/items}
# Returns basically a single feature

# Schema for GET /buildings/bbox
# Returns basically a Buildings collection
