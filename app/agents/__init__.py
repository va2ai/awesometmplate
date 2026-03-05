"""Agents - compose tools to accomplish higher-level tasks.

Each agent has a specific role:
- researcher: Full directory research from a topic
- router: Routes topics to pages or sections (Haiku)
- merger: Adds content to existing sections (Sonnet)
- taxonomist: Checks section organization, proposes merges
- designer: Enhances visual theming after research (colors, icons, animations, block upgrades)
- block_designer: Creates new custom block types
"""

from .researcher import organize_with_claude
from .designer import design_directory
from .smart_adder import smart_add_with_claude
from .router import route_to_page
from .block_designer import create_new_block_type
