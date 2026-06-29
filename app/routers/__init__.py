"""Router package for the Gemini backend API.

Each sub-module registers a FastAPI ``APIRouter`` that is included in the
main application.  The available routers are:

- ``beam_lines``       — CRUD for BeamLine nodes
- ``line_items``       — CRUD for LineItem nodes scoped to a beam line
- ``line_item_adjacents``   — manage PREVIOUS/NEXT adjacency relationships
- ``line_item_connections`` — manage CONNECTED_TO edges between line items and items
- ``items``            — CRUD for non-line Item nodes
- ``item_connections`` — manage CONNECTED_TO edges between items
"""
