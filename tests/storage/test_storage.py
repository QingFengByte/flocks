"""
Tests for storage module
"""

import pytest
from pathlib import Path
import tempfile
from pydantic import BaseModel

from flocks.storage.storage import Storage


class StorageTestModel(BaseModel):
    """Test model for storage"""
    id: str
    name: str
    value: int


@pytest.fixture
async def storage():
    """Create a temporary storage for testing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        await Storage.init(db_path)
        yield Storage
        # Cleanup
        await Storage.clear()


@pytest.mark.asyncio
async def test_storage_set_get(storage):
    """Test basic set and get operations"""
    await storage.set("test_key", {"value": 123}, "test")
    
    result = await storage.get("test_key")
    assert result == {"value": 123}


@pytest.mark.asyncio
async def test_storage_with_model(storage):
    """Test storage with Pydantic models"""
    model = StorageTestModel(id="test_1", name="Test", value=42)
    
    await storage.set("model_key", model, "test_model")
    
    retrieved = await storage.get("model_key", StorageTestModel)
    assert retrieved.id == "test_1"
    assert retrieved.name == "Test"
    assert retrieved.value == 42


@pytest.mark.asyncio
async def test_storage_delete(storage):
    """Test delete operation"""
    await storage.set("delete_key", {"data": "test"}, "test")
    
    exists = await storage.exists("delete_key")
    assert exists is True
    
    deleted = await storage.delete("delete_key")
    assert deleted is True
    
    exists = await storage.exists("delete_key")
    assert exists is False


@pytest.mark.asyncio
async def test_storage_list_keys(storage):
    """Test listing keys with prefix"""
    await storage.set("prefix:key1", {"data": 1}, "test")
    await storage.set("prefix:key2", {"data": 2}, "test")
    await storage.set("other:key", {"data": 3}, "test")
    
    keys = await storage.list_keys(prefix="prefix:")
    assert len(keys) == 2
    assert "prefix:key1" in keys
    assert "prefix:key2" in keys
    assert "other:key" not in keys


@pytest.mark.asyncio
async def test_storage_list_entries(storage):
    """Test batch listing entries with model deserialization."""
    item1 = StorageTestModel(id="m1", name="Alpha", value=1)
    item2 = StorageTestModel(id="m2", name="Beta", value=2)
    await storage.set("batch:key1", item1, "test_model")
    await storage.set("batch:key2", item2, "test_model")
    await storage.set("other:key", {"skip": True}, "test")

    entries = await storage.list_entries(prefix="batch:", model=StorageTestModel)

    assert len(entries) == 2
    entry_map = {key: value for key, value in entries}
    assert set(entry_map) == {"batch:key1", "batch:key2"}
    assert entry_map["batch:key1"].name == "Alpha"
    assert entry_map["batch:key2"].value == 2


@pytest.mark.asyncio
async def test_storage_clear(storage):
    """Test clearing storage"""
    await storage.set("clear1", {"data": 1}, "test")
    await storage.set("clear2", {"data": 2}, "test")
    
    deleted = await storage.clear()
    assert deleted == 2
    
    keys = await storage.list_keys()
    assert len(keys) == 0
