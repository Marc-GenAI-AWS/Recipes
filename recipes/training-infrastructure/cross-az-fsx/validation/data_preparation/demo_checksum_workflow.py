#!/usr/bin/env python3
"""
Demonstration of checksum calculator workflow with hg38_downloader

This script demonstrates the complete workflow:
1. Download chromosome files (simulated)
2. Generate checksum manifest
3. Verify file integrity
4. Detect corruption
"""

import tempfile
from pathlib import Path
from checksum_calculator import ChecksumCalculator


def demo_workflow():
    """Demonstrate complete checksum workflow"""
    
    print("="*70)
    print("CHECKSUM CALCULATOR WORKFLOW DEMONSTRATION")
    print("="*70)
    print()
    
    # Create temporary directory with simulated downloaded files
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        
        # Step 1: Simulate downloaded chromosome files
        print("Step 1: Simulating downloaded chromosome files...")
        test_files = {
            'chr1.fa.gz': b'ATCGATCGATCG' * 1000,
            'chr2.fa.gz': b'GCTAGCTAGCTA' * 1000,
            'chrX.fa.gz': b'TTAATTAATTAA' * 1000
        }
        
        for filename, content in test_files.items():
            filepath = data_dir / filename
            filepath.write_bytes(content)
            print(f"  ✓ Created {filename} ({len(content)} bytes)")
        
        print()
        
        # Step 2: Initialize checksum calculator
        print("Step 2: Initializing checksum calculator...")
        calculator = ChecksumCalculator(str(data_dir))
        print(f"  ✓ Calculator initialized for {data_dir}")
        print()
        
        # Step 3: Generate manifest
        print("Step 3: Generating checksum manifest...")
        manifest = calculator.generate_manifest()
        manifest_path = calculator.save_manifest(manifest)
        
        metadata = manifest['metadata']
        print(f"  ✓ Manifest generated: {manifest_path}")
        print(f"    - Files: {metadata['total_files']}")
        print(f"    - Total size: {metadata['total_size_human']}")
        print(f"    - Successful: {metadata['successful_files']}")
        print()
        
        # Step 4: Display checksums
        print("Step 4: Checksum details...")
        for filename, file_data in sorted(manifest['files'].items()):
            print(f"  {filename}:")
            print(f"    MD5:    {file_data['md5']}")
            print(f"    SHA256: {file_data['sha256']}")
        print()
        
        # Step 5: Verify all files (should pass)
        print("Step 5: Verifying file integrity (initial)...")
        results = calculator.verify_all_files()
        for filename, is_valid in sorted(results.items()):
            status = "✓ PASS" if is_valid else "✗ FAIL"
            print(f"  {status} {filename}")
        print()
        
        # Step 6: Simulate file corruption
        print("Step 6: Simulating file corruption...")
        corrupted_file = data_dir / "chr2.fa.gz"
        corrupted_file.write_bytes(b'CORRUPTED_DATA')
        print(f"  ✗ Corrupted {corrupted_file.name}")
        print()
        
        # Step 7: Verify again (should detect corruption)
        print("Step 7: Verifying file integrity (after corruption)...")
        results = calculator.verify_all_files()
        for filename, is_valid in sorted(results.items()):
            status = "✓ PASS" if is_valid else "✗ FAIL"
            print(f"  {status} {filename}")
        print()
        
        # Step 8: Summary
        print("Step 8: Summary...")
        passed = sum(1 for v in results.values() if v)
        failed = len(results) - passed
        print(f"  Total files: {len(results)}")
        print(f"  Passed: {passed}")
        print(f"  Failed: {failed}")
        print()
        
        print("="*70)
        print("DEMONSTRATION COMPLETE")
        print("="*70)
        print()
        print("Key takeaways:")
        print("  1. Checksums are calculated for both MD5 and SHA256")
        print("  2. Manifest stores all checksum data in JSON format")
        print("  3. Verification detects file corruption reliably")
        print("  4. Integration with hg38_downloader is straightforward")
        print()


if __name__ == "__main__":
    demo_workflow()
