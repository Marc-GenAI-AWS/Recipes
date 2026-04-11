#!/usr/bin/env python3
"""
Integration tests for checksum_calculator with hg38_downloader
"""

import pytest
import tempfile
from pathlib import Path
from checksum_calculator import ChecksumCalculator


class TestChecksumIntegration:
    """Integration tests for checksum calculator with downloaded files"""
    
    @pytest.fixture
    def mock_downloaded_files(self):
        """Create mock downloaded chromosome files similar to hg38_downloader output"""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            
            # Simulate downloaded chromosome files with realistic names
            test_files = {
                'chr1.fa.gz': b'ATCGATCGATCG' * 100,  # Larger content
                'chr2.fa.gz': b'GCTAGCTAGCTA' * 100,
                'chrX.fa.gz': b'TTAATTAATTAA' * 100
            }
            
            for filename, content in test_files.items():
                filepath = data_dir / filename
                filepath.write_bytes(content)
            
            yield data_dir
    
    def test_end_to_end_workflow(self, mock_downloaded_files):
        """Test complete workflow: calculate checksums, save manifest, verify integrity"""
        calculator = ChecksumCalculator(str(mock_downloaded_files))
        
        # Step 1: Generate manifest
        manifest = calculator.generate_manifest()
        assert len(manifest['files']) == 3
        assert manifest['metadata']['successful_files'] == 3
        
        # Step 2: Save manifest
        manifest_path = calculator.save_manifest(manifest)
        assert manifest_path.exists()
        
        # Step 3: Verify all files
        results = calculator.verify_all_files()
        assert all(results.values())
        
        # Step 4: Simulate file corruption and detect it
        corrupted_file = mock_downloaded_files / "chr1.fa.gz"
        corrupted_file.write_bytes(b'CORRUPTED')
        
        result = calculator.verify_file_integrity('chr1.fa.gz')
        assert result is False
    
    def test_manifest_contains_required_fields(self, mock_downloaded_files):
        """Test that manifest contains all required fields for validation"""
        calculator = ChecksumCalculator(str(mock_downloaded_files))
        manifest = calculator.generate_manifest()
        
        # Check metadata fields
        assert 'generated_at' in manifest['metadata']
        assert 'data_directory' in manifest['metadata']
        assert 'total_files' in manifest['metadata']
        assert 'total_size_bytes' in manifest['metadata']
        
        # Check file fields
        for filename, file_data in manifest['files'].items():
            assert 'filename' in file_data
            assert 'filepath' in file_data
            assert 'size_bytes' in file_data
            assert 'md5' in file_data
            assert 'sha256' in file_data
            assert 'calculated_at' in file_data
    
    def test_checksum_types_are_different(self, mock_downloaded_files):
        """Test that MD5 and SHA256 produce different checksums"""
        calculator = ChecksumCalculator(str(mock_downloaded_files))
        filepath = mock_downloaded_files / "chr1.fa.gz"
        
        checksums = calculator.calculate_file_checksums(filepath)
        
        # MD5 and SHA256 should be different
        assert checksums['md5'] != checksums['sha256']
        
        # MD5 should be 32 hex chars, SHA256 should be 64
        assert len(checksums['md5']) == 32
        assert len(checksums['sha256']) == 64
