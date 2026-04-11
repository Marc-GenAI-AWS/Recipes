# HG38 Chromosome Data Downloader

This module provides functionality to download hg38 chromosome data from UCSC Genome Browser for use in cross-AZ FSx validation testing with BioNeMo Megatron Framework.

## Features

- **Selective Downloads**: Download specific chromosomes or all chromosomes
- **Progress Tracking**: Real-time progress updates during downloads
- **Error Handling**: Automatic retry logic with configurable attempts and delays
- **Resume Support**: Skip already downloaded files (unless forced)
- **Checksum Validation**: Calculate MD5 checksums for integrity verification
- **Configurable Timeouts**: Adjust timeout settings for different network conditions

## Data Source

Downloads from: https://hgdownload.soe.ucsc.edu/goldenpath/hg38/chromosomes/

## Usage

### Command Line Interface

#### Download All Chromosomes

```bash
python hg38_downloader.py --output-dir ./hg38_data
```

#### Download Specific Chromosomes

```bash
python hg38_downloader.py --output-dir ./hg38_data --chromosomes chr1 chr2 chrX
```

#### Force Re-download

```bash
python hg38_downloader.py --output-dir ./hg38_data --force
```

#### Custom Retry Configuration

```bash
python hg38_downloader.py \
    --output-dir ./hg38_data \
    --max-retries 5 \
    --retry-delay 10 \
    --timeout 600
```

### Python API

```python
from hg38_downloader import HG38Downloader

# Initialize downloader
downloader = HG38Downloader(
    output_dir="./hg38_data",
    max_retries=3,
    retry_delay=5,
    timeout=300
)

# Download specific chromosomes
results = downloader.download_chromosomes(['chr1', 'chr2', 'chrX'])

# Download all chromosomes
results = downloader.download_all_chromosomes()

# Access download metadata
for result in results:
    print(f"Chromosome: {result['chromosome']}")
    print(f"Size: {result['size_bytes']} bytes")
    print(f"Checksum: {result['checksum_md5']}")
    print(f"Status: {result['status']}")
```

## Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--output-dir` | Output directory for downloaded files | `./hg38_data` |
| `--chromosomes` | Specific chromosomes to download (space-separated) | All chromosomes |
| `--force` | Force re-download even if files exist | `False` |
| `--max-retries` | Maximum number of retry attempts | `3` |
| `--retry-delay` | Delay in seconds between retries | `5` |
| `--timeout` | Timeout in seconds for each download | `300` |

## Available Chromosomes

The downloader supports all human chromosomes:
- Autosomes: chr1 through chr22
- Sex chromosomes: chrX, chrY
- Mitochondrial: chrM

Total: 25 chromosomes

## Download Metadata

Each download returns a dictionary with the following information:

```python
{
    "chromosome": "chr1",           # Chromosome name
    "filename": "chr1.fa.gz",       # Downloaded filename
    "filepath": "/path/to/chr1.fa.gz",  # Full path to file
    "size_bytes": 248956422,        # File size in bytes
    "download_time_seconds": 45.2,  # Time taken to download
    "checksum_md5": "abc123...",    # MD5 checksum
    "status": "downloaded"          # Status: downloaded, skipped, or failed
}
```

## Error Handling

The downloader implements robust error handling:

1. **Network Errors**: Automatically retries with exponential backoff
2. **Timeout Errors**: Retries with the same timeout setting
3. **Partial Downloads**: Cleans up incomplete files before retry
4. **Max Retries Exceeded**: Raises `DownloadError` with details

## Testing

Run the unit tests:

```bash
python -m pytest test_hg38_downloader.py -v
```

## Integration with Validation Phases

The downloader is designed to support the incremental validation phases:

### Phase 2.5: 10GB Dataset (chr1, chr2)
```bash
python hg38_downloader.py --output-dir ./data/10gb --chromosomes chr1 chr2
```

### Phase 2.6: 100GB Dataset (chr1-chr10)
```bash
python hg38_downloader.py --output-dir ./data/100gb --chromosomes chr1 chr2 chr3 chr4 chr5 chr6 chr7 chr8 chr9 chr10
```

### Phase 2.7: 500GB Dataset (chr1-chr22, chrX)
```bash
python hg38_downloader.py --output-dir ./data/500gb --chromosomes chr{1..22} chrX
```

### Phase 2.8-2.9: 1TB and 2TB Datasets
For larger datasets, download all chromosomes and use preprocessing/duplication:
```bash
python hg38_downloader.py --output-dir ./data/all_chromosomes
```

## Logging

The downloader uses Python's logging module with INFO level by default. Logs include:
- Download progress (every 10%)
- Retry attempts
- Success/failure status
- File sizes and checksums
- Summary statistics

## Performance Considerations

- **Parallel Downloads**: Not implemented to avoid overwhelming UCSC servers
- **Chunk Size**: 8KB chunks for efficient memory usage
- **Progress Updates**: Every 10% to balance visibility and log volume
- **Checksum Calculation**: Performed after download completes

## License

This tool is part of the cross-AZ FSx validation project and follows the project's licensing terms.

## Support

For issues or questions, refer to the main project documentation or contact the development team.
