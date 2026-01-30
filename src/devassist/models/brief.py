"""Brief models for DevAssist.

Defines the structure of the Unified Morning Brief output.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from devassist.models.context import SourceType


class BriefItem(BaseModel):
    """A single item in the brief."""

    id: str = Field(..., description="Original item ID")
    source_type: SourceType = Field(..., description="Source of this item")
    title: str = Field(..., description="Item title/subject")
    summary: str | None = Field(None, description="AI-generated summary of this item")
    relevance_score: float = Field(..., description="Computed relevance score")
    url: str | None = Field(None, description="Link to original item")
    author: str | None = Field(None, description="Who created/sent item")
    timestamp: datetime = Field(..., description="When item was created")

    # Legacy method removed - not used in MCP-based architecture
    # from_context_item: Replaced by direct Claude API aggregation via MCP


class BriefSection(BaseModel):
    """A section of the brief grouping items by source."""

    source_type: SourceType = Field(..., description="Source type for this section")
    display_name: str = Field(..., description="Human-readable section name")
    items: list[BriefItem] = Field(default_factory=list, description="Items in this section")
    item_count: int = Field(0, description="Total items in section")

    @property
    def has_items(self) -> bool:
        """Check if section has any items."""
        return len(self.items) > 0


class Brief(BaseModel):
    """The complete Unified Morning Brief."""

    summary: str = Field(..., description="AI-generated executive summary")
    sections: list[BriefSection] = Field(default_factory=list, description="Sections by source")
    generated_at: datetime = Field(
        default_factory=datetime.now,
        description="When brief was generated",
    )
    total_items: int = Field(0, description="Total items across all sections")
    sources_queried: list[SourceType] = Field(
        default_factory=list,
        description="Sources that were queried",
    )
    sources_failed: list[str] = Field(
        default_factory=list,
        description="Sources that failed to respond",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata (e.g., session_id)",
    )

    @property
    def has_errors(self) -> bool:
        """Check if any sources failed."""
        return len(self.sources_failed) > 0

    def get_section(self, source_type: SourceType) -> BriefSection | None:
        """Get section for a specific source type.

        Args:
            source_type: Source type to find.

        Returns:
            BriefSection or None if not found.
        """
        for section in self.sections:
            if section.source_type == source_type:
                return section
        return None


class BriefSummary(BaseModel):
    """AI-generated summary response structure."""

    executive_summary: str = Field(..., description="High-level summary paragraph")
    action_items: list[str] = Field(default_factory=list, description="Suggested action items")
    highlights: list[str] = Field(default_factory=list, description="Key highlights")
    priorities: list[str] = Field(default_factory=list, description="Suggested priorities")
