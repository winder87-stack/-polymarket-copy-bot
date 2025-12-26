"""
Wallet Behavior Data Storage System
===================================

Persistent storage system for wallet behavior analysis, classifications,
and historical tracking. Provides efficient data management with
compression, indexing, and automatic cleanup.

Features:
- Compressed JSON storage with metadata
- Time-series data management
- Automatic data cleanup and optimization
- Backup and recovery capabilities
- Performance analytics and caching
"""

import json
import logging
import os
import shutil
import time
import zlib
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class WalletBehaviorStore:
    """
    Advanced data storage system for wallet behavior analysis.

    Handles persistent storage of:
    - Wallet classifications and metadata
    - Historical behavior analysis results
    - Performance metrics and trends
    - Market maker detection data
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path("data/wallet_behavior")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Storage paths
        self.classifications_file = self.data_dir / "classifications.json.gz"
        self.behavior_history_file = self.data_dir / "behavior_history.json.gz"
        self.metadata_file = self.data_dir / "metadata.json"
        self.backups_dir = self.data_dir / "backups"
        self.backups_dir.mkdir(exist_ok=True)

        # In-memory caches
        self._classifications_cache: Optional[Dict[str, Any]] = None
        self._behavior_cache: Optional[Dict[str, List[Dict[str, Any]]]] = None
        self._metadata_cache: Optional[Dict[str, Any]] = None

        # Cache settings
        self.cache_ttl = 300  # 5 minutes
        self._last_cache_update = 0

        # Storage settings
        self.compression_level = 6  # zlib compression level
        self.max_history_per_wallet = 200  # Maximum history entries per wallet
        self.backup_interval_days = 7  # Backup frequency

        # Initialize storage
        self._initialize_storage()

        logger.info(f"💾 Wallet behavior store initialized at {self.data_dir}")

    def _initialize_storage(self):
        """Initialize storage files and directories"""
        # Create metadata if it doesn't exist
        if not self.metadata_file.exists():
            metadata = {
                "created_at": datetime.now().isoformat(),
                "version": "1.0",
                "total_wallets": 0,
                "last_backup": None,
                "storage_stats": {
                    "total_classifications": 0,
                    "total_history_entries": 0,
                    "compressed_size_mb": 0,
                    "last_optimization": None
                }
            }
            self._save_metadata(metadata)

        # Create empty data files if they don't exist
        if not self.classifications_file.exists():
            self._save_compressed_json(self.classifications_file, {})

        if not self.behavior_history_file.exists():
            self._save_compressed_json(self.behavior_history_file, {})

    def store_wallet_classification(
        self,
        wallet_address: str,
        classification_data: Dict[str, Any]
    ) -> bool:
        """
        Store wallet classification data with metadata and timestamps.

        Args:
            wallet_address: Normalized wallet address
            classification_data: Complete classification analysis

        Returns:
            Success status
        """
        try:
            # Load current classifications
            classifications = self._load_classifications()

            # Add metadata
            classification_data["_stored_at"] = datetime.now().isoformat()
            classification_data["_version"] = "1.0"

            # Store classification
            classifications[wallet_address] = classification_data

            # Save to disk
            self._save_compressed_json(self.classifications_file, classifications)

            # Update metadata
            self._update_metadata_stats()

            # Clear cache
            self._invalidate_cache()

            logger.debug(f"💾 Stored classification for {wallet_address}")
            return True

        except Exception as e:
            logger.error(f"Error storing classification for {wallet_address}: {e}")
            return False

    def store_behavior_history(
        self,
        wallet_address: str,
        behavior_entry: Dict[str, Any]
    ) -> bool:
        """
        Store behavior analysis history entry.

        Args:
            wallet_address: Normalized wallet address
            behavior_entry: Behavior analysis entry with timestamp

        Returns:
            Success status
        """
        try:
            # Load current behavior history
            behavior_history = self._load_behavior_history()

            # Initialize wallet history if needed
            if wallet_address not in behavior_history:
                behavior_history[wallet_address] = []

            # Add metadata
            behavior_entry["_stored_at"] = datetime.now().isoformat()

            # Append new entry
            behavior_history[wallet_address].append(behavior_entry)

            # Maintain size limits (keep most recent entries)
            if len(behavior_history[wallet_address]) > self.max_history_per_wallet:
                # Keep the most recent entries
                behavior_history[wallet_address] = behavior_history[wallet_address][-self.max_history_per_wallet:]

            # Save to disk
            self._save_compressed_json(self.behavior_history_file, behavior_history)

            # Update metadata
            self._update_metadata_stats()

            # Clear cache
            self._invalidate_cache()

            logger.debug(f"💾 Stored behavior history entry for {wallet_address}")
            return True

        except Exception as e:
            logger.error(f"Error storing behavior history for {wallet_address}: {e}")
            return False

    def get_wallet_classification(self, wallet_address: str) -> Optional[Dict[str, Any]]:
        """Retrieve wallet classification data"""
        classifications = self._load_classifications()
        return classifications.get(wallet_address)

    def get_wallet_behavior_history(
        self,
        wallet_address: str,
        limit: Optional[int] = None,
        days_back: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve wallet behavior history with optional filtering.

        Args:
            wallet_address: Normalized wallet address
            limit: Maximum number of entries to return
            days_back: Only return entries from last N days

        Returns:
            List of behavior history entries (newest first)
        """
        behavior_history = self._load_behavior_history()

        if wallet_address not in behavior_history:
            return []

        history = behavior_history[wallet_address].copy()

        # Filter by days back if specified
        if days_back:
            cutoff_date = datetime.now() - timedelta(days=days_back)
            history = [
                entry for entry in history
                if datetime.fromisoformat(entry.get('timestamp', datetime.min.isoformat())) >= cutoff_date
            ]

        # Sort by timestamp (newest first)
        history.sort(
            key=lambda x: x.get('timestamp', datetime.min.isoformat()),
            reverse=True
        )

        # Apply limit
        if limit:
            history = history[:limit]

        return history

    def get_all_classifications(self) -> Dict[str, Any]:
        """Get all wallet classifications"""
        return self._load_classifications()

    def get_behavior_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics for stored behavior data"""

        classifications = self._load_classifications()
        behavior_history = self._load_behavior_history()

        # Classification distribution
        classification_counts = defaultdict(int)
        mm_probabilities = []
        confidence_scores = []

        for wallet_data in classifications.values():
            classification = wallet_data.get('classification', 'unknown')
            classification_counts[classification] += 1

            mm_prob = wallet_data.get('market_maker_probability', 0)
            conf_score = wallet_data.get('confidence_score', 0)

            mm_probabilities.append(mm_prob)
            confidence_scores.append(conf_score)

        # Behavior history stats
        total_history_entries = sum(len(history) for history in behavior_history.values())
        wallets_with_history = len(behavior_history)

        # Market maker concentration
        market_makers = classification_counts.get('market_maker', 0)
        total_classified = len(classifications)

        return {
            "total_wallets_classified": total_classified,
            "total_history_entries": total_history_entries,
            "wallets_with_history": wallets_with_history,
            "classification_distribution": dict(classification_counts),
            "market_maker_percentage": market_makers / total_classified if total_classified > 0 else 0,
            "avg_market_maker_probability": sum(mm_probabilities) / len(mm_probabilities) if mm_probabilities else 0,
            "avg_confidence_score": sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0,
            "high_confidence_classifications": sum(1 for score in confidence_scores if score >= 0.8),
            "storage_stats": self.get_storage_stats()
        }

    def detect_classification_changes(
        self,
        hours_back: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Detect wallets with recent classification changes.

        Args:
            hours_back: Hours to look back for changes

        Returns:
            List of wallets with classification changes
        """
        changes = []
        behavior_history = self._load_behavior_history()
        cutoff_time = datetime.now() - timedelta(hours=hours_back)

        for wallet_address, history in behavior_history.items():
            if len(history) < 2:
                continue

            # Get recent entries
            recent_entries = [
                entry for entry in history
                if datetime.fromisoformat(entry.get('timestamp', datetime.min.isoformat())) >= cutoff_time
            ]

            if len(recent_entries) < 2:
                continue

            # Sort by timestamp
            recent_entries.sort(key=lambda x: x.get('timestamp', ''))

            # Check for classification changes
            first_classification = recent_entries[0].get('classification')
            last_classification = recent_entries[-1].get('classification')

            if first_classification != last_classification:
                changes.append({
                    "wallet_address": wallet_address,
                    "previous_classification": first_classification,
                    "current_classification": last_classification,
                    "change_timestamp": recent_entries[-1].get('timestamp'),
                    "hours_since_change": (datetime.now() - datetime.fromisoformat(recent_entries[-1].get('timestamp', datetime.now().isoformat()))).total_seconds() / 3600,
                    "confidence_current": recent_entries[-1].get('confidence_score', 0),
                    "mm_probability_change": recent_entries[-1].get('market_maker_probability', 0) - recent_entries[0].get('market_maker_probability', 0)
                })

        return changes

    def optimize_storage(self) -> Dict[str, Any]:
        """Optimize storage by cleaning up old data and compressing"""

        optimization_stats = {
            "old_entries_removed": 0,
            "size_before_mb": 0,
            "size_after_mb": 0,
            "compression_ratio": 0,
            "optimization_timestamp": datetime.now().isoformat()
        }

        try:
            # Get current size
            optimization_stats["size_before_mb"] = self._get_directory_size_mb()

            # Clean up old behavior history entries (keep last 100 per wallet)
            behavior_history = self._load_behavior_history()
            entries_removed = 0

            for wallet_address, history in behavior_history.items():
                if len(history) > 100:
                    removed = len(history) - 100
                    behavior_history[wallet_address] = history[-100:]
                    entries_removed += removed

            # Save optimized data
            if entries_removed > 0:
                self._save_compressed_json(self.behavior_history_file, behavior_history)
                logger.info(f"🧹 Removed {entries_removed} old behavior history entries")

            optimization_stats["old_entries_removed"] = entries_removed

            # Recompress all files with optimal settings
            self._recompress_all_files()

            # Update metadata
            metadata = self._load_metadata()
            metadata["storage_stats"]["last_optimization"] = datetime.now().isoformat()
            self._save_metadata(metadata)

            # Get new size
            optimization_stats["size_after_mb"] = self._get_directory_size_mb()
            optimization_stats["compression_ratio"] = (
                optimization_stats["size_before_mb"] / optimization_stats["size_after_mb"]
                if optimization_stats["size_after_mb"] > 0 else 1
            )

            # Clear cache
            self._invalidate_cache()

            logger.info(
                f"✅ Storage optimization complete: "
                f"{optimization_stats['size_before_mb']:.2f}MB → {optimization_stats['size_after_mb']:.2f}MB "
                f"({optimization_stats['compression_ratio']:.2f}x compression)"
            )

        except Exception as e:
            logger.error(f"Error during storage optimization: {e}")

        return optimization_stats

    def create_backup(self) -> Optional[Path]:
        """Create a backup of all behavior data"""

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.backups_dir / f"wallet_behavior_backup_{timestamp}.tar.gz"

            # Create backup archive
            import tarfile
            with tarfile.open(backup_file, "w:gz") as tar:
                # Add all data files
                for file_path in [self.classifications_file, self.behavior_history_file, self.metadata_file]:
                    if file_path.exists():
                        tar.add(file_path, arcname=file_path.name)

            # Update metadata
            metadata = self._load_metadata()
            metadata["last_backup"] = datetime.now().isoformat()
            self._save_metadata(metadata)

            logger.info(f"💾 Created backup: {backup_file}")
            return backup_file

        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            return None

    def restore_from_backup(self, backup_file: Path) -> bool:
        """Restore data from backup file"""

        try:
            import tarfile

            # Extract backup
            with tarfile.open(backup_file, "r:gz") as tar:
                tar.extractall(self.data_dir, filter='data')

            # Clear cache
            self._invalidate_cache()

            logger.info(f"🔄 Restored from backup: {backup_file}")
            return True

        except Exception as e:
            logger.error(f"Error restoring from backup: {e}")
            return False

    def get_storage_stats(self) -> Dict[str, Any]:
        """Get detailed storage statistics"""

        try:
            classifications_size = self.classifications_file.stat().st_size if self.classifications_file.exists() else 0
            behavior_size = self.behavior_history_file.stat().st_size if self.behavior_history_file.exists() else 0
            metadata_size = self.metadata_file.stat().st_size if self.metadata_file.exists() else 0

            total_size_mb = (classifications_size + behavior_size + metadata_size) / (1024 * 1024)

            classifications = self._load_classifications()
            behavior_history = self._load_behavior_history()

            total_history_entries = sum(len(history) for history in behavior_history.values())

            return {
                "total_size_mb": round(total_size_mb, 2),
                "classifications_file_mb": round(classifications_size / (1024 * 1024), 2),
                "behavior_history_file_mb": round(behavior_size / (1024 * 1024), 2),
                "metadata_file_mb": round(metadata_size / (1024 * 1024), 2),
                "total_wallets": len(classifications),
                "total_history_entries": total_history_entries,
                "avg_history_per_wallet": total_history_entries / len(classifications) if classifications else 0,
                "compression_ratio": self._calculate_compression_ratio(),
                "last_backup": self._load_metadata().get("last_backup"),
                "last_optimization": self._load_metadata().get("storage_stats", {}).get("last_optimization")
            }

        except Exception as e:
            logger.error(f"Error getting storage stats: {e}")
            return {}

    # Private helper methods

    def _load_classifications(self) -> Dict[str, Any]:
        """Load classifications with caching"""
        if self._should_use_cache():
            if self._classifications_cache is not None:
                return self._classifications_cache

        try:
            classifications = self._load_compressed_json(self.classifications_file)
            self._classifications_cache = classifications
            self._last_cache_update = time.time()
            return classifications
        except Exception as e:
            logger.error(f"Error loading classifications: {e}")
            return {}

    def _load_behavior_history(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load behavior history with caching"""
        if self._should_use_cache():
            if self._behavior_cache is not None:
                return self._behavior_cache

        try:
            behavior_history = self._load_compressed_json(self.behavior_history_file)
            self._behavior_cache = behavior_history
            self._last_cache_update = time.time()
            return behavior_history
        except Exception as e:
            logger.error(f"Error loading behavior history: {e}")
            return {}

    def _load_metadata(self) -> Dict[str, Any]:
        """Load metadata"""
        if self._metadata_cache is not None and self._should_use_cache():
            return self._metadata_cache

        try:
            if self.metadata_file.exists():
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
            else:
                metadata = {}
            self._metadata_cache = metadata
            return metadata
        except Exception as e:
            logger.error(f"Error loading metadata: {e}")
            return {}

    def _save_metadata(self, metadata: Dict[str, Any]):
        """Save metadata"""
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, default=str)
            self._metadata_cache = metadata
        except Exception as e:
            logger.error(f"Error saving metadata: {e}")

    def _should_use_cache(self) -> bool:
        """Check if cache should be used"""
        return time.time() - self._last_cache_update < self.cache_ttl

    def _invalidate_cache(self):
        """Invalidate all caches"""
        self._classifications_cache = None
        self._behavior_cache = None
        self._metadata_cache = None
        self._last_cache_update = 0

    def _update_metadata_stats(self):
        """Update storage statistics in metadata"""
        try:
            metadata = self._load_metadata()
            stats = metadata.get("storage_stats", {})

            classifications = self._load_classifications()
            behavior_history = self._load_behavior_history()

            stats["total_classifications"] = len(classifications)
            stats["total_history_entries"] = sum(len(history) for history in behavior_history.values())
            stats["compressed_size_mb"] = self._get_directory_size_mb()

            metadata["storage_stats"] = stats
            metadata["total_wallets"] = len(classifications)

            self._save_metadata(metadata)

        except Exception as e:
            logger.error(f"Error updating metadata stats: {e}")

    def _load_compressed_json(self, file_path: Path) -> Any:
        """Load compressed JSON data"""
        if not file_path.exists():
            return {}

        try:
            with open(file_path, 'rb') as f:
                compressed_data = f.read()
                json_data = zlib.decompress(compressed_data)
                return json.loads(json_data.decode('utf-8'))
        except Exception as e:
            logger.error(f"Error loading compressed JSON from {file_path}: {e}")
            return {}

    def _save_compressed_json(self, file_path: Path, data: Any):
        """Save data as compressed JSON"""
        try:
            json_str = json.dumps(data, default=str, separators=(',', ':'))
            compressed_data = zlib.compress(json_str.encode('utf-8'), level=self.compression_level)

            with open(file_path, 'wb') as f:
                f.write(compressed_data)

        except Exception as e:
            logger.error(f"Error saving compressed JSON to {file_path}: {e}")

    def _get_directory_size_mb(self) -> float:
        """Get total size of data directory in MB"""
        try:
            total_size = 0
            for file_path in self.data_dir.rglob('*'):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
            return total_size / (1024 * 1024)
        except Exception:
            return 0

    def _calculate_compression_ratio(self) -> float:
        """Calculate effective compression ratio"""
        try:
            # Estimate by comparing compressed vs uncompressed sizes
            classifications = self._load_classifications()
            behavior_history = self._load_behavior_history()

            # Rough estimate of uncompressed size
            uncompressed_size = len(json.dumps(classifications, default=str)) + len(json.dumps(behavior_history, default=str))
            compressed_size = (
                (self.classifications_file.stat().st_size if self.classifications_file.exists() else 0) +
                (self.behavior_history_file.stat().st_size if self.behavior_history_file.exists() else 0)
            )

            return uncompressed_size / compressed_size if compressed_size > 0 else 1

        except Exception:
            return 1

    def _recompress_all_files(self):
        """Recompress all data files with optimal settings"""
        try:
            # Reload and resave all data with current compression settings
            classifications = self._load_classifications()
            self._save_compressed_json(self.classifications_file, classifications)

            behavior_history = self._load_behavior_history()
            self._save_compressed_json(self.behavior_history_file, behavior_history)

            logger.debug("🔄 Recompressed all data files")

        except Exception as e:
            logger.error(f"Error recompressing files: {e}")

    def cleanup_old_backups(self, keep_days: int = 30):
        """Clean up old backup files"""
        try:
            cutoff_date = datetime.now() - timedelta(days=keep_days)
            removed_count = 0

            for backup_file in self.backups_dir.glob("*.tar.gz"):
                try:
                    # Extract timestamp from filename
                    timestamp_str = backup_file.stem.split('_')[-1]
                    file_date = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")

                    if file_date < cutoff_date:
                        backup_file.unlink()
                        removed_count += 1

                except Exception:
                    continue

            if removed_count > 0:
                logger.info(f"🗑️ Removed {removed_count} old backup files")

        except Exception as e:
            logger.error(f"Error cleaning up old backups: {e}")
