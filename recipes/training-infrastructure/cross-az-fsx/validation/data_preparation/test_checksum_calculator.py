#!/usr/bin/env python3
"""
Unit tests for checksum_calculator module
"""

import json
import pytest
import tempfile
from pathlib import Path
from checksum_calculator import ChecksumCalculator


class TestChecksumCalculator:
    """Test suite for ChecksumCalculator class"""
    
    @pytest.fixture
    def temp_data_dir(self):
        """Create a temporary directory with test files"""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            
            # Create test files with known content
            test_files = {
                'chr1.fa.gz': b'ATCGATCGATCG',
                'chr2.fa.gz': b'GCTAGCTAGCTA',
                'chr3.fa.gz': b'TTAATTAATTAA'
            }
            
            for filename, content in test_files.items():
                filepath = data_dir / filename
                filepath.write_bytes(content)
            
            yield data_dir
    
    def test_init_with_valid_directory(self, temp_data_dir):
        """Test initialization with valid directory"""
        calculator = ChecksumCalculator(str(temp_data_dir))
        assert calculator.data_dir == temp_data_dir
        assert calculator.manifest_path == temp_data_dir / "checksums_manifest.json"
    
    def test_init_with_invalid_directory(self):
        """Test initialization with non-existent directory"""
        with pytest.raises(ValueError, match="Data directory does not exist"):
            ChecksumCalculator("/nonexistent/directory")
    
    def test_init_with_custom_manifest_path(self, temp_data_dir):
        """Test initialization with custom manifest path"""
        custom_path = temp_data_dir / "custom_manifest.json"
        calculator = ChecksumCalculator(str(temp_data_dir), str(custom_path))
        assert calculator.manifest_path == custom_path
    
    def test_calculate_file_checksums(self, temp_data_dir):
        """Test checksum calculation for a single file"""
        calculator = ChecksumCalculator(str(temp_data_dir))
        filepath = temp_data_dir / "chr1.fa.gz"
        
        checksums = calculator.calculate_file_checksums(filepath)
        
        assert 'md5' in checksums
        assert 'sha256' in checksums
        assert len(checksums['md5']) == 32  # MD5 is 32 hex chars
        assert len(checksums['sha256']) == 64  # SHA256 is 64 hex chars
    
    def test_calculate_file_checksums_consistency(self, temp_data_dir):
        """Test that checksums are consistent across multiple calculations"""
        calculator = ChecksumCalculator(str(temp_data_dir))
        filepath = temp_data_dir / "chr1.fa.gz"
        
        checksums1 = calculator.calculate_file_checksums(filepath)
        checksums2 = calculator.calculate_file_checksums(filepath)
        
        assert checksums1['md5'] == checksums2['md5']
        assert checksums1['sha256'] == checksums2['sha256']
    
    def test_calculate_directory_checksums(self, temp_data_dir):
        """Test checksum calculation for all files in directory"""
        calculator = ChecksumCalculator(str(temp_data_dir))
        
        results = calculator.calculate_directory_checksums()
        
        assert len(results) == 3
        assert 'chr1.fa.gz' in results
        assert 'chr2.fa.gz' in results
        assert 'chr3.fa.gz' in results
        
        for filename, data in results.items():
            assert 'filename' in data
            assert 'filepath' in data
            assert 'size_bytes' in data
            assert 'md5' in data
            assert 'sha256' in data
            assert 'calculated_at' in data
    
    def test_calculate_directory_checksums_with_pattern(self, temp_data_dir):
        """Test checksum calculation with specific pattern"""
        calculator = ChecksumCalculator(str(temp_data_dir))
        
        # Create a file that doesn't match the pattern
        (temp_data_dir / "readme.txt").write_text("test")
        
        results = calculator.calculate_directory_checksums(pattern="*.fa.gz")
        
        assert len(results) == 3
        assert 'readme.txt' not in results
    
    def test_generate_manifest(self, temp_data_dir):
        """Test manifest generation"""
        calculator = ChecksumCalculator(str(temp_data_dir))
        
        manifest = calculator.generate_manifest()
        
        assert 'files' in manifest
        assert 'metadata' in manifest
        assert len(manifest['files']) == 3
        
        metadata = manifest['metadata']
        assert metadata['total_files'] == 3
        assert metadata['successful_files'] == 3
        assert metadata['failed_files'] == 0
        assert metadata['total_size_bytes'] > 0
    
    def test_save_and_load_manifest(self, temp_data_dir):
        """Test saving and loading manifest"""
        calculator = ChecksumCalculator(str(temp_data_dir))
        
        # Generate and save manifest
        original_manifest = calculator.generate_manifest()
        manifest_path = calculator.save_manifest(original_manifest)
        
        assert manifest_path.exists()
        
        # Load manifest
        loaded_manifest = calculator.load_manifest()
        
        assert loaded_manifest['files'] == original_manifest['files']
        assert loaded_manifest['metadata']['total_files'] == original_manifest['metadata']['total_files']
    
    def test_load_manifest_not_found(self, temp_data_dir):
        """Test loading non-existent manifest"""
        calculator = ChecksumCalculator(str(temp_data_dir))
        
        with pytest.raises(FileNotFoundError):
            calculator.load_manifest()
    
    def test_verify_file_integrity_success(self, temp_data_dir):
        """Test successful file integrity verification"""
        calculator = ChecksumCalculator(str(temp_data_dir))
        
        # Generate manifest
        manifest = calculator.generate_manifest()
        calculator.save_manifest(manifest)
        
        # Verify file
        result = calculator.verify_file_integrity('chr1.fa.gz')
        
        assert result is True
    
    def test_verify_file_integrity_failure(self, temp_data_dir):
        """Test file integrity verification with corrupted file"""
        calculator = ChecksumCalculator(str(temp_data_dir))
        
        # Generate manifest
        manifest = calculator.generate_manifest()
        calculator.save_manifest(manifest)
        
        # Corrupt the file
        filepath = temp_data_dir / "chr1.fa.gz"
        filepath.write_bytes(b'CORRUPTED')
        
        # Verify file
        result = calculator.verify_file_integrity('chr1.fa.gz')
        
        assert result is False
    
    def test_verify_file_not_in_manifest(self, temp_data_dir):
        """Test verification of file not in manifest"""
        calculator = ChecksumCalculator(str(temp_data_dir))
        
        # Generate manifest
        manifest = calculator.generate_manifest()
        calculator.save_manifest(manifest)
        
        # Try to verify non-existent file
        result = calculator.verify_file_integrity('chr99.fa.gz')
        
        assert result is False
    
    def test_verify_all_files_success(self, temp_data_dir):
        """Test verification of all files"""
        calculator = ChecksumCalculator(str(temp_data_dir))
        
        # Generate manifest
        manifest = calculator.generate_manifest()
        calculator.save_manifest(manifest)
        
        # Verify all files
        results = calculator.verify_all_files()
        
        assert len(results) == 3
        assert all(results.values())
    
    def test_verify_all_files_with_corruption(self, temp_data_dir):
        """Test verification of all files with one corrupted"""
        calculator = ChecksumCalculator(str(temp_data_dir))
        
        # Generate manifest
        manifest = calculator.generate_manifest()
        calculator.save_manifest(manifest)
        
        # Corrupt one file
        filepath = temp_data_dir / "chr2.fa.gz"
        filepath.write_bytes(b'CORRUPTED')
        
        # Verify all files
        results = calculator.verify_all_files()
        
        assert len(results) == 3
        assert results['chr1.fa.gz'] is True
        assert results['chr2.fa.gz'] is False
        assert results['chr3.fa.gz'] is True
    
    def test_format_size(self):
        """Test size formatting"""
        assert ChecksumCalculator._format_size(500) == "500.00 B"
        assert ChecksumCalculator._format_size(1024) == "1.00 KB"
        assert ChecksumCalculator._format_size(1024 * 1024) == "1.00 MB"
        assert ChecksumCalculator._format_size(1024 * 1024 * 1024) == "1.00 GB"
