#!/usr/bin/env python3
"""
Unit tests for hg38_downloader module
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
from urllib.error import URLError

from hg38_downloader import HG38Downloader, DownloadError, ALL_CHROMOSOMES


class TestHG38Downloader(unittest.TestCase):
    """Test cases for HG38Downloader class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.downloader = HG38Downloader(
            output_dir=self.temp_dir,
            max_retries=2,
            retry_delay=1,
            timeout=30
        )
    
    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_initialization(self):
        """Test downloader initialization creates output directory"""
        self.assertTrue(Path(self.temp_dir).exists())
        self.assertEqual(self.downloader.max_retries, 2)
        self.assertEqual(self.downloader.retry_delay, 1)
        self.assertEqual(self.downloader.timeout, 30)
    
    def test_format_size(self):
        """Test byte size formatting"""
        self.assertEqual(HG38Downloader._format_size(500), "500.00 B")
        self.assertEqual(HG38Downloader._format_size(1024), "1.00 KB")
        self.assertEqual(HG38Downloader._format_size(1024 * 1024), "1.00 MB")
        self.assertEqual(HG38Downloader._format_size(1024 * 1024 * 1024), "1.00 GB")
    
    def test_all_chromosomes_list(self):
        """Test that ALL_CHROMOSOMES contains expected chromosomes"""
        self.assertIn("chr1", ALL_CHROMOSOMES)
        self.assertIn("chr22", ALL_CHROMOSOMES)
        self.assertIn("chrX", ALL_CHROMOSOMES)
        self.assertIn("chrY", ALL_CHROMOSOMES)
        self.assertIn("chrM", ALL_CHROMOSOMES)
        self.assertEqual(len(ALL_CHROMOSOMES), 25)  # chr1-22 + X, Y, M
    
    @patch('hg38_downloader.urlopen')
    def test_download_chromosome_success(self, mock_urlopen):
        """Test successful chromosome download"""
        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.headers.get.return_value = '100'
        mock_response.read.side_effect = [b'test_data', b'']
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = self.downloader.download_chromosome('chr1')
        
        self.assertEqual(result['chromosome'], 'chr1')
        self.assertEqual(result['filename'], 'chr1.fa.gz')
        self.assertEqual(result['status'], 'downloaded')
        self.assertIn('checksum_md5', result)
        self.assertGreater(result['size_bytes'], 0)
    
    def test_download_chromosome_skip_existing(self):
        """Test that existing files are skipped"""
        # Create a dummy file
        test_file = Path(self.temp_dir) / "chr1.fa.gz"
        test_file.write_bytes(b"existing_data")
        
        result = self.downloader.download_chromosome('chr1', force=False)
        
        self.assertEqual(result['status'], 'skipped')
        self.assertEqual(result['chromosome'], 'chr1')
        self.assertEqual(result['download_time_seconds'], 0)
    
    def test_download_chromosome_force_redownload(self):
        """Test force re-download of existing file"""
        # Create a dummy file
        test_file = Path(self.temp_dir) / "chr1.fa.gz"
        test_file.write_bytes(b"existing_data")
        
        with patch('hg38_downloader.urlopen') as mock_urlopen:
            mock_response = MagicMock()
            mock_response.headers.get.return_value = '100'
            mock_response.read.side_effect = [b'new_data', b'']
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            result = self.downloader.download_chromosome('chr1', force=True)
            
            self.assertEqual(result['status'], 'downloaded')
    
    @patch('hg38_downloader.urlopen')
    def test_download_chromosome_retry_on_failure(self, mock_urlopen):
        """Test retry logic on download failure"""
        # First attempt fails, second succeeds
        mock_response_fail = MagicMock()
        mock_response_fail.read.side_effect = URLError("Network error")
        
        mock_response_success = MagicMock()
        mock_response_success.headers.get.return_value = '100'
        mock_response_success.read.side_effect = [b'test_data', b'']
        
        mock_urlopen.return_value.__enter__.side_effect = [
            URLError("Network error"),
            mock_response_success
        ]
        
        result = self.downloader.download_chromosome('chr1')
        
        self.assertEqual(result['status'], 'downloaded')
        self.assertEqual(mock_urlopen.call_count, 2)
    
    @patch('hg38_downloader.urlopen')
    def test_download_chromosome_max_retries_exceeded(self, mock_urlopen):
        """Test that DownloadError is raised after max retries"""
        mock_urlopen.return_value.__enter__.side_effect = URLError("Network error")
        
        with self.assertRaises(DownloadError):
            self.downloader.download_chromosome('chr1')
        
        # Should attempt max_retries times
        self.assertEqual(mock_urlopen.call_count, self.downloader.max_retries)
    
    @patch.object(HG38Downloader, 'download_chromosome')
    def test_download_chromosomes_multiple(self, mock_download):
        """Test downloading multiple chromosomes"""
        mock_download.return_value = {
            'chromosome': 'chr1',
            'status': 'downloaded',
            'size_bytes': 1000,
            'download_time_seconds': 1.0
        }
        
        chromosomes = ['chr1', 'chr2', 'chr3']
        results = self.downloader.download_chromosomes(chromosomes)
        
        self.assertEqual(len(results), 3)
        self.assertEqual(mock_download.call_count, 3)
    
    @patch.object(HG38Downloader, 'download_chromosome')
    def test_download_chromosomes_handles_failures(self, mock_download):
        """Test that download_chromosomes handles individual failures"""
        # First succeeds, second fails, third succeeds
        mock_download.side_effect = [
            {'chromosome': 'chr1', 'status': 'downloaded', 'size_bytes': 1000, 'download_time_seconds': 1.0},
            DownloadError("Download failed"),
            {'chromosome': 'chr3', 'status': 'downloaded', 'size_bytes': 1000, 'download_time_seconds': 1.0}
        ]
        
        chromosomes = ['chr1', 'chr2', 'chr3']
        results = self.downloader.download_chromosomes(chromosomes)
        
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]['status'], 'downloaded')
        self.assertEqual(results[1]['status'], 'failed')
        self.assertEqual(results[2]['status'], 'downloaded')
    
    @patch.object(HG38Downloader, 'download_chromosomes')
    def test_download_all_chromosomes(self, mock_download_chromosomes):
        """Test download_all_chromosomes calls download_chromosomes with all chromosomes"""
        mock_download_chromosomes.return_value = []
        
        self.downloader.download_all_chromosomes()
        
        mock_download_chromosomes.assert_called_once_with(ALL_CHROMOSOMES, force=False)
    
    def test_calculate_md5(self):
        """Test MD5 checksum calculation"""
        # Create a test file
        test_file = Path(self.temp_dir) / "test.txt"
        test_data = b"test data for checksum"
        test_file.write_bytes(test_data)
        
        checksum = self.downloader._calculate_md5(test_file)
        
        # Verify it's a valid MD5 hex string
        self.assertEqual(len(checksum), 32)
        self.assertTrue(all(c in '0123456789abcdef' for c in checksum))
        
        # Verify consistency
        checksum2 = self.downloader._calculate_md5(test_file)
        self.assertEqual(checksum, checksum2)


if __name__ == '__main__':
    unittest.main()
