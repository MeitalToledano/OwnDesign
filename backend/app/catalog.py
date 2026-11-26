"""Design styles and finish materials: the single source of truth for validation and for GET /v1/catalog."""

SURFACES = ("floor", "walls", "ceiling", "cabinets")

STYLES = [
    {"id": "modern", "label": "Modern", "description": "Clean lines, neutral palette, little ornament."},
    {"id": "scandinavian", "label": "Scandinavian", "description": "Light woods, white walls, cosy textiles."},
    {"id": "industrial", "label": "Industrial", "description": "Raw concrete, black metal, exposed texture."},
    {"id": "mid-century", "label": "Mid-century", "description": "Warm teak, tapered legs, bold accents."},
    {"id": "japandi", "label": "Japandi", "description": "Calm minimalism with natural, handmade materials."},
    {"id": "classic", "label": "Classic", "description": "Symmetry, mouldings and timeless furniture."},
    {"id": "mediterranean", "label": "Mediterranean", "description": "Terracotta, lime plaster and sunlit tones."},
    {"id": "bohemian", "label": "Bohemian", "description": "Layered patterns, plants and collected pieces."},
]

# `surfaces`: where the material can be applied. `color`: swatch shown in the UI.
MATERIALS = [
    {"id": "oak-floor", "label": "Natural oak", "surfaces": ["floor", "cabinets"], "color": "#c9a46b"},
    {"id": "walnut-floor", "label": "Walnut", "surfaces": ["floor", "cabinets"], "color": "#6b4a32"},
    {"id": "polished-concrete", "label": "Polished concrete", "surfaces": ["floor", "walls"], "color": "#9a9a97"},
    {"id": "porcelain-stone", "label": "Stone-look porcelain", "surfaces": ["floor", "walls"], "color": "#b8b2a7"},
    {"id": "terracotta-tile", "label": "Terracotta tile", "surfaces": ["floor", "walls"], "color": "#b9573a"},
    {"id": "white-paint", "label": "Warm white paint", "surfaces": ["walls", "ceiling", "cabinets"], "color": "#f3efe6"},
    {"id": "sage-paint", "label": "Sage green paint", "surfaces": ["walls", "cabinets"], "color": "#9caf88"},
    {"id": "navy-paint", "label": "Deep navy paint", "surfaces": ["walls", "cabinets"], "color": "#26364f"},
    {"id": "lime-plaster", "label": "Lime plaster", "surfaces": ["walls"], "color": "#e4dccb"},
    {"id": "black-metal", "label": "Black metal", "surfaces": ["cabinets"], "color": "#2b2b2b"},
]

STYLE_IDS = frozenset(style["id"] for style in STYLES)
MATERIALS_BY_ID = {material["id"]: material for material in MATERIALS}

# Generic furniture, width x depth in cm. The same list as frontend/js/catalog.js, which the editor needs
# offline for guests; tests/test_layout.py fails if the two drift apart. `review`: kitchen and wet-area fixtures.
FURNITURE = [
    {"type": "sofa", "label": "Sofa", "w": 200, "d": 90},
    {"type": "armchair", "label": "Armchair", "w": 85, "d": 85},
    {"type": "coffee-table", "label": "Coffee table", "w": 110, "d": 60},
    {"type": "tv-unit", "label": "TV unit", "w": 160, "d": 45},
    {"type": "dining-table", "label": "Dining table", "w": 160, "d": 90},
    {"type": "chair", "label": "Chair", "w": 45, "d": 45},
    {"type": "double-bed", "label": "Double bed", "w": 160, "d": 200},
    {"type": "single-bed", "label": "Single bed", "w": 90, "d": 200},
    {"type": "bedside-table", "label": "Bedside table", "w": 45, "d": 40},
    {"type": "wardrobe", "label": "Wardrobe", "w": 180, "d": 60},
    {"type": "desk", "label": "Desk", "w": 120, "d": 60},
    {"type": "kitchen-counter", "label": "Counter", "w": 240, "d": 60, "review": True},
    {"type": "kitchen-island", "label": "Island", "w": 180, "d": 90, "review": True},
    {"type": "sink", "label": "Sink", "w": 80, "d": 60, "review": True},
    {"type": "stove", "label": "Stove", "w": 60, "d": 60, "review": True},
    {"type": "fridge", "label": "Fridge", "w": 70, "d": 70},
    {"type": "toilet", "label": "Toilet", "w": 40, "d": 65, "review": True},
    {"type": "bathtub", "label": "Bathtub", "w": 170, "d": 75, "review": True},
    {"type": "shower", "label": "Shower", "w": 90, "d": 90, "review": True},
    {"type": "vanity", "label": "Vanity", "w": 80, "d": 50, "review": True},
]
FURNITURE_BY_TYPE = {item["type"]: item for item in FURNITURE}

# The furniture a layout request starts with, per room type (the client edits the list before asking).
ROOM_DEFAULTS = {
    "living": [("sofa", 1), ("armchair", 1), ("coffee-table", 1), ("tv-unit", 1)],
    "bedroom": [("double-bed", 1), ("bedside-table", 2), ("wardrobe", 1)],
    "kitchen": [("kitchen-counter", 1), ("sink", 1), ("stove", 1), ("fridge", 1)],
    "bathroom": [("toilet", 1), ("vanity", 1), ("shower", 1)],
    "hallway": [],
    "balcony": [("chair", 2)],
    "other": [("desk", 1), ("chair", 1)],
}
