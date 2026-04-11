#!/usr/bin/env python3
"""
Unit Tests for Data Integrity Validator

Tests the DataIntegrityValidator class functionality including:
- File integrity verification
- Upload validation
- Report generation
- Error handling
"""

import json
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from data_integrity_validator import DataIntegrityValidator, ValidationError


class TestDataIntegrityValidator:
    """Test suite for DataIntegrityValidator"""
    
    @pytest.fixture
    def temp_dirs(self):
        """Create temporary source and FSx directories"""
        source_dir = tempfile.mkdtemp(prefix="test_source_")
        fsx_dir = tempfile.mkdtemp(prefix="test_fsx_")
        
        yield Path(source_dir), Path(fsx_dir)
        
        # Cleanup
        shutil.rmtree(source_dir, ignore_errors=True)
        shutil.rmtree(fsx_dir, ignore_errors=True)
    
    @pytest.fixture
    def sample_file(self, temp_dirs):
        """Create a sample test file"""
        source_dir, _ = temp_dirs
        test_file = source_dir / "test_chr1.fa.gz"
        test_file.write_bytes(b"ATCGATCGATCG" * 1000)  # 12KB test data
        return test_file
    
    def test_initialization_valid_directories(self, temp_dirs):
        """Test validator initialization with valid directories"""
        source_dir, fsx_dir = temp_dirs
        
        validator = DataIntegrityValidator(
            source_dir=str(source_dir),
            fsx_mount_path=str(fsx_dir)
        )
        
        assert validator.source_dir == source_dir
        assert validator.fsx_mount_path == fsx_dir
        assert validator.checksum_calculator is not None
    
    def test_initialization_invalid_source_dir(self, temp_dirs):
        """Test validator initialization with non-existent source directory"""
        _, fsx_dir = temp_dirs
        
        with pytest.raises(ValueError, match="Source directory does not exist"):
            DataIntegrityValidator(
                source_dir="/nonexistent/path",
                fsx_mount_path=str(fsx_dir)
            )
    
    def test_initialization_invalid_fsx_mount(self, temp_dirs):
        """Test validator initialization with non-existent FSx mount"""
        source_dir, _ = temp_dirs
        
        with pytest.raises(ValueError, match="FSx mount path does not exist"):
            DataIntegrityValidator(
                source_dir=str(source_dir),
                fsx_mount_path="/nonexistent/fsx"
            )
    
    def test_verify_file_integrity_matching_files(self, temp_dirs, sample_file):
        """Test file integrity verification with matching source and destination"""
        source_dir, fsx_dir = temp_dirs
        
        # Copy file to FSx directory
        dest_file = fsx_dir / sample_file.name
        shutil.copy2(sample_file, dest_file)
        
        validator = DataIntegrityValidator(
            source_dir=str(source_dir),
            fsx_mount_path=str(fsx_dir)
        )
        
        result = validator.verify_file_integrity(sample_file, dest_file)
        
        assert result["valid"] is True
        assert result["filename"] == sample_file.name
        assert result["size_match"] is True
        assert result["checksum_match"] is True
        assert result["source_md5"] == result["dest_md5"]
        assert result["source_sha256"] == result["dest_sha256"]
        assert "error_message" not in result or result["error_message"] is None
    
    def test_verify_file_integrity_missing_destination(self, temp_dirs, sample_file):
        """Test file integrity verification when destination file is missing"""
        source_dir, fsx_dir = temp_dirs
        
        dest_file = fsx_dir / "nonexistent.fa.gz"
        
        validator = DataIntegrityValidator(
            source_dir=str(source_dir),
            fsx_mount_path=str(fsx_dir)
        )
        
        result = validator.verify_file_integrity(sample_file, dest_file)
        
        assert result["valid"] is False
        assert "Destination file does not exist" in result["error_message"]
    
    def test_verify_file_integrity_size_mismatch(self, temp_dirs, sample_file):
        """Test file integrity verification with size mismatch"""
        source_dir, fsx_dir = temp_dirs
        
        # Create destination file with different size
        dest_file = fsx_dir / sample_file.name
        dest_file.write_bytes(b"ATCG" * 100)  # Different size
        
        validator = DataIntegrityValidator(
            source_dir=str(source_dir),
            fsx_mount_path=str(fsx_dir)
        )
        
        result = validator.verify_file_integrity(sample_file, dest_file)
        
        assert result["valid"] is False
        assert result["size_match"] is False
        assert "File size mismatch" in result["error_message"]
        assert result["source_size"] != result["dest_size"]
    
    def test_verify_file_integrity_checksum_mismatch(self, temp_dirs, sample_file):
        """Test file integrity verification with checksum mismatch"""
        source_dir, fsx_dir = temp_dirs
        
        # Create destination file with same size but different content
        dest_file = fsx_dir / sample_file.name
        source_size = sample_file.stat().st_size
        dest_file.write_bytes(b"X" * source_size)  # Same size, different content
        
        validator = DataIntegrityValidator(
            source_dir=str(source_dir),
            fsx_mount_path=str(fsx_dir)
        )
        
        result = validator.verify_file_integrity(sample_file, dest_file)
        
        assert result["valid"] is False
        assert result["size_match"] is True
        assert result["checksum_match"] is False
        assert "mismatch" in result["error_message"].lower()
        assert result["source_md5"] != result["dest_md5"]
    
    def test_validate_upload_all_files_valid(self, temp_dirs):
        """Test upload validation with all files valid"""
        source_dir, fsx_dir = temp_dirs
        
        # Create multiple test files
        test_files = []
        for i in range(3):
            test_file = source_dir / f"chr{i+1}.fa.gz"
            test_file.write_bytes(b"ATCG" * (i + 1) * 100)
            test_files.append(test_file)
            
            # Copy to FSx
            dest_file = fsx_dir / test_file.name
            shutil.copy2(test_file, dest_file)
        
        validator = DataIntegrityValidator(
            source_dir=str(source_dir),
            fsx_mount_path=str(fsx_dir)
        )
        
        results = validator.validate_upload(pattern="*.fa.gz")
        
        assert results["total_files"] == 3
        assert results["valid_files"] == 3
        assert results["invalid_files"] == 0
        assert results["total_size_bytes"] > 0
        assert "validation_timestamp" in results
        assert len(results["files"]) == 3
        
        for file_result in results["files"]:
            assert file_result["valid"] is True
    
    def test_validate_upload_some_files_invalid(self, temp_dirs):
        """Test upload validation with some files invalid"""
        source_dir, fsx_dir = temp_dirs
        
        # Create test files
        valid_file = source_dir / "chr1.fa.gz"
        valid_file.write_bytes(b"ATCG" * 100)
        shutil.copy2(valid_file, fsx_dir / valid_file.name)
        
        invalid_file = source_dir / "chr2.fa.gz"
        invalid_file.write_bytes(b"ATCG" * 200)
        # Create corrupted destination
        (fsx_dir / invalid_file.name).write_bytes(b"XXXX" * 200)
        
        validator = DataIntegrityValidator(
            source_dir=str(source_dir),
            fsx_mount_path=str(fsx_dir)
        )
        
        results = validator.validate_upload(pattern="*.fa.gz")
        
        assert results["total_files"] == 2
        assert results["valid_files"] == 1
        assert results["invalid_files"] == 1
    
    def test_validate_upload_no_matching_files(self, temp_dirs):
        """Test upload validation with no matching files"""
        source_dir, fsx_dir = temp_dirs
        
        validator = DataIntegrityValidator(
            source_dir=str(source_dir),
            fsx_mount_path=str(fsx_dir)
        )
        
        results = validator.validate_upload(pattern="*.fa.gz")
        
        assert results["total_files"] == 0
        assert results["valid_files"] == 0
        assert results["invalid_files"] == 0
        assert len(results["files"]) == 0
    
    def test_validate_upload_with_subdirectory(self, temp_dirs):
        """Test upload validation with destination subdirectory"""
        source_dir, fsx_dir = temp_dirs
        
        # Create subdirectory in FSx
        subdir = fsx_dir / "hg38_data"
        subdir.mkdir()
        
        # Create test file
        test_file = source_dir / "chr1.fa.gz"
        test_file.write_bytes(b"ATCG" * 100)
        shutil.copy2(test_file, subdir / test_file.name)
        
        validator = DataIntegrityValidator(
            source_dir=str(source_dir),
            fsx_mount_path=str(fsx_dir)
        )
        
        results = validator.validate_upload(
            dest_subdir="hg38_data",
            pattern="*.fa.gz"
        )
        
        assert results["total_files"] == 1
        assert results["valid_files"] == 1
        assert results["dest_subdir"] == "hg38_data"
    
    def test_validate_upload_nonexistent_subdirectory(self, temp_dirs):
        """Test upload validation with non-existent subdirectory"""
        source_dir, fsx_dir = temp_dirs
        
        test_file = source_dir / "chr1.fa.gz"
        test_file.write_bytes(b"ATCG" * 100)
        
        validator = DataIntegrityValidator(
            source_dir=str(source_dir),
            fsx_mount_path=str(fsx_dir)
        )
        
        with pytest.raises(ValidationError, match="Destination directory does not exist"):
            validator.validate_upload(
                dest_subdir="nonexistent_subdir",
                pattern="*.fa.gz"
            )
    
    def test_generate_validation_report(self, temp_dirs):
        """Test validation report generation"""
        source_dir, fsx_dir = temp_dirs
        
        # Create test file
        test_file = source_dir / "chr1.fa.gz"
        test_file.write_bytes(b"ATCG" * 100)
        shutil.copy2(test_file, fsx_dir / test_file.name)
        
        validator = DataIntegrityValidator(
            source_dir=str(source_dir),
            fsx_mount_path=str(fsx_dir)
        )
        
        validation_results = validator.validate_upload(pattern="*.fa.gz")
        report_path = validator.generate_validation_report(validation_results)
        
        assert report_path.exists()
        assert report_path.suffix == ".json"
        
        # Verify JSON report content
        with open(report_path, 'r') as f:
            report = json.load(f)
        
        assert "validation_summary" in report
        assert "configuration" in report
        assert "file_results" in report
        assert "failed_files" in report
        
        assert report["validation_summary"]["total_files"] == 1
        assert report["validation_summary"]["valid_files"] == 1
        assert report["validation_summary"]["success_rate"] == 100.0
        
        # Verify text summary was also created
        text_report_path = report_path.with_suffix('.txt')
        assert text_report_path.exists()
        
        text_content = text_report_path.read_text()
        assert "DATA INTEGRITY VALIDATION REPORT" in text_content
        assert "PASSED" in text_content
    
    def test_generate_validation_report_with_failures(self, temp_dirs):
        """Test validation report generation with failed files"""
        source_dir, fsx_dir = temp_dirs
        
        # Create test file with corrupted destination
        test_file = source_dir / "chr1.fa.gz"
        test_file.write_bytes(b"ATCG" * 100)
        (fsx_dir / test_file.name).write_bytes(b"XXXX" * 100)
        
        validator = DataIntegrityValidator(
            source_dir=str(source_dir),
            fsx_mount_path=str(fsx_dir)
        )
        
        validation_results = validator.validate_upload(pattern="*.fa.gz")
        report_path = validator.generate_validation_report(validation_results)
        
        with open(report_path, 'r') as f:
            report = json.load(f)
        
        assert report["validation_summary"]["invalid_files"] == 1
        assert len(report["failed_files"]) == 1
        assert report["failed_files"][0]["filename"] == "chr1.fa.gz"
        
        # Verify text summary shows failure
        text_content = report_path.with_suffix('.txt').read_text()
        assert "FAILED" in text_content
        assert "Failed Files:" in text_content
    
    def test_generate_validation_report_custom_path(self, temp_dirs):
        """Test validation report generation with custom path"""
        source_dir, fsx_dir = temp_dirs
        
        test_file = source_dir / "chr1.fa.gz"
        test_file.write_bytes(b"ATCG" * 100)
        shutil.copy2(test_file, fsx_dir / test_file.name)
        
        validator = DataIntegrityValidator(
            source_dir=str(source_dir),
            fsx_mount_path=str(fsx_dir)
        )
        
        validation_results = validator.validate_upload(pattern="*.fa.gz")
        custom_path = source_dir / "custom_report.json"
        
        report_path = validator.generate_validation_report(
            validation_results,
            report_path=str(custom_path)
        )
        
        assert report_path == custom_path
        assert custom_path.exists()
    
    def test_format_size(self):
        """Test size formatting utility"""
        validator_class = DataIntegrityValidator
        
        assert validator_class._format_size(500) == "500.00 B"
        assert validator_class._format_size(1024) == "1.00 KB"
        assert validator_class._format_size(1024 * 1024) == "1.00 MB"
        assert validator_class._format_size(1024 * 1024 * 1024) == "1.00 GB"
        assert validator_class._format_size(1024 * 1024 * 1024 * 1024) == "1.00 TB"
    
    def test_calculate_checksum_md5(self, temp_dirs):
        """Test MD5 checksum calculation"""
        source_dir, fsx_dir = temp_dirs
        
        test_file = source_dir / "test.txt"
        test_file.write_bytes(b"test content")
        
        validator = DataIntegrityValidator(
            source_dir=str(source_dir),
            fsx_mount_path=str(fsx_dir)
        )
        
        checksum = validator._calculate_checksum(test_file, 'md5')
        
        assert isinstance(checksum, str)
        assert len(checksum) == 32  # MD5 produces 32 hex characters
    
    def test_calculate_checksum_sha256(self, temp_dirs):
        """Test SHA256 checksum calculation"""
        source_dir, fsx_dir = temp_dirs
        
        test_file = source_dir / "test.txt"
        test_file.write_bytes(b"test content")
        
        validator = DataIntegrityValidator(
            source_dir=str(source_dir),
            fsx_mount_path=str(fsx_dir)
        )
        
        checksum = validator._calculate_checksum(test_file, 'sha256')
        
        assert isinstance(checksum, str)
        assert len(checksum) == 64  # SHA256 produces 64 hex characters
    
    def test_calculate_checksum_invalid_algorithm(self, temp_dirs):
        """Test checksum calculation with invalid algorithm"""
        source_dir, fsx_dir = temp_dirs
        
        test_file = source_dir / "test.txt"
        test_file.write_bytes(b"test content")
        
        validator = DataIntegrityValidator(
            source_dir=str(source_dir),
            fsx_mount_path=str(fsx_dir)
        )
        
        with pytest.raises(ValueError, match="Unsupported hash algorithm"):
            validator._calculate_checksum(test_file, 'invalid_algo')


class TestDataIntegrityValidatorCLI:
    """Test suite for CLI interface"""
    
    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for CLI tests"""
        source_dir = tempfile.mkdtemp(prefix="test_cli_source_")
        fsx_dir = tempfile.mkdtemp(prefix="test_cli_fsx_")
        
        yield Path(source_dir), Path(fsx_dir)
        
        shutil.rmtree(source_dir, ignore_errors=True)
        shutil.rmtree(fsx_dir, ignore_errors=True)
    
    def test_cli_successful_validation(self, temp_dirs, monkeypatch):
        """Test CLI with successful validation"""
        source_dir, fsx_dir = temp_dirs
        
        # Create test file
        test_file = source_dir / "chr1.fa.gz"
        test_file.write_bytes(b"ATCG" * 100)
        shutil.copy2(test_file, fsx_dir / test_file.name)
        
        # Mock sys.argv
        test_args = [
            "data_integrity_validator.py",
            "--source-dir", str(source_dir),
            "--fsx-mount", str(fsx_dir),
            "--pattern", "*.fa.gz"
        ]
        monkeypatch.setattr("sys.argv", test_args)
        
        # Import and run main
        from data_integrity_validator import main
        
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        assert exc_info.value.code == 0  # Success exit code
    
    def test_cli_failed_validation(self, temp_dirs, monkeypatch):
        """Test CLI with failed validation"""
        source_dir, fsx_dir = temp_dirs
        
        # Create test file with corrupted destination
        test_file = source_dir / "chr1.fa.gz"
        test_file.write_bytes(b"ATCG" * 100)
        (fsx_dir / test_file.name).write_bytes(b"XXXX" * 100)
        
        test_args = [
            "data_integrity_validator.py",
            "--source-dir", str(source_dir),
            "--fsx-mount", str(fsx_dir),
            "--pattern", "*.fa.gz"
        ]
        monkeypatch.setattr("sys.argv", test_args)
        
        from data_integrity_validator import main
        
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        assert exc_info.value.code == 1  # Failure exit code


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
