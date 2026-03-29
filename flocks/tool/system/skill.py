"""
Skill Tool - Load and execute skills

Loads skill files that provide specialized instructions for specific tasks.
Skills are markdown files with structured content.
Ported from original skill tool.
"""

import os
from typing import List

from flocks.tool.registry import (
    ToolRegistry, ToolCategory, ToolParameter, ParameterType, ToolResult, ToolContext
)
from flocks.skill.skill import Skill, SkillInfo
from flocks.utils.log import Log


log = Log.create(service="tool.skill")


def build_description(skills: List[SkillInfo]) -> str:
    """Build tool description with available skills"""
    if not skills:
        return "Load a skill to get detailed instructions for a specific task. No skills are currently available."
    
    # Match Flocks's format: space-separated, no newlines
    parts = [
        "Load a skill to get detailed instructions for a specific task.",
        "Skills provide specialized knowledge and step-by-step guidance.",
        "Use this when a task matches an available skill's description.",
        "<available_skills>",
    ]
    
    for skill in skills:
        parts.extend([
            "  <skill>",
            f"    <name>{skill.name}</name>",
            f"    <description>{skill.description}</description>",
            "  </skill>",
        ])
    
    parts.append("</available_skills>")
    
    # Join with space like Flocks does: .join(" ")
    return " ".join(parts)


async def skill_tool_impl(
    ctx: ToolContext,
    name: str,
) -> ToolResult:
    """
    Load a skill
    
    Args:
        ctx: Tool context
        name: Skill name to load
        
    Returns:
        ToolResult with skill content
    """
    if not name:
        return ToolResult(
            success=False,
            error="Skill name is required"
        )
    
    # Get skill
    skill = await Skill.get(name)
    
    if not skill:
        all_skills = await Skill.all()
        available = ", ".join(s.name for s in all_skills) or "none"
        return ToolResult(
            success=False,
            error=f'Skill "{name}" not found. Available skills: {available}'
        )
    
    # Request permission
    await ctx.ask(
        permission="skill",
        patterns=[name],
        always=[name],
        metadata={}
    )
    
    # Load skill content
    location = skill.location
    
    try:
        with open(location, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return ToolResult(
            success=False,
            error=f"Failed to load skill: {str(e)}"
        )
    
    # Get base directory
    skill_dir = os.path.dirname(location)
    
    # Format output
    output = f"""## Skill: {skill.name}

**Base directory**: {skill_dir}

{content.strip()}"""
    
    return ToolResult(
        success=True,
        output=output,
        title=f"Loaded skill: {skill.name}",
        metadata={
            "name": skill.name,
            "dir": skill_dir
        }
    )


async def get_all_skills() -> List[dict]:
    """
    Get all available skills as dictionaries
    
    Wrapper function for API routes compatibility.
    
    Returns:
        List of skill dictionaries with name, description, location
    """
    skills = await Skill.all()
    return [
        {
            "name": skill.name,
            "description": skill.description,
            "location": skill.location,
        }
        for skill in skills
    ]


async def get_skill(name: str) -> dict | None:
    """
    Get a specific skill by name as a dictionary
    
    Wrapper function for API routes compatibility.
    
    Args:
        name: Skill name to get
        
    Returns:
        Skill dictionary or None if not found
    """
    skill = await Skill.get(name)
    if not skill:
        return None
    
    # Also read the content
    try:
        with open(skill.location, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        content = ""
    
    return {
        "name": skill.name,
        "description": skill.description,
        "location": skill.location,
        "content": content,
    }


# Register the tool (description will be updated dynamically on first call)
@ToolRegistry.register_function(
    name="skill",
    description="Load a skill to get detailed instructions for a specific task. Available skills are listed in the description.",
    category=ToolCategory.SYSTEM,
    parameters=[
        ToolParameter(
            name="name",
            type=ParameterType.STRING,
            description="The skill identifier from available_skills",
            required=True
        ),
    ]
)
async def skill_tool(
    ctx: ToolContext,
    name: str,
) -> ToolResult:
    """Wrapper that updates description and calls implementation"""
    # Update tool description with available skills on first call
    tool = ToolRegistry.get("skill")
    if tool:
        skills = await Skill.all()
        tool.info.description = build_description(skills)
    
    return await skill_tool_impl(ctx, name)
