import pytest
import tempfile
import os
from pathlib import Path
from flocks.tool.file.file_search import file_search, _should_skip_path, _is_binary_file


@pytest.fixture
def temp_test_dir():
    """Create a temporary directory with test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)
        
        # Create test files
        (test_dir / "test1.py").write_text("import os\nprint('hello')\nimport sys")
        (test_dir / "test2.py").write_text("def foo():\n    return 'bar'")
        (test_dir / "config.json").write_text('{"key": "value"}')
        (test_dir / "data.txt").write_text("line1\nline2\nline3")
        
        # Create subdirectory
        subdir = test_dir / "subdir"
        subdir.mkdir()
        (subdir / "nested.py").write_text("import json\nimport re")
        (subdir / "readme.md").write_text("# Test\n\nContent here")
        
        # Create sensitive directory (should be skipped)
        sensitive = test_dir / ".ssh"
        sensitive.mkdir()
        (sensitive / "key").write_text("secret key")
        
        yield test_dir


class TestFileSearch:
    """Test file_search function."""
    
    @pytest.mark.asyncio
    async def test_search_by_filename_pattern(self, temp_test_dir):
        """Test searching files by glob pattern."""
        result = await file_search(
            pattern="*.py",
            directory=str(temp_test_dir),
            recursive=True
        )
        
        assert result["status"] == "success"
        assert result["search_type"] == "filename"
        assert result["count"] >= 3  # test1.py, test2.py, nested.py
        assert all(r["name"].endswith(".py") for r in result["results"])
    
    @pytest.mark.asyncio
    async def test_search_by_filename_non_recursive(self, temp_test_dir):
        """Test non-recursive filename search."""
        result = await file_search(
            pattern="*.py",
            directory=str(temp_test_dir),
            recursive=False
        )
        
        assert result["status"] == "success"
        assert result["count"] == 2  # Only test1.py, test2.py (not nested.py)
        assert all(r["name"] in ["test1.py", "test2.py"] for r in result["results"])
    
    @pytest.mark.asyncio
    async def test_search_by_content(self, temp_test_dir):
        """Test searching file contents."""
        result = await file_search(
            pattern="import",
            directory=str(temp_test_dir),
            search_content=True,
            file_extensions="py"
        )
        
        assert result["status"] == "success"
        assert result["search_type"] == "content"
        assert result["count"] >= 2  # test1.py and nested.py have imports
        
        # Check that results contain matches
        for file_result in result["results"]:
            assert "matches" in file_result
            assert file_result["match_count"] > 0
    
    @pytest.mark.asyncio
    async def test_search_by_content_regex(self, temp_test_dir):
        """Test searching with regex pattern."""
        result = await file_search(
            pattern=r"import\s+(os|json)",
            directory=str(temp_test_dir),
            search_content=True,
            file_extensions="py"
        )
        
        assert result["status"] == "success"
        assert result["count"] >= 2
    
    @pytest.mark.asyncio
    async def test_max_results_limit(self, temp_test_dir):
        """Test max_results parameter."""
        result = await file_search(
            pattern="*",
            directory=str(temp_test_dir),
            max_results=2
        )
        
        assert result["status"] == "success"
        assert result["count"] <= 2
        assert result["truncated"] == True
    
    @pytest.mark.asyncio
    async def test_nonexistent_directory(self):
        """Test searching in non-existent directory."""
        result = await file_search(
            pattern="*.py",
            directory="/nonexistent/directory"
        )
        
        assert result["status"] == "error"
        assert "does not exist" in result["error"]
    
    @pytest.mark.asyncio
    async def test_invalid_regex_pattern(self, temp_test_dir):
        """Test invalid regex pattern for content search."""
        result = await file_search(
            pattern="[invalid(",
            directory=str(temp_test_dir),
            search_content=True
        )
        
        assert result["status"] == "error"
        assert "Invalid regex pattern" in result["error"]
    
    @pytest.mark.asyncio
    async def test_file_extensions_filter(self, temp_test_dir):
        """Test file extensions filter for content search."""
        result = await file_search(
            pattern="import",
            directory=str(temp_test_dir),
            search_content=True,
            file_extensions="py"
        )
        
        assert result["status"] == "success"
        # All results should be Python files
        assert all(r["name"].endswith(".py") for r in result["results"])


class TestHelperFunctions:
    """Test helper functions."""
    
    def test_should_skip_path_sensitive_dirs(self):
        """Test that sensitive directories are skipped."""
        assert _should_skip_path(Path("/home/user/.ssh/key")) == True
        assert _should_skip_path(Path("/home/user/.gnupg/file")) == True
        assert _should_skip_path(Path("/home/user/node_modules/lib")) == True
        assert _should_skip_path(Path("/home/user/.git/config")) == True
        assert _should_skip_path(Path("/home/user/normal/file.py")) == False
    
    def test_is_binary_file_by_extension(self):
        """Test binary file detection by extension."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir)
            
            # Create files with binary extensions
            (test_dir / "test.png").write_text("fake png")
            (test_dir / "test.exe").write_text("fake exe")
            (test_dir / "test.zip").write_text("fake zip")
            
            assert _is_binary_file(test_dir / "test.png") == True
            assert _is_binary_file(test_dir / "test.exe") == True
            assert _is_binary_file(test_dir / "test.zip") == True  # .zip is a binary extension
    
    def test_is_binary_file_by_size(self):
        """Test binary file detection by size."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir)
            
            # Create a large file
            large_file = test_dir / "large.txt"
            large_file.write_bytes(b"x" * (11 * 1024 * 1024))  # 11MB
            
            assert _is_binary_file(large_file) == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])