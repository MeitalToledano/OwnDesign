// Generic furniture and fixtures with typical dimensions in centimetres (width x depth).
// `review` marks wet-area and kitchen fixtures: moving them is conceptual until a professional reviews it.
// backend/app/catalog.py holds the same list (layout suggestions); a backend test fails if the two differ.
export const FURNITURE = [
  { type: "sofa", label: "Sofa", group: "Living", w: 200, d: 90 },
  { type: "armchair", label: "Armchair", group: "Living", w: 85, d: 85 },
  { type: "coffee-table", label: "Coffee table", group: "Living", w: 110, d: 60 },
  { type: "tv-unit", label: "TV unit", group: "Living", w: 160, d: 45 },
  { type: "dining-table", label: "Dining table", group: "Living", w: 160, d: 90 },
  { type: "chair", label: "Chair", group: "Living", w: 45, d: 45 },
  { type: "double-bed", label: "Double bed", group: "Bedroom", w: 160, d: 200 },
  { type: "single-bed", label: "Single bed", group: "Bedroom", w: 90, d: 200 },
  { type: "bedside-table", label: "Bedside table", group: "Bedroom", w: 45, d: 40 },
  { type: "wardrobe", label: "Wardrobe", group: "Bedroom", w: 180, d: 60 },
  { type: "desk", label: "Desk", group: "Bedroom", w: 120, d: 60 },
  { type: "kitchen-counter", label: "Counter", group: "Kitchen", w: 240, d: 60, review: true },
  { type: "kitchen-island", label: "Island", group: "Kitchen", w: 180, d: 90, review: true },
  { type: "sink", label: "Sink", group: "Kitchen", w: 80, d: 60, review: true },
  { type: "stove", label: "Stove", group: "Kitchen", w: 60, d: 60, review: true },
  { type: "fridge", label: "Fridge", group: "Kitchen", w: 70, d: 70 },
  { type: "toilet", label: "Toilet", group: "Bathroom", w: 40, d: 65, review: true },
  { type: "bathtub", label: "Bathtub", group: "Bathroom", w: 170, d: 75, review: true },
  { type: "shower", label: "Shower", group: "Bathroom", w: 90, d: 90, review: true },
  { type: "vanity", label: "Vanity", group: "Bathroom", w: 80, d: 50, review: true },
];

export const FURNITURE_BY_TYPE = new Map(FURNITURE.map((item) => [item.type, item]));

export const ROOM_TYPES = [
  ["living", "Living room"],
  ["kitchen", "Kitchen"],
  ["bedroom", "Bedroom"],
  ["bathroom", "Bathroom"],
  ["hallway", "Hallway"],
  ["balcony", "Balcony"],
  ["other", "Other"],
];

export const REVIEW_NOTE =
  "Changes to walls, openings, kitchens and bathrooms are conceptual until reviewed by a qualified professional.";
