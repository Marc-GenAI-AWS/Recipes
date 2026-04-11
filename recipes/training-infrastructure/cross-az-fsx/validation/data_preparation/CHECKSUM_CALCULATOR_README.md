# Checksum Calculator for hg38 Chromosome Files

This module calculates MD5 and SHA256 checksums for downloaded hg38 chromosome files and stores them in a manifest file for data integrity validation.

## Features

- Calculate MD5 and SHA256 checksums for chromosome files
- Generate manifest files with checksum metadata
- Verify file integrity against stored checksums
- Support for batch processing of multiple files
- Human-readable size formatting
- Detailed logging

## Installation

No additional dependencies required beyond Python standard library.

## Usage

### Command Line Interface

The checksum calculator provides three main commands:

#### 1. Generate Manifest

Generate a manifest file with checksums for all chromosome files:

```bash
python checksum_calculator.py --data-dir ./hg38_data generate
```

This will:
- Calculate MD5 and SHA256 checksums for all `*.fa.gz` files
- Store results in `./hg38_data/checksums_manifest.json`
- Include metadata (file count, total size, timestamp)

#### 2. Verify File Integrity

Verify a specific file against the manifest:

```bash
python checksum_calculator.py --data-dir ./hg38_data verify --file chr1.fa.gz
```

Verify all files in the manifest:

```bash
python checksum_calculator.py --data-dir ./hg38_data verify
```

#### 3. Calculate Checksums

Calculate checksums for a single file without updating the manifest:

```bash
python checksum_calculator.py --data-dir ./hg38_data calculate chr1.fa.gz
```

### Python API

#### Basic Usage

```python
from checksum_calculator import ChecksumCalculator

# Initialize calculator
calculator = ChecksumCalculator(data_dir="./hg38_data")

# Generate and save manifest
manifest = calculator.generate_manifest()
calculator.save_manifest(manifest)

# Verify file integrity
is_valid = calculator.verify_file_integrity("chr1.fa.gz")
print(f"File is valid: {is_valid}")

# Verify all files
results = calculator.verify_all_files()
for filename, is_valid in results.items():
    print(f"{filename}: {'✓' if is_valid else '✗'}")
```

#### Calculate Checksums for a Single File

```python
from pathlib import Path
from checksum_calculator import ChecksumCalculator

calculator = ChecksumCalculator(data_dir="./hg38_data")
filepath = Path("./hg38_data/chr1.fa.gz")

checksums = calculator.calculate_file_checksums(filepath)
print(f"MD5:    {checksums['md5']}")
print(f"SHA256: {checksums['sha256']}")
```

#### Custom Manifest Path

```python
calculator = ChecksumCalculator(
    data_dir="./hg38_data",
    manifest_path="./custom_manifest.json"
)
```

#### Custom File Pattern

```python
# Process only specific chromosomes
manifest = calculator.generate_manifest(pattern="chr[1-5].fa.gz")
```

## Manifest Format

The manifest file is a JSON document with the following structure:

```json
{
  "metadata": {
    "generated_at": "2024-01-15T10:30:45Z",
    "data_directory": "/path/to/hg38_data",
    "file_pattern": "*.fa.gz",
    "total_files": 3,
    "successful_files": 3,
    "failed_files": 0,
    "total_size_bytes": 1234567890,
    "total_size_human": "1.15 GB"
  },
  "files": {
    "chr1.fa.gz": {
      "filename": "chr1.fa.gz",
      "filepath": "/path/to/hg38_data/chr1.fa.gz",
      "size_bytes": 248956422,
      "size_human": "237.45 MB",
      "md5": "abc123def456...",
      "sha256": "789ghi012jkl...",
      "calculated_at": "2024-01-15T10:30:45Z"
    }
  }
}
```

## Integration with hg38_downloader

The checksum calculator is designed to work seamlessly with the hg38_downloader:

```python
from hg38_downloader import HG38Downloader
from checksum_calculator import ChecksumCalculator

# Step 1: Download chromosomes
downloader = HG38Downloader(output_dir="./hg38_data")
results = downloader.download_chromosomes(["chr1", "chr2", "chrX"])

# Step 2: Generate checksums and manifest
calculator = ChecksumCalculator(data_dir="./hg38_data")
manifest = calculator.generate_manifest()
calculator.save_manifest(manifest)

# Step 3: Verify integrity before uploading to FSx
verification_results = calculator.verify_all_files()
if all(verification_results.values()):
    print("All files verified successfully")
else:
    print("Some files failed verification")
```

## Use Cases

### 1. Post-Download Validation

After downloading chromosome files, generate a manifest to ensure data integrity:

```bash
# Download chromosomes
python hg38_downloader.py --output-dir ./hg38_data --chromosomes chr1 chr2

# Generate checksum manifest
python checksum_calculator.py --data-dir ./hg38_data generate
```

### 2. Pre-Upload Verification

Before uploading to FSx, verify all files are intact:

```bash
python checksum_calculator.py --data-dir ./hg38_data verify
```

### 3. Post-Upload Verification

After uploading to FSx, verify files on the remote system:

```bash
# On the system with FSx mount
python checksum_calculator.py --data-dir /mnt/fsx/hg38_data verify
```

### 4. Corruption Detection

Detect file corruption during transfer or storage:

```python
calculator = ChecksumCalculator(data_dir="./hg38_data")

# Verify before transfer
pre_transfer = calculator.verify_all_files()

# ... transfer files ...

# Verify after transfer
post_transfer = calculator.verify_all_files()

# Compare results
for filename in pre_transfer:
    if pre_transfer[filename] and not post_transfer[filename]:
        print(f"File corrupted during transfer: {filename}")
```

## Error Handling

The calculator handles various error scenarios:

- **Missing files**: Returns `False` for verification
- **Corrupted files**: Detects checksum mismatches
- **Invalid directory**: Raises `ValueError` on initialization
- **Missing manifest**: Raises `FileNotFoundError` when loading

All errors are logged with detailed information for troubleshooting.

## Testing

Run the test suite:

```bash
# Unit tests
python -m pytest test_checksum_calculator.py -v

# Integration tests
python -m pytest test_checksum_integration.py -v

# All tests
python -m pytest test_checksum*.py -v
```

## Performance Considerations

- Checksum calculation is I/O bound
- Processing large files (>1GB) may take several minutes
- Both MD5 and SHA256 are calculated in a single pass for efficiency
- Files are read in 8KB chunks to minimize memory usage

## Logging

The module uses Python's logging framework. Configure logging level as needed:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Log levels:
- `INFO`: Progress updates, successful operations
- `ERROR`: Verification failures, file errors
- `DEBUG`: Detailed operation information

## Related Modules

- `hg38_downloader.py`: Downloads chromosome files from UCSC
- `prepare_validation_datasets.py`: Prepares datasets for validation phases

## License

Part of the cross-AZ FSx validation system.
