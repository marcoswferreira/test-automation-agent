"""Core data models for Test Automation Agent."""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    x: float
    y: float
    width: float
    height: float


class UIElement(BaseModel):
    """Represents an interactive or significant element on the web page."""
    mark_id: int
    tag_name: str
    element_id: Optional[str] = None
    test_id: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = None
    text: Optional[str] = None
    placeholder: Optional[str] = None
    bbox: BoundingBox
    selector_candidates: List[str] = Field(default_factory=list)
    attributes: Dict[str, str] = Field(default_factory=dict)


class VisualChange(BaseModel):
    """Represents a visual or structural difference detected between baseline and target."""
    change_type: Literal["added", "removed", "modified", "layout_shift"]
    description: str
    affected_element_ids: List[str] = Field(default_factory=list)
    confidence: float = 1.0
    suggested_assertion: Optional[str] = None


class ActionStep(BaseModel):
    """Represents an atomic action in a test scenario."""
    action_type: Literal["click", "fill_text", "select_option", "verify_text", "verify_visible", "take_screenshot", "wait_for"]
    target_selector: str
    target_description: str
    value: Optional[str] = None
    expected_outcome: Optional[str] = None


class KeywordDefinition(BaseModel):
    """Robot Framework keyword abstraction (Page Object / Resource pattern)."""
    name: str
    arguments: List[str] = Field(default_factory=list)
    documentation: Optional[str] = None
    steps: List[str] = Field(default_factory=list)


class TestCaseDefinition(BaseModel):
    """Single Robot Framework test case."""
    __test__ = False
    name: str
    documentation: str
    tags: List[str] = Field(default_factory=list)
    steps: List[str] = Field(default_factory=list)


class TestSuiteDefinition(BaseModel):
    """Complete Robot Framework test suite and companion resource file."""
    __test__ = False
    suite_name: str
    documentation: str
    target_url: str
    resource_name: str
    keywords: List[KeywordDefinition] = Field(default_factory=list)
    test_cases: List[TestCaseDefinition] = Field(default_factory=list)
    variables: Dict[str, str] = Field(default_factory=dict)


class TestExecutionResult(BaseModel):
    """Result of running a Robot Framework test suite."""
    __test__ = False
    success: bool
    total_tests: int
    passed_tests: int
    failed_tests: int
    output_xml_path: str
    log_html_path: str
    report_html_path: str
    failure_messages: List[str] = Field(default_factory=list)
    failed_keyword: Optional[str] = None
    raw_console_output: Optional[str] = None
