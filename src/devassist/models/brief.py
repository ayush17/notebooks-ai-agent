"""Brief models for DevAssist.

Defines the structure of the Unified Morning Brief output.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from devassist.models.context import ContextItem, SourceType


class BriefItem(BaseModel):
    """A single item in the brief, derived from a ContextItem."""

    id: str = Field(..., description="Original item ID")
    source_type: SourceType = Field(..., description="Source of this item")
    title: str = Field(..., description="Item title/subject")
    summary: str | None = Field(None, description="AI-generated summary of this item")
    relevance_score: float = Field(..., description="Computed relevance score")
    url: str | None = Field(None, description="Link to original item")
    author: str | None = Field(None, description="Who created/sent item")
    timestamp: datetime = Field(..., description="When item was created")

    @classmethod
    def from_context_item(cls, item: ContextItem, summary: str | None = None) -> "BriefItem":
        """Create a BriefItem from a ContextItem.

        Args:
            item: Source ContextItem.
            summary: Optional AI-generated summary.

        Returns:
            New BriefItem instance.
        """
        return cls(
            id=item.id,
            source_type=item.source_type,
            title=item.title,
            summary=summary or item.content[:200] if item.content else None,
            relevance_score=item.relevance_score,
            url=item.url,
            author=item.author,
            timestamp=item.timestamp,
        )


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
