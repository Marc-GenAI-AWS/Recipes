# HG38 Downloader Quick Start Guide

## Quick Commands

### Download a Single Small Chromosome (for testing)
```bash
python hg38_downloader.py --output-dir ./test_data --chromosomes chrM
```

### Prepare 10GB Dataset (Phase 2.5)
```bash
python prepare_validation_datasets.py --output-dir ./validation_datasets --phases 10GB
```

### Prepare All Validation Datasets
```bash
python prepare_validation_datasets.py --output-dir ./validation_datasets
```

### List Available Phases
```bash
python prepare_validation_datasets.py --list-phases
```

## Validation Phase Datasets

| Phase | Size | Chromosomes | Use Case |
|-------|------|-------------|----------|
| 10GB | ~10GB | chr1, chr2 | Initial validation |
| 100GB | ~100GB | chr1-chr10 | Small-scale testing |
| 500GB | ~500GB | chr1-chr22, chrX | Medium-scale testing |
| 1TB | ~1TB | All chromosomes | Large-scale testing |
| 2TB | ~2TB | All chromosomes (duplicated) | Maximum-scale testing |

## Common Use Cases

### 1. Test the Downloader
Download the smallest chromosome to verify everything works:
```bash
python hg38_downloader.py --output-dir ./test --chromosomes chrM --timeout 60
```

### 2. Prepare Initial Validation Dataset
Start with the 10GB dataset for initial testing:
```bash
python prepare_validation_datasets.py --output-dir ./data --phases 10GB
```

### 3. Prepare Multiple Phases
Prepare 10GB and 100GB datasets:
```bash
python prepare_validation_datasets.py --output-dir ./data --phases 10GB 100GB
```

### 4. Force Re-download
Re-download all files even if they exist:
```bash
python prepare_validation_datasets.py --output-dir ./data --phases 10GB --force
```

### 5. Download Custom Chromosome Set
Download specific chromosomes:
```bash
python hg38_downloader.py --output-dir ./custom --chromosomes chr1 chr2 chrX chrY
```

## Output Structure

After running `prepare_validation_datasets.py`, you'll have:

```
validation_datasets/
├── preparation_summary.json          # Overall summary
├── 10gb/
│   ├── chr1.fa.gz
│   ├── chr2.fa.gz
│   └── metadata.json                 # Phase metadata
├── 100gb/
│   ├── chr1.fa.gz
│   ├── chr2.fa.gz
│   ├── ...
│   ├── chr10.fa.gz
│   └── metadata.json
└── ...
```

## Metadata Files

Each phase directory contains a `metadata.json` file with:
- Phase information
- List of chromosomes
- Download results
- File sizes and checksums
- Success/failure status

Example:
```json
{
  "phase": "10GB",
  "description": "Phase 2.5: 10GB validation dataset",
  "total_chromosomes": 2,
  "successful_downloads": 2,
  "failed_downloads": 0,
  "total_size_gb": 9.87,
  "download_results": [...]
}
```

## Troubleshooting

### Download Fails with Timeout
Increase the timeout:
```bash
python hg38_downloader.py --output-dir ./data --chromosomes chr1 --timeout 1200
```

### Network Interruption
The downloader automatically retries. Adjust retry settings:
```bash
python hg38_downloader.py --output-dir ./data --chromosomes chr1 --max-retries 5 --retry-delay 10
```

### Resume Interrupted Downloads
Simply re-run the same command. Already downloaded files will be skipped:
```bash
python prepare_validation_datasets.py --output-dir ./data --phases 10GB
```

### Check Download Integrity
Verify checksums in the metadata.json file or re-calculate:
```python
from hg38_downloader import HG38Downloader
downloader = HG38Downloader(output_dir="./data/10gb")
checksum = downloader._calculate_md5("./data/10gb/chr1.fa.gz")
print(f"MD5: {checksum}")
```

## Performance Tips

1. **Start Small**: Test with chrM (smallest) before downloading large chromosomes
2. **Check Disk Space**: Ensure sufficient space before starting large downloads
3. **Stable Network**: Use a stable network connection for large downloads
4. **Sequential Downloads**: The downloader processes chromosomes sequentially to avoid overwhelming UCSC servers

## Estimated Download Times

Approximate times on a 100 Mbps connection:

| Dataset | Size | Chromosomes | Estimated Time |
|---------|------|-------------|----------------|
| chrM | ~5 KB | 1 | < 1 second |
| 10GB | ~10 GB | 2 | 15-20 minutes |
| 100GB | ~100 GB | 10 | 2-3 hours |
| 500GB | ~500 GB | 23 | 10-12 hours |
| 1TB | ~1 TB | 25 | 20-24 hours |

*Note: Actual times vary based on network speed and UCSC server load*

## Next Steps

After downloading datasets:
1. Verify checksums in metadata.json
2. Upload to FSx volume (Task 2.3)
3. Run data integrity validation (Task 2.4)
4. Proceed with validation phases (Phase 6)

## Support

For issues or questions:
- Check the main README.md for detailed documentation
- Review error logs for specific error messages
- Verify network connectivity to UCSC servers
- Ensure sufficient disk space
