#!/usr/bin/env python3
"""
Unit tests for FSx Uploader

Tests the FSxUploader class functionality including:
- Mount verification
- File upload with retry logic
- Checksum verification
- Resume functionality
- Manifest generation
"""

import hashlib
import json
import os
import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from fsx_uploader import FSxUploader, UploadError


@pytest.fixture
def temp_source_dir():
    """Create temporary source directory with test files"""
    with tempfile.TemporaryDirectory() as tmpdir:
        source_dir = Path(tmpdir) / "source"
        source_dir.mkdir()
        
        # Create test files
        test_files = {
            "chr1.fa.gz": b"ATCGATCGATCG" * 100,
            "chr2.fa.gz": b"GCTAGCTAGCTA" * 100,
            "chr3.fa.gz": b"TTAATTAATTAA" * 100
        }
        
        for filename, content in test_files.items():
            filepath = source_dir / filename
            filepath.write_bytes(content)
        
        yield source_dir


@pytest.fixture
def temp_fsx_mount():
    """Create temporary FSx mount directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        fsx_mount = Path(tmpdir) / "fsx"
        fsx_mount.mkdir()
        yield fsx_mount


@pytest.fixture
def uploader(temp_source_dir, temp_fsx_mount):
    """Create FSxUploader instance with temporary directories"""
    return FSxUploader(
        source_dir=str(temp_source_dir),
        fsx_mount_point=str(temp_fsx_mount),
        max_retries=3,
        retry_delay=0.1,  # Short delay for tests
        verify_checksums=True,
        resume=True
    )


class TestFSxUploaderInit:
    """Test FSxUploader initialization"""
    
    def test_init_with_valid_paths(self, temp_source_dir, temp_fsx_mount):
        """Test initialization with valid paths"""
        uploader = FSxUploader(
            source_dir=str(temp_source_dir),
            fsx_mount_point=str(temp_fsx_mount)
        )
        
        assert uploader.source_dir == temp_source_dir
        assert uploader.fsx_mount_point == temp_fsx_mount
        assert uploader.max_retries == 3
        assert uploader.verify_checksums is True
        assert uploader.resume is True
    
    def test_init_with_nonexistent_source(self, temp_fsx_mount):
        """Test initialization with nonexistent source directory"""
        with pytest.raises(ValueError, match="Source directory does not exist"):
            FSxUploader(
                source_dir="/nonexistent/path",
                fsx_mount_point=str(temp_fsx_mount)
            )
    
    def test_init_with_nonexistent_mount(self, temp_source_dir):
        """Test initialization with nonexistent FSx mount"""
        with pytest.raises(ValueError, match="FSx mount point does not exist"):
            FSxUploader(
                source_dir=str(temp_source_dir),
                fsx_mount_point="/nonexistent/mount"
            )
    
    def test_init_with_custom_settings(self, temp_source_dir, temp_fsx_mount):
        """Test initialization with custom settings"""
        uploader = FSxUploader(
            source_dir=str(temp_source_dir),
            fsx_mount_point=str(temp_fsx_mount),
            max_retries=5,
            retry_delay=10,
            verify_checksums=False,
            resume=False
        )
        
        assert uploader.max_retries == 5
        assert uploader.retry_delay == 10
        assert uploader.verify_checksums is False
        assert uploader.resume is False


class TestMountVerification:
    """Test FSx mount verification"""
    
    def test_verify_mount_access_success(self, uploader):
        """Test successful mount verification"""
        assert uploader.verify_mount_access() is True
    
    def test_verify_mount_access_not_writable(self, uploader):
        """Test mount verification with non-writable mount"""
        with patch('os.access', return_value=False):
            assert uploader.verify_mount_access() is False
    
    def test_verify_mount_access_write_test_fails(self, uploader):
        """Test mount verification when write test fails"""
        with patch.object(Path, 'write_text', side_effect=PermissionError):
            assert uploader.verify_mount_access() is False


class TestChecksumCalculation:
    """Test checksum calculation"""
    
    def test_calculate_md5_checksum(self, uploader, temp_source_dir):
        """Test MD5 checksum calculation"""
        test_file = temp_source_dir / "chr1.fa.gz"
        checksum = uploader.calculate_checksum(test_file, algorithm='md5')
        
        # Verify checksum format
        assert len(checksum) == 32
        assert all(c in '0123456789abcdef' for c in checksum)
        
        # Verify checksum is consistent
        checksum2 = uploader.calculate_checksum(test_file, algorithm='md5')
        assert checksum == checksum2
    
    def test_calculate_sha256_checksum(self, uploader, temp_source_dir):
        """Test SHA256 checksum calculation"""
        test_file = temp_source_dir / "chr1.fa.gz"
        checksum = uploader.calculate_checksum(test_file, algorithm='sha256')
        
        # Verify checksum format
        assert len(checksum) == 64
        assert all(c in '0123456789abcdef' for c in checksum)
    
    def test_calculate_checksum_invalid_algorithm(self, uploader, temp_source_dir):
        """Test checksum calculation with invalid algorithm"""
        test_file = temp_source_dir / "chr1.fa.gz"
        
        with pytest.raises(ValueError, match="Unsupported hash algorithm"):
            uploader.calculate_checksum(test_file, algorithm='invalid')


class TestFileSkipping:
    """Test file skipping logic for resume functionality"""
    
    def test_should_skip_file_not_exists(self, uploader, temp_source_dir, temp_fsx_mount):
        """Test that non-existent files are not skipped"""
        source_file = temp_source_dir / "chr1.fa.gz"
        dest_file = temp_fsx_mount / "chr1.fa.gz"
        
        should_skip, reason = uploader.should_skip_file(source_file, dest_file)
        
        assert should_skip is False
        assert reason is None
    
    def test_should_skip_file_size_mismatch(self, uploader, temp_source_dir, temp_fsx_mount):
        """Test that files with size mismatch are not skipped"""
        source_file = temp_source_dir / "chr1.fa.gz"
        dest_file = temp_fsx_mount / "chr1.fa.gz"
        
        # Create dest file with different size
        dest_file.write_bytes(b"different content")
        
        should_skip, reason = uploader.should_skip_file(source_file, dest_file)
        
        assert should_skip is False
        assert "size mismatch" in reason
    
    def test_should_skip_file_checksum_match(self, uploader, temp_source_dir, temp_fsx_mount):
        """Test that files with matching checksums are skipped"""
        source_file = temp_source_dir / "chr1.fa.gz"
        dest_file = temp_fsx_mount / "chr1.fa.gz"
        
        # Copy file to destination
        dest_file.write_bytes(source_file.read_bytes())
        
        should_skip, reason = uploader.should_skip_file(source_file, dest_file)
        
        assert should_skip is True
        assert "matching checksum" in reason
    
    def test_should_skip_file_checksum_mismatch(self, uploader, temp_source_dir, temp_fsx_mount):
        """Test that files with checksum mismatch are not skipped"""
        source_file = temp_source_dir / "chr1.fa.gz"
        dest_file = temp_fsx_mount / "chr1.fa.gz"
        
        # Create dest file with same size but different content
        source_content = source_file.read_bytes()
        dest_content = b'X' * len(source_content)
        dest_file.write_bytes(dest_content)
        
        should_skip, reason = uploader.should_skip_file(source_file, dest_file)
        
        assert should_skip is False
        assert "checksum mismatch" in reason
    
    def test_should_skip_file_resume_disabled(self, temp_source_dir, temp_fsx_mount):
        """Test that files are not skipped when resume is disabled"""
        uploader = FSxUploader(
            source_dir=str(temp_source_dir),
            fsx_mount_point=str(temp_fsx_mount),
            resume=False
        )
        
        source_file = temp_source_dir / "chr1.fa.gz"
        dest_file = temp_fsx_mount / "chr1.fa.gz"
        
        # Copy file to destination
        dest_file.write_bytes(source_file.read_bytes())
        
        should_skip, reason = uploader.should_skip_file(source_file, dest_file)
        
        assert should_skip is False
        assert reason is None


class TestFileUpload:
    """Test file upload functionality"""
    
    def test_upload_file_success(self, uploader, temp_source_dir):
        """Test successful file upload"""
        source_file = temp_source_dir / "chr1.fa.gz"
        
        result = uploader.upload_file(source_file)
        
        assert result["status"] == "uploaded"
        assert result["filename"] == "chr1.fa.gz"
        assert result["size_bytes"] > 0
        assert result["upload_time_seconds"] >= 0
        assert result["checksum_source"] is not None
        assert result["checksum_dest"] is not None
        assert result["checksum_source"] == result["checksum_dest"]
        
        # Verify file exists at destination
        dest_file = Path(result["dest_path"])
        assert dest_file.exists()
    
    def test_upload_file_to_subdirectory(self, uploader, temp_source_dir):
        """Test file upload to subdirectory"""
        source_file = temp_source_dir / "chr1.fa.gz"
        
        result = uploader.upload_file(source_file, dest_subdir="chromosomes")
        
        assert result["status"] == "uploaded"
        assert "chromosomes" in result["dest_path"]
        
        # Verify subdirectory was created
        dest_file = Path(result["dest_path"])
        assert dest_file.parent.name == "chromosomes"
        assert dest_file.exists()
    
    def test_upload_file_skip_existing(self, uploader, temp_source_dir, temp_fsx_mount):
        """Test that existing files are skipped"""
        source_file = temp_source_dir / "chr1.fa.gz"
        
        # First upload
        result1 = uploader.upload_file(source_file)
        assert result1["status"] == "uploaded"
        
        # Second upload should skip
        result2 = uploader.upload_file(source_file)
        assert result2["status"] == "skipped"
        assert result2["upload_time_seconds"] == 0
    
    def test_upload_file_without_checksum_verification(self, temp_source_dir, temp_fsx_mount):
        """Test file upload without checksum verification"""
        uploader = FSxUploader(
            source_dir=str(temp_source_dir),
            fsx_mount_point=str(temp_fsx_mount),
            verify_checksums=False
        )
        
        source_file = temp_source_dir / "chr1.fa.gz"
        result = uploader.upload_file(source_file)
        
        assert result["status"] == "uploaded"
        assert result["checksum_source"] is None
        assert result["checksum_dest"] is None
    
    def test_upload_file_retry_on_failure(self, uploader, temp_source_dir):
        """Test retry logic on upload failure"""
        source_file = temp_source_dir / "chr1.fa.gz"
        
        # Mock copy to fail twice then succeed
        call_count = 0
        original_copy = uploader._copy_with_progress
        
        def mock_copy(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise IOError("Simulated failure")
            return original_copy(*args, **kwargs)
        
        with patch.object(uploader, '_copy_with_progress', side_effect=mock_copy):
            result = uploader.upload_file(source_file)
        
        assert result["status"] == "uploaded"
        assert call_count == 3  # Failed twice, succeeded on third attempt
    
    def test_upload_file_max_retries_exceeded(self, uploader, temp_source_dir):
        """Test that UploadError is raised after max retries"""
        source_file = temp_source_dir / "chr1.fa.gz"
        
        # Mock copy to always fail
        with patch.object(uploader, '_copy_with_progress', side_effect=IOError("Simulated failure")):
            with pytest.raises(UploadError, match="Failed to upload.*after 3 attempts"):
                uploader.upload_file(source_file)


class TestDirectoryUpload:
    """Test directory upload functionality"""
    
    def test_upload_directory_all_files(self, uploader):
        """Test uploading all files from directory"""
        result = uploader.upload_directory(pattern="*.fa.gz")
        
        assert result["total_files"] == 3
        assert result["uploaded_files"] == 3
        assert result["skipped_files"] == 0
        assert result["failed_files"] == 0
        assert result["total_size_bytes"] > 0
        assert len(result["files"]) == 3
    
    def test_upload_directory_with_pattern(self, uploader, temp_source_dir):
        """Test uploading files matching specific pattern"""
        # Create additional file that shouldn't match
        (temp_source_dir / "readme.txt").write_text("test")
        
        result = uploader.upload_directory(pattern="chr*.fa.gz")
        
        assert result["total_files"] == 3
        assert all("chr" in f["filename"] for f in result["files"])
    
    def test_upload_directory_to_subdirectory(self, uploader):
        """Test uploading directory to subdirectory"""
        result = uploader.upload_directory(
            pattern="*.fa.gz",
            dest_subdir="test_phase"
        )
        
        assert result["total_files"] == 3
        assert result["dest_subdir"] == "test_phase"
        assert all("test_phase" in f["dest_path"] for f in result["files"])
    
    def test_upload_directory_no_matching_files(self, uploader):
        """Test uploading with no matching files"""
        result = uploader.upload_directory(pattern="*.txt")
        
        assert result["total_files"] == 0
        assert result["uploaded_files"] == 0
        assert len(result["files"]) == 0
    
    def test_upload_directory_with_failures(self, uploader, temp_source_dir):
        """Test directory upload with some failures"""
        # Mock upload_file to fail for chr2
        original_upload = uploader.upload_file
        
        def mock_upload(source_file, dest_subdir=None):
            if "chr2" in source_file.name:
                raise UploadError("Simulated failure")
            return original_upload(source_file, dest_subdir)
        
        with patch.object(uploader, 'upload_file', side_effect=mock_upload):
            result = uploader.upload_directory(pattern="*.fa.gz")
        
        assert result["total_files"] == 3
        assert result["uploaded_files"] == 2
        assert result["failed_files"] == 1
        
        # Check that failed file is recorded
        failed_files = [f for f in result["files"] if f["status"] == "failed"]
        assert len(failed_files) == 1
        assert "chr2" in failed_files[0]["filename"]


class TestManifestGeneration:
    """Test upload manifest generation"""
    
    def test_save_upload_manifest(self, uploader, temp_fsx_mount):
        """Test saving upload manifest"""
        # Upload files
        upload_result = uploader.upload_directory(pattern="*.fa.gz")
        
        # Save manifest
        manifest_path = uploader.save_upload_manifest(upload_result)
        
        assert manifest_path.exists()
        assert manifest_path.name == "upload_manifest.json"
        
        # Verify manifest content
        with open(manifest_path) as f:
            manifest = json.load(f)
        
        assert "uploaded_at" in manifest
        assert "source_dir" in manifest
        assert "fsx_mount_point" in manifest
        assert "summary" in manifest
        assert "files" in manifest
        
        assert manifest["summary"]["total_files"] == 3
        assert manifest["summary"]["uploaded_files"] == 3
        assert len(manifest["files"]) == 3
    
    def test_save_upload_manifest_custom_path(self, uploader, temp_fsx_mount):
        """Test saving manifest to custom path"""
        upload_result = uploader.upload_directory(pattern="*.fa.gz")
        
        custom_path = temp_fsx_mount / "custom_manifest.json"
        manifest_path = uploader.save_upload_manifest(
            upload_result,
            manifest_path=str(custom_path)
        )
        
        assert manifest_path == custom_path
        assert custom_path.exists()


class TestUploadVerification:
    """Test upload verification functionality"""
    
    def test_verify_uploaded_files_success(self, uploader, temp_fsx_mount):
        """Test successful verification of uploaded files"""
        # Upload files
        upload_result = uploader.upload_directory(pattern="*.fa.gz")
        uploader.save_upload_manifest(upload_result)
        
        # Verify files
        results = uploader.verify_uploaded_files()
        
        assert len(results) == 3
        assert all(results.values())  # All should pass
    
    def test_verify_uploaded_files_missing_file(self, uploader, temp_fsx_mount):
        """Test verification with missing file"""
        # Upload files
        upload_result = uploader.upload_directory(pattern="*.fa.gz")
        uploader.save_upload_manifest(upload_result)
        
        # Delete one file
        (temp_fsx_mount / "chr1.fa.gz").unlink()
        
        # Verify files
        results = uploader.verify_uploaded_files()
        
        assert results["chr1.fa.gz"] is False
        assert results["chr2.fa.gz"] is True
        assert results["chr3.fa.gz"] is True
    
    def test_verify_uploaded_files_corrupted(self, uploader, temp_fsx_mount):
        """Test verification with corrupted file"""
        # Upload files
        upload_result = uploader.upload_directory(pattern="*.fa.gz")
        uploader.save_upload_manifest(upload_result)
        
        # Corrupt one file
        corrupted_file = temp_fsx_mount / "chr1.fa.gz"
        corrupted_file.write_bytes(b"corrupted data")
        
        # Verify files
        results = uploader.verify_uploaded_files()
        
        assert results["chr1.fa.gz"] is False
        assert results["chr2.fa.gz"] is True
        assert results["chr3.fa.gz"] is True
    
    def test_verify_uploaded_files_no_manifest(self, uploader):
        """Test verification without manifest"""
        with pytest.raises(FileNotFoundError, match="Manifest file not found"):
            uploader.verify_uploaded_files()


class TestUtilityMethods:
    """Test utility methods"""
    
    def test_format_size(self):
        """Test size formatting"""
        assert FSxUploader._format_size(0) == "0.00 B"
        assert FSxUploader._format_size(1024) == "1.00 KB"
        assert FSxUploader._format_size(1024 * 1024) == "1.00 MB"
        assert FSxUploader._format_size(1024 * 1024 * 1024) == "1.00 GB"
        assert FSxUploader._format_size(1024 * 1024 * 1024 * 1024) == "1.00 TB"
    
    def test_format_rate(self):
        """Test rate formatting"""
        assert FSxUploader._format_rate(0, 1) == "0.00 B/s"
        assert FSxUploader._format_rate(1024, 1) == "1.00 KB/s"
        assert FSxUploader._format_rate(1024 * 1024, 1) == "1.00 MB/s"
        assert FSxUploader._format_rate(1024 * 1024 * 1024, 1) == "1.00 GB/s"
        assert FSxUploader._format_rate(100, 0) == "N/A"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
