# Data Integrity Validator

## Overview

The Data Integrity Validator verifies data integrity before and after FSx upload by comparing checksums and file sizes between source files and FSx destination files. It integrates with the existing `checksum_calculator` and `fsx_uploader` modules to provide comprehensive validation for the cross-AZ FSx validation project.

## Features

- **File Integrity Verification**: Compare checksums (MD5 and SHA256) and file sizes between source and destination
- **Batch Validation**: Validate multiple files matching a pattern
- **Comprehensive Reporting**: Generate JSON and human-readable text reports
- **Error Detection**: Identify missing files, size mismatches, and checksum mismatches
- **Integration**: Works seamlessly with existing checksum_calculator and fsx_uploader modules
- **CLI and Python API**: Use from command line or import as a Python module

## Installation

No additional dependencies required beyond the existing project dependencies:

```bash
# Ensure you have the required modules
pip install -r requirements.txt  # If available
```

## Usage

### Command Line Interface

#### Basic Validation

Validate all `.fa.gz` files uploaded to FSx:

```bash
python data_integrity_validator.py \
    --source-dir ./hg38_data \
    --fsx-mount /mnt/fsx
```

#### Validation with Subdirectory

Validate files in a specific FSx subdirectory:

```bash
python data_integrity_validator.py \
    --source-dir ./hg38_data \
    --fsx-mount /mnt/fsx \
    --dest-subdir hg38_chromosomes
```

#### Custom File Pattern

Validate files matching a custom pattern:

```bash
python data_integrity_validator.py \
    --source-dir ./hg38_data \
    --fsx-mount /mnt/fsx \
    --pattern "chr*.fa.gz"
```

#### Custom Report Path

Save validation report to a custom location:

```bash
python data_integrity_validator.py \
    --source-dir ./hg38_data \
    --fsx-mount /mnt/fsx \
    --report /path/to/custom_report.json
```

#### With Checksum Manifest

Use an existing checksum manifest:

```bash
python data_integrity_validator.py \
    --source-dir ./hg38_data \
    --fsx-mount /mnt/fsx \
    --manifest ./hg38_data/checksums_manifest.json
```

### Python API

#### Basic Usage

```python
from data_integrity_validator import DataIntegrityValidator

# Initialize validator
validator = DataIntegrityValidator(
    source_dir="./hg38_data",
    fsx_mount_path="/mnt/fsx"
)

# Validate all uploaded files
results = validator.validate_upload(pattern="*.fa.gz")

# Generate report
report_path = validator.generate_validation_report(results)

print(f"Validation complete: {results['valid_files']}/{results['total_files']} files valid")
print(f"Report saved to: {report_path}")
```

#### Validate Single File

```python
from pathlib import Path
from data_integrity_validator import DataIntegrityValidator

validator = DataIntegrityValidator(
    source_dir="./hg38_data",
    fsx_mount_path="/mnt/fsx"
)

source_file = Path("./hg38_data/chr1.fa.gz")
dest_file = Path("/mnt/fsx/chr1.fa.gz")

result = validator.verify_file_integrity(source_file, dest_file)

if result["valid"]:
    print(f"✓ {result['filename']} integrity verified")
else:
    print(f"✗ {result['filename']} validation failed: {result['error_message']}")
```

#### Validate with Subdirectory

```python
validator = DataIntegrityValidator(
    source_dir="./hg38_data",
    fsx_mount_path="/mnt/fsx"
)

results = validator.validate_upload(
    dest_subdir="hg38_chromosomes",
    pattern="*.fa.gz"
)

if results["invalid_files"] == 0:
    print("All files validated successfully!")
else:
    print(f"Warning: {results['invalid_files']} files failed validation")
```

#### Custom Report Generation

```python
validator = DataIntegrityValidator(
    source_dir="./hg38_data",
    fsx_mount_path="/mnt/fsx"
)

results = validator.validate_upload()

# Generate report with custom path
report_path = validator.generate_validation_report(
    results,
    report_path="./reports/validation_2024_01_15.json"
)
```

## Integration with Existing Modules

### With Checksum Calculator

```python
from checksum_calculator import ChecksumCalculator
from data_integrity_validator import DataIntegrityValidator

# Generate checksums before upload
calculator = ChecksumCalculator(data_dir="./hg38_data")
manifest = calculator.generate_manifest()
calculator.save_manifest()

# ... perform upload with fsx_uploader ...

# Validate after upload
validator = DataIntegrityValidator(
    source_dir="./hg38_data",
    fsx_mount_path="/mnt/fsx",
    checksum_manifest_path="./hg38_data/checksums_manifest.json"
)

results = validator.validate_upload()
```

### Complete Workflow with FSx Uploader

```python
from checksum_calculator import ChecksumCalculator
from fsx_uploader import FSxUploader
from data_integrity_validator import DataIntegrityValidator

# Step 1: Calculate checksums
calculator = ChecksumCalculator(data_dir="./hg38_data")
manifest = calculator.generate_manifest()
calculator.save_manifest()

# Step 2: Upload to FSx
uploader = FSxUploader(
    source_dir="./hg38_data",
    fsx_mount_point="/mnt/fsx",
    verify_checksums=True
)

if uploader.verify_mount_access():
    upload_result = uploader.upload_directory(dest_subdir="hg38_chromosomes")
    uploader.save_upload_manifest(upload_result)
    
    # Step 3: Validate upload integrity
    validator = DataIntegrityValidator(
        source_dir="./hg38_data",
        fsx_mount_path="/mnt/fsx"
    )
    
    validation_results = validator.validate_upload(dest_subdir="hg38_chromosomes")
    report_path = validator.generate_validation_report(validation_results)
    
    if validation_results["invalid_files"] == 0:
        print("✓ All files uploaded and validated successfully")
    else:
        print(f"✗ {validation_results['invalid_files']} files failed validation")
```

## Validation Report Format

### JSON Report

The validator generates a comprehensive JSON report:

```json
{
  "validation_summary": {
    "total_files": 3,
    "valid_files": 3,
    "invalid_files": 0,
    "success_rate": 100.0,
    "total_size_bytes": 1234567890,
    "total_size_human": "1.15 GB",
    "validation_timestamp": "2024-01-15T10:30:45Z"
  },
  "configuration": {
    "source_dir": "/path/to/hg38_data",
    "fsx_mount_path": "/mnt/fsx",
    "dest_subdir": "hg38_chromosomes"
  },
  "file_results": [
    {
      "filename": "chr1.fa.gz",
      "source_path": "/path/to/hg38_data/chr1.fa.gz",
      "dest_path": "/mnt/fsx/hg38_chromosomes/chr1.fa.gz",
      "source_size": 248956422,
      "dest_size": 248956422,
      "size_match": true,
      "source_md5": "abc123...",
      "dest_md5": "abc123...",
      "source_sha256": "def456...",
      "dest_sha256": "def456...",
      "checksum_match": true,
      "valid": true
    }
  ],
  "failed_files": []
}
```

### Text Report

A human-readable text summary is also generated:

```
================================================================================
DATA INTEGRITY VALIDATION REPORT
================================================================================

Validation Timestamp: 2024-01-15T10:30:45Z

Configuration:
  Source Directory: /path/to/hg38_data
  FSx Mount Path:   /mnt/fsx
  Destination Subdir: hg38_chromosomes

Summary:
  Total Files:    3
  Valid Files:    3
  Invalid Files:  0
  Success Rate:   100.00%
  Total Size:     1.15 GB

================================================================================
Validation PASSED
================================================================================
```

## Error Handling

The validator detects and reports various error conditions:

### Missing Destination File

```
✗ chr1.fa.gz: Destination file not found
```

### Size Mismatch

```
✗ chr2.fa.gz: Size mismatch
  Source: 248.96 MB
  Dest:   248.50 MB
```

### Checksum Mismatch

```
✗ chr3.fa.gz: MD5 mismatch
  Source: abc123def456...
  Dest:   xyz789uvw012...
```

## Exit Codes

When used from the command line:

- `0`: All files validated successfully
- `1`: One or more files failed validation or fatal error occurred

## Performance Considerations

- **Checksum Calculation**: The validator calculates both MD5 and SHA256 checksums, which can be time-consuming for large files
- **Parallel Processing**: For large datasets, consider validating files in batches
- **Network I/O**: Reading from FSx mount involves network I/O, which may be slower than local disk

## Best Practices

1. **Generate Checksums Before Upload**: Use `checksum_calculator` to generate checksums before uploading
2. **Validate After Upload**: Always validate after upload to ensure data integrity
3. **Save Reports**: Keep validation reports for audit trails
4. **Monitor Failed Files**: Investigate and re-upload any files that fail validation
5. **Use Subdirectories**: Organize data in subdirectories for better management

## Troubleshooting

### "Source directory does not exist"

Ensure the source directory path is correct and accessible.

### "FSx mount path does not exist"

Verify that the FSx volume is properly mounted at the specified path.

### "Destination directory does not exist"

If using `--dest-subdir`, ensure the subdirectory exists on the FSx mount.

### Slow Validation

For large files, checksum calculation can be slow. This is expected behavior. Consider:
- Validating in smaller batches
- Using faster storage for source files
- Ensuring good network connectivity to FSx mount

### All Files Failing Validation

Check:
- FSx mount is accessible and readable
- Files were actually uploaded to the correct location
- No corruption occurred during upload

## Testing

Run the unit tests:

```bash
python -m pytest test_data_integrity_validator.py -v
```

Run specific test:

```bash
python -m pytest test_data_integrity_validator.py::TestDataIntegrityValidator::test_verify_file_integrity_matching_files -v
```

## Related Modules

- **checksum_calculator.py**: Calculates checksums and generates manifests
- **fsx_uploader.py**: Uploads files to FSx with integrity verification
- **hg38_downloader.py**: Downloads hg38 chromosome data from UCSC

## License

Part of the cross-AZ FSx validation project.

## Support

For issues or questions, refer to the project documentation or contact the development team.
