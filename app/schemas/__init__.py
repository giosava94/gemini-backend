"""
Schema package — re-exports all public symbols so that existing
`from app.schemas import X` imports continue to work unchanged.
"""

from app.schemas.common import (
    NonEmptyStr,
    StatusEnum,
    HealthResponse,
)

from app.schemas.beam_lines import (
    BeamLineCreate,
    BeamLineData,
    BeamLineDetailResponse,
    BeamLineListResponse,
    BeamLineUpdate,
    LinksModel,
)

from app.schemas.line_item_adjacents import (
    ADJ_POS_LOOKUP,
    AdjacentPosition,
    LineItemAdjacent,
    LineItemAdjacentData,
    LineItemAdjacentPatch,
    LineItemAdjacentsDelete,
    LineItemAdjacentsListResponse,
    LineItemAdjacentsUpdate,
)

from app.schemas.line_items import (
    LINE_ITEM_KIND_LOOKUP,
    LineItemCreate,
    LineItemCreateResponse,
    LineItemData,
    LineItemDetailData,
    LineItemDetailResponse,
    LineItemKind,
    LineItemLinksModel,
    LineItemListResponse,
    LineItemStatus,
    LineItemUpdate,
)

from app.schemas.line_item_connections import (
    LineItemConnectionData,
    LineItemConnectionsDelete,
    LineItemConnectionsListResponse,
    LineItemConnectionsUpdate,
)

from app.schemas.items import (
    ITEM_KIND_LOOKUP,
    ItemCreate,
    ItemCreateResponse,
    ItemData,
    ItemDetailData,
    ItemDetailResponse,
    ItemKind,
    ItemLinksModel,
    ItemListResponse,
    ItemStatus,
    ItemUpdate,
)

from app.schemas.item_connections import (
    ItemConnectionData,
    ItemConnectionsDelete,
    ItemConnectionsListResponse,
    ItemConnectionsUpdate,
    ItemLineItemConnectionData,
    ItemLineItemConnectionsListResponse,
)

__all__ = [
    # common
    "NonEmptyStr",
    "StatusEnum",
    "HealthResponse",
    # beam lines
    "BeamLineCreate",
    "BeamLineData",
    "BeamLineDetailResponse",
    "BeamLineListResponse",
    "BeamLineUpdate",
    "LinksModel",
    # line item adjacents
    "ADJ_POS_LOOKUP",
    "AdjacentPosition",
    "LineItemAdjacent",
    "LineItemAdjacentData",
    "LineItemAdjacentPatch",
    "LineItemAdjacentsDelete",
    "LineItemAdjacentsListResponse",
    "LineItemAdjacentsUpdate",
    # line items
    "LINE_ITEM_KIND_LOOKUP",
    "LineItemCreate",
    "LineItemCreateResponse",
    "LineItemData",
    "LineItemDetailData",
    "LineItemDetailResponse",
    "LineItemKind",
    "LineItemLinksModel",
    "LineItemListResponse",
    "LineItemStatus",
    "LineItemUpdate",
    # line item connections
    "LineItemConnectionData",
    "LineItemConnectionsDelete",
    "LineItemConnectionsListResponse",
    "LineItemConnectionsUpdate",
    # items
    "ITEM_KIND_LOOKUP",
    "ItemCreate",
    "ItemCreateResponse",
    "ItemData",
    "ItemDetailData",
    "ItemDetailResponse",
    "ItemKind",
    "ItemLinksModel",
    "ItemListResponse",
    "ItemStatus",
    "ItemUpdate",
    # item connections
    "ItemConnectionData",
    "ItemConnectionsDelete",
    "ItemConnectionsListResponse",
    "ItemConnectionsUpdate",
    "ItemLineItemConnectionData",
    "ItemLineItemConnectionsListResponse",
]
