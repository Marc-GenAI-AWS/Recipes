#!/usr/bin/env python3
"""
SageMaker Training Script for Cross-AZ FSx Validation

This script runs inside a SageMaker training job to validate:
1. Cross-AZ FSx mount establishment
2. Data accessibility and integrity
3. Read performance metrics
4. Network latency measurements

This is a simplified validation before full BioNeMo integration.
"""

import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import boto3

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FSxValidator:
    """Validates cross-AZ FSx access from SageMaker"""
    
    def __init__(self):
        """Initialize validator"""
        self.fsx_dns = os.environ.get('FSX_DNS_NAME')
        self.fsx_mount_path = os.environ.get('FSX_MOUNT_PATH', '/genomics')
        self.data_subdir = os.environ.get('DATA_SUBDIR', 'phase_10gb')
        self.fsx_az = os.environ.get('FSX_AZ')
        self.training_az = os.environ.get('TRAINING_AZ')
        self.mount_point = '/mnt/fsx'
        
        self.cloudwatch = boto3.client('cloudwatch', region_name='us-west-2')
        
        logger.info("FSx Validator initialized")
        logger.info(f"  FSx DNS: {self.fsx_dns}")
        logger.info(f"  FSx Mount Path: {self.fsx_mount_path}")
        logger.info(f"  Data Subdir: {self.data_subdir}")
        logger.info(f"  FSx AZ: {self.fsx_az}")
        logger.info(f"  Training AZ: {self.training_az}")
        logger.info(f"  Cross-AZ: {self.fsx_az != self.training_az}")
    
    def mount_fsx(self) -> Dict[str, any]:
        """
        Mount FSx volume via NFS
        
        Returns:
            Dictionary with mount result
        """
        logger.info("========================================")
        logger.info("Mounting FSx Volume")
        logger.info("========================================")
        
        start_time = time.time()
        
        try:
            # Create mount point
            os.makedirs(self.mount_point, exist_ok=True)
            logger.info(f"Created mount point: {self.mount_point}")
            
            # Mount FSx volume
            mount_cmd = [
                'mount',
                '-t', 'nfs',
                '-o', 'nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2',
                f"{self.fsx_dns}:{self.fsx_mount_path}",
                self.mount_point
            ]
            
            logger.info(f"Mount command: {' '.join(mount_cmd)}")
            
            result = subprocess.run(
                mount_cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                raise Exception(f"Mount failed: {result.stderr}")
            
            mount_time = time.time() - start_time
            
            logger.info(f"✓ FSx volume mounted successfully")
            logger.info(f"  Mount time: {mount_time:.2f} seconds")
            
            # Verify mount
            if not os.path.ismount(self.mount_point):
                raise Exception("Mount verification failed")
            
            logger.info(f"✓ Mount verified")
            
            return {
                'success': True,
                'mount_time_seconds': mount_time,
                'mount_point': self.mount_point
            }
            
        except Exception as e:
            logger.error(f"✗ Mount failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'mount_time_seconds': time.time() - start_time
            }
    
    def list_data_files(self) -> List[str]:
        """
        List files in data subdirectory
        
        Returns:
            List of file paths
        """
        data_path = Path(self.mount_point) / self.data_subdir
        
        logger.info(f"Listing files in: {data_path}")
        
        if not data_path.exists():
            logger.warning(f"Data path does not exist: {data_path}")
            return []
        
        files = list(data_path.glob("*.fa.gz"))
        
        logger.info(f"Found {len(files)} files:")
        for f in files:
            size_mb = f.stat().st_size / (1024 * 1024)
            logger.info(f"  {f.name}: {size_mb:.2f} MB")
        
        return [str(f) for f in files]
    
    def measure_read_performance(self, file_path: str, chunk_size_mb: int = 10) -> Dict[str, any]:
        """
        Measure read performance for a file
        
        Args:
            file_path: Path to file
            chunk_size_mb: Chunk size for reading (MB)
            
        Returns:
            Dictionary with performance metrics
        """
        logger.info(f"Measuring read performance: {Path(file_path).name}")
        
        chunk_size = chunk_size_mb * 1024 * 1024
        total_bytes = 0
        start_time = time.time()
        
        try:
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    total_bytes += len(chunk)
            
            duration = time.time() - start_time
            throughput_mbps = (total_bytes / (1024 * 1024)) / duration
            
            logger.info(f"  Total bytes: {total_bytes / (1024 * 1024):.2f} MB")
            logger.info(f"  Duration: {duration:.2f} seconds")
            logger.info(f"  Throughput: {throughput_mbps:.2f} MB/s")
            
            return {
                'success': True,
                'file': Path(file_path).name,
                'total_bytes': total_bytes,
                'duration_seconds': duration,
                'throughput_mbps': throughput_mbps
            }
            
        except Exception as e:
            logger.error(f"  Read failed: {e}")
            return {
                'success': False,
                'file': Path(file_path).name,
                'error': str(e)
            }
    
    def measure_latency(self, num_samples: int = 100) -> Dict[str, any]:
        """
        Measure network latency by reading small chunks
        
        Args:
            num_samples: Number of latency samples to collect
            
        Returns:
            Dictionary with latency metrics
        """
        logger.info(f"Measuring network latency ({num_samples} samples)")
        
        # Create a small test file
        test_file = Path(self.mount_point) / ".latency_test"
        test_data = b"x" * 1024  # 1 KB
        
        try:
            # Write test file
            with open(test_file, 'wb') as f:
                f.write(test_data)
            
            latencies = []
            
            for i in range(num_samples):
                start = time.time()
                with open(test_file, 'rb') as f:
                    f.read()
                latency_ms = (time.time() - start) * 1000
                latencies.append(latency_ms)
            
            # Clean up
            test_file.unlink()
            
            latencies.sort()
            
            metrics = {
                'success': True,
                'num_samples': num_samples,
                'min_latency_ms': min(latencies),
                'max_latency_ms': max(latencies),
                'avg_latency_ms': sum(latencies) / len(latencies),
                'p50_latency_ms': latencies[len(latencies) // 2],
                'p95_latency_ms': latencies[int(len(latencies) * 0.95)],
                'p99_latency_ms': latencies[int(len(latencies) * 0.99)]
            }
            
            logger.info(f"  Min: {metrics['min_latency_ms']:.2f} ms")
            logger.info(f"  Avg: {metrics['avg_latency_ms']:.2f} ms")
            logger.info(f"  P95: {metrics['p95_latency_ms']:.2f} ms")
            logger.info(f"  P99: {metrics['p99_latency_ms']:.2f} ms")
            logger.info(f"  Max: {metrics['max_latency_ms']:.2f} ms")
            
            return metrics
            
        except Exception as e:
            logger.error(f"  Latency measurement failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def publish_metrics(self, metrics: Dict[str, any]) -> None:
        """
        Publish metrics to CloudWatch
        
        Args:
            metrics: Dictionary of metrics to publish
        """
        try:
            metric_data = []
            
            # Mount time
            if 'mount_time_seconds' in metrics.get('mount', {}):
                metric_data.append({
                    'MetricName': 'MountEstablishmentTime',
                    'Value': metrics['mount']['mount_time_seconds'],
                    'Unit': 'Seconds',
                    'Dimensions': [
                        {'Name': 'CrossAZ', 'Value': str(self.fsx_az != self.training_az)},
                        {'Name': 'DataVolume', 'Value': self.data_subdir}
                    ]
                })
            
            # Throughput
            if 'read_performance' in metrics:
                for perf in metrics['read_performance']:
                    if perf.get('success'):
                        metric_data.append({
                            'MetricName': 'ReadThroughput',
                            'Value': perf['throughput_mbps'],
                            'Unit': 'Megabytes/Second',
                            'Dimensions': [
                                {'Name': 'CrossAZ', 'Value': str(self.fsx_az != self.training_az)},
                                {'Name': 'DataVolume', 'Value': self.data_subdir}
                            ]
                        })
            
            # Latency
            if 'latency' in metrics and metrics['latency'].get('success'):
                for metric_name in ['avg_latency_ms', 'p95_latency_ms', 'p99_latency_ms']:
                    metric_data.append({
                        'MetricName': metric_name.replace('_', '').title(),
                        'Value': metrics['latency'][metric_name],
                        'Unit': 'Milliseconds',
                        'Dimensions': [
                            {'Name': 'CrossAZ', 'Value': str(self.fsx_az != self.training_az)},
                            {'Name': 'DataVolume', 'Value': self.data_subdir}
                        ]
                    })
            
            if metric_data:
                self.cloudwatch.put_metric_data(
                    Namespace='CrossAZValidation',
                    MetricData=metric_data
                )
                logger.info(f"✓ Published {len(metric_data)} metrics to CloudWatch")
            
        except Exception as e:
            logger.warning(f"Failed to publish metrics: {e}")
    
    def run_validation(self) -> Dict[str, any]:
        """
        Run complete validation
        
        Returns:
            Dictionary with validation results
        """
        logger.info("========================================")
        logger.info("Starting Cross-AZ FSx Validation")
        logger.info("========================================")
        
        results = {
            'start_time': datetime.utcnow().isoformat() + 'Z',
            'fsx_az': self.fsx_az,
            'training_az': self.training_az,
            'cross_az': self.fsx_az != self.training_az,
            'data_subdir': self.data_subdir
        }
        
        # 1. Mount FSx
        mount_result = self.mount_fsx()
        results['mount'] = mount_result
        
        if not mount_result['success']:
            results['success'] = False
            results['error'] = 'Mount failed'
            return results
        
        # 2. List data files
        files = self.list_data_files()
        results['files_found'] = len(files)
        
        if not files:
            logger.warning("No data files found")
            results['success'] = False
            results['error'] = 'No data files found'
            return results
        
        # 3. Measure read performance
        logger.info("========================================")
        logger.info("Measuring Read Performance")
        logger.info("========================================")
        
        read_performance = []
        for file_path in files[:3]:  # Test first 3 files
            perf = self.measure_read_performance(file_path)
            read_performance.append(perf)
        
        results['read_performance'] = read_performance
        
        # 4. Measure latency
        logger.info("========================================")
        logger.info("Measuring Network Latency")
        logger.info("========================================")
        
        latency_metrics = self.measure_latency()
        results['latency'] = latency_metrics
        
        # 5. Publish metrics to CloudWatch
        self.publish_metrics(results)
        
        # 6. Summary
        results['end_time'] = datetime.utcnow().isoformat() + 'Z'
        results['success'] = True
        
        logger.info("========================================")
        logger.info("Validation Complete")
        logger.info("========================================")
        logger.info(f"  Cross-AZ: {results['cross_az']}")
        logger.info(f"  Files found: {results['files_found']}")
        logger.info(f"  Mount time: {mount_result['mount_time_seconds']:.2f}s")
        
        if read_performance:
            avg_throughput = sum(p['throughput_mbps'] for p in read_performance if p.get('success')) / len([p for p in read_performance if p.get('success')])
            logger.info(f"  Avg throughput: {avg_throughput:.2f} MB/s")
        
        if latency_metrics.get('success'):
            logger.info(f"  Avg latency: {latency_metrics['avg_latency_ms']:.2f} ms")
        
        return results


def main():
    """Main entry point"""
    try:
        validator = FSxValidator()
        results = validator.run_validation()
        
        # Save results
        output_dir = Path('/opt/ml/output')
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = output_dir / 'validation_results.json'
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"Results saved to {output_file}")
        
        # Exit with appropriate code
        sys.exit(0 if results.get('success') else 1)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
